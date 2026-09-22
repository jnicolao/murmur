"""One voice turn over one WebSocket connection.

Protocol, client to server:
    binary            Int16 PCM mono at 16 kHz, appended to the current utterance
    {"type":"end"}    the person stopped speaking; run the turn
    {"type":"stop"}   barge-in; abandon whatever is still being spoken
    {"type":"mood","value":1..5}   the check-in after a session

Protocol, server to client:
    {"type":"transcript","text":...}   what was heard
    {"type":"reply","text":...}        one speech unit, sent just before its audio
    {"type":"crisis","text":...,"resources":[...]}   the crisis path, not a reply
    binary                             Int16 PCM mono at 24 kHz for that unit
    {"type":"done","timings":{...}}    turn finished
    {"type":"error","message":...}
"""

from __future__ import annotations

import asyncio
import time

import numpy as np
from fastapi import WebSocket

from murmur.affect import prosody
from murmur.audio.asr import SAMPLE_RATE, Transcriber
from murmur.audio.sentences import stream_sentences
from murmur.audio.tts import Speaker
from murmur.llm.client import DEFAULT_MODEL, Ollama
from murmur.llm.prompts import PROMPT_VERSION, REFLECT_SYSTEM
from murmur.safety.check import SafetyCheck
from murmur.safety.classifier import CLASSIFIER_VERSION
from murmur.safety.response import CRISIS_MESSAGE, resources
from murmur.store.db import Store


def to_float32(pcm: bytes) -> np.ndarray:
    return np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768.0


def to_int16(audio: np.ndarray) -> bytes:
    return np.clip(audio * 32767.0, -32768, 32767).astype("<i2").tobytes()


