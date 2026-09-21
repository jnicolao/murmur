"""One voice turn over one WebSocket connection.

Protocol, client to server:
    binary            Int16 PCM mono at 16 kHz, appended to the current utterance
    {"type":"end"}    the person stopped speaking; run the turn
    {"type":"stop"}   barge-in; abandon whatever is still being spoken

Protocol, server to client:
    {"type":"transcript","text":...}   what was heard
    {"type":"reply","text":...}        one speech unit, sent just before its audio
    binary                             Int16 PCM mono at 24 kHz for that unit
    {"type":"done","timings":{...}}    turn finished
    {"type":"error","message":...}
"""

from __future__ import annotations

import asyncio
import time

import numpy as np
from fastapi import WebSocket

from murmur.audio.asr import SAMPLE_RATE, Transcriber
from murmur.audio.sentences import stream_sentences
from murmur.audio.tts import Speaker
from murmur.llm.client import Ollama
from murmur.llm.prompts import REFLECT_SYSTEM


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

    def warm(self) -> None:
        """Run one tiny turn so the first real one is not paying setup costs."""
        self.transcriber.transcribe(np.zeros(SAMPLE_RATE // 2, dtype=np.float32))
        self.speaker.say("Ready.")

    async def run_turn(self, websocket: WebSocket, pcm: bytes, cancelled: asyncio.Event) -> None:
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

        ttfa_ms = None
        spoken = []
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

        cancelled.set()  # stop the producer if the client went away
        await producer

        await websocket.send_json(
            {
                "type": "done",
                "cancelled": len(spoken) == 0,
                "timings": {
                    "asr_ms": round((t_asr - t0) * 1000),
                    "ttfa_ms": ttfa_ms,
                    "total_ms": round((time.perf_counter() - t0) * 1000),
                },
            }
        )