class Session:
    """Holds the models for the process. Loading them takes seconds, so one
    instance is shared across connections."""

    def __init__(self) -> None:
        self.transcriber = Transcriber()
        self.speaker = Speaker()
        self.llm = Ollama()
        self.safety = SafetyCheck(self.llm)
        self.store = Store()

    def warm(self) -> None:
        """Run one tiny turn so the first real one is not paying setup costs."""
        self.transcriber.transcribe(np.zeros(SAMPLE_RATE // 2, dtype=np.float32))
        self.speaker.say("Ready.")
        self.safety.run("I had a quiet day.")
        # librosa loads its submodules on first use, which costs most of a
        # second. Pay it here rather than on somebody's first entry.
        prosody.extract(np.zeros(SAMPLE_RATE, dtype=np.float32), SAMPLE_RATE, 0)

    async def _speak(self, websocket: WebSocket, text: str) -> None:
        clip = await asyncio.to_thread(self.speaker.say, text)
        await websocket.send_bytes(to_int16(clip))

    async def run_turn(
        self, websocket: WebSocket, entry_id: int, pcm: bytes, cancelled: asyncio.Event
    ) -> None:
        t0 = time.perf_counter()
        audio = to_float32(pcm)
        if audio.size < SAMPLE_RATE // 4:
            await websocket.send_json({"type": "error", "message": "That was too short to hear."})
            return

        transcript = await asyncio.to_thread(self.transcriber.transcribe, audio)
        t_asr = time.perf_counter()
        if not transcript:
            await websocket.send_json({"type": "error", "message": "I did not catch that."})
            return
        await websocket.send_json({"type": "transcript", "text": transcript})

        utterance_id = await asyncio.to_thread(
            self.store.add_utterance,
            entry_id,
            transcript,
            audio,
            SAMPLE_RATE,
            round((t_asr - t0) * 1000),
        )

        # How it sounded is measured beside the reply, never before it. There
        # is about 60 ms of headroom in the turn and this is not worth any of
        # it, so the task is started here and collected once the talking is
        # done.
        measuring = asyncio.create_task(
            asyncio.to_thread(self._measure, utterance_id, audio, len(transcript.split()))
        )

        # Safety runs before a single token of reply is generated, so nothing
        # the model writes can reach someone in crisis.
        verdict = await asyncio.to_thread(self.safety.run, transcript)
        t_safety = time.perf_counter()

        if verdict.triggered:
            await self._crisis(websocket, utterance_id, t0)
            await measuring
            await websocket.send_json(
                {
                    "type": "done",
                    "crisis": True,
                    "timings": {
                        "asr_ms": round((t_asr - t0) * 1000),
                        "safety_ms": round((t_safety - t_asr) * 1000),
                        "ttfa_ms": round((time.perf_counter() - t0) * 1000),
                        "total_ms": round((time.perf_counter() - t0) * 1000),
                    },
                }
            )
            return

        ttfa_ms, spoken = await self._reflect(websocket, transcript, cancelled, t0)

        await asyncio.to_thread(
            self.store.add_reply,
            utterance_id,
            " ".join(spoken),
            model=DEFAULT_MODEL,
            prompt_version=PROMPT_VERSION,
            latency_ms=round((time.perf_counter() - t0) * 1000),
        )
        if ttfa_ms is not None:
            await asyncio.to_thread(self.store.set_ttfa, utterance_id, ttfa_ms)
        await measuring

        await websocket.send_json(
            {
                "type": "done",
                "cancelled": len(spoken) == 0,
                "timings": {
                    "asr_ms": round((t_asr - t0) * 1000),
                    "safety_ms": round((t_safety - t_asr) * 1000),
                    "ttfa_ms": ttfa_ms,
                    "total_ms": round((time.perf_counter() - t0) * 1000),
                },
            }
        )

    def _measure(self, utterance_id: int, audio: np.ndarray, word_count: int) -> None:
        """Prosody for one utterance. Failing here must never fail the turn:
        a missing measurement is a gap in a chart, a raised exception is a
        journal entry the person loses."""
        try:
            values = prosody.extract(audio, SAMPLE_RATE, word_count)
            self.store.set_prosody(utterance_id, values.as_row())
        except Exception as error:  # noqa: BLE001
            print(f"prosody failed for utterance {utterance_id}: {error}")

    async def _crisis(self, websocket: WebSocket, utterance_id: int, t0: float) -> None:
        """Fixed words, spoken verbatim. The model writes nothing here."""
        await websocket.send_json(
            {"type": "crisis", "text": CRISIS_MESSAGE, "resources": resources()}
        )
        await self._speak(websocket, CRISIS_MESSAGE)
        await asyncio.to_thread(
            self.store.add_reply,
            utterance_id,
            CRISIS_MESSAGE,
            safety_triggered=True,
            safety_stage="phrase-or-classifier",
            prompt_version=CLASSIFIER_VERSION,
            latency_ms=round((time.perf_counter() - t0) * 1000),
        )

    async def _reflect(
        self, websocket: WebSocket, transcript: str, cancelled: asyncio.Event, t0: float
    ) -> tuple[int | None, list[str]]:
        # The model runs on a thread so the socket keeps reading, which is what
        # makes barge-in possible mid-reply.
        queue: asyncio.Queue[str | None] = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def produce() -> None:
            try:
                for unit in stream_sentences(self.llm.stream(REFLECT_SYSTEM, transcript)):
                    if cancelled.is_set():
                        break
                    loop.call_soon_threadsafe(queue.put_nowait, unit)
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, None)

        producer = asyncio.create_task(asyncio.to_thread(produce))

        ttfa_ms: int | None = None
        spoken: list[str] = []
        while True:
            unit = await queue.get()
            if unit is None or cancelled.is_set():
                break
            await websocket.send_json({"type": "reply", "text": unit})
            clip = await asyncio.to_thread(self.speaker.say, unit)
            if cancelled.is_set():
                break
            await websocket.send_bytes(to_int16(clip))
            spoken.append(unit)
            if ttfa_ms is None:
                ttfa_ms = round((time.perf_counter() - t0) * 1000)

        cancelled.set()
        await producer
        return ttfa_ms, spoken
