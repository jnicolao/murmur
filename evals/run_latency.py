"""Measure the Phase 1 voice loop on this machine.

The design doc's first risk is that four models contending for 16 GB push
time-to-first-audio past two seconds. This measures the critical path end to
end before anything else is built on top of it.

    uv run --project apps/api python evals/run_latency.py

Writes evals/results/latency-<timestamp>.json
"""

from __future__ import annotations

import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from murmur.audio.asr import DEFAULT_MODEL as ASR_MODEL
from murmur.audio.asr import SAMPLE_RATE, Transcriber
from murmur.audio.sentences import stream_sentences
from murmur.audio.tts import Speaker
from murmur.llm.client import DEFAULT_MODEL, Ollama
from murmur.llm.prompts import PROMPT_VERSION, REFLECT_SYSTEM
from murmur.safety.check import SafetyCheck

# Realistic journal entries. Nothing here should trip a safety path.
UTTERANCES = [
    (
        "I had a really long day at work today and I keep replaying that "
        "conversation with my manager in my head."
    ),
    (
        "I don't really know why I've been feeling so flat this week. Nothing is "
        "wrong exactly, it just all feels like effort."
    ),
    (
        "I finally finished the thing I had been putting off for a month and I "
        "feel a lot lighter than I expected to."
    ),
    (
        "My sister called and we ended up arguing about the same thing we always "
        "argue about, and I hung up feeling like the bad guy."
    ),
    (
        "I have been sleeping badly for about two weeks now and I think it is "
        "making everything feel harder than it actually is."
    ),
]

FIXTURES = ROOT / "evals" / "datasets" / "audio"


def build_fixtures(speaker: Speaker) -> list[Path]:
    """Synthesise the test utterances once so runs are reproducible."""
    FIXTURES.mkdir(parents=True, exist_ok=True)
    paths = []
    for i, text in enumerate(UTTERANCES):
        path = FIXTURES / f"utterance-{i:02d}.wav"
        if not path.exists():
            audio = speaker.say(text)
            sf.write(path, audio, 24_000)
        paths.append(path)
    return paths


def load_16k(path: Path) -> np.ndarray:
    audio, rate = sf.read(path, dtype="float32")
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    if rate != SAMPLE_RATE:
        # Linear resample is fine here: the fixture is clean synthetic speech.
        n = round(len(audio) * SAMPLE_RATE / rate)
        audio = np.interp(
            np.linspace(0, len(audio), n, endpoint=False),
            np.arange(len(audio)),
            audio,
        ).astype(np.float32)
    return audio


def run_turn(
    audio: np.ndarray,
    transcriber: Transcriber,
    llm: Ollama,
    speaker: Speaker,
    safety: SafetyCheck,
) -> dict:
    """One full turn. t0 is the moment the user stops speaking."""
    t0 = time.perf_counter()

    transcript = transcriber.transcribe(audio)
    t_asr = time.perf_counter()

    # Safety sits in the critical path from Phase 2 on: nothing the model
    # writes may reach someone in crisis, so the check has to finish first.
    verdict = safety.run(transcript)
    t_safety = time.perf_counter()
    if verdict.triggered:
        raise RuntimeError(f"fixture tripped the crisis path: {transcript!r}")

    first_sentence = None
    t_first_sentence = None
    sentences = []
    for sentence in stream_sentences(llm.stream(REFLECT_SYSTEM, transcript)):
        sentences.append(sentence)
        if first_sentence is None:
            first_sentence = sentence
            t_first_sentence = time.perf_counter()
            break  # TTFA only needs the first sentence

    if first_sentence is None:
        raise RuntimeError("model produced no sentence")

    reply_audio = speaker.say(first_sentence)
    t_first_audio = time.perf_counter()

    return {
        "transcript": transcript,
        "first_sentence": first_sentence,
        "asr_ms": round((t_asr - t0) * 1000),
        "safety_ms": round((t_safety - t_asr) * 1000),
        "llm_first_sentence_ms": round((t_first_sentence - t_safety) * 1000),
        "tts_ms": round((t_first_audio - t_first_sentence) * 1000),
        "ttfa_ms": round((t_first_audio - t0) * 1000),
        "audio_seconds": round(len(audio) / SAMPLE_RATE, 2),
        "reply_audio_seconds": round(len(reply_audio) / 24_000, 2),
    }


def percentile(values: list[int], pct: float) -> int:
    ordered = sorted(values)
    k = (len(ordered) - 1) * pct
    lo, hi = int(k), min(int(k) + 1, len(ordered) - 1)
    return round(ordered[lo] + (ordered[hi] - ordered[lo]) * (k - lo))


def main() -> int:
    print("loading models...")
    t = time.perf_counter()
    speaker = Speaker()
    tts_load = time.perf_counter() - t

    t = time.perf_counter()
    transcriber = Transcriber()
    asr_load = time.perf_counter() - t

    llm = Ollama()
    safety = SafetyCheck(llm)
    print(f"  tts loaded in {tts_load:.1f}s, asr loaded in {asr_load:.1f}s")

    paths = build_fixtures(speaker)
    clips = [load_16k(p) for p in paths]

    # One warm turn so the Ollama model is resident and caches are hot.
    print("warming up...")
    run_turn(clips[0], transcriber, llm, speaker, safety)

    turns = []
    for i, clip in enumerate(clips):
        turn = run_turn(clip, transcriber, llm, speaker, safety)
        turns.append(turn)
        print(
            f"  [{i + 1}/{len(clips)}] ttfa={turn['ttfa_ms']}ms "
            f"(asr {turn['asr_ms']} + safety {turn['safety_ms']} + "
            f"llm {turn['llm_first_sentence_ms']} + tts {turn['tts_ms']})"
        )

    ttfa = [t["ttfa_ms"] for t in turns]
    summary = {
        "prompt_version": PROMPT_VERSION,
        "model": DEFAULT_MODEL,
        "asr_model": f"{ASR_MODEL}/int8",
        "ran_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "turns": len(turns),
        "ttfa_p50_ms": percentile(ttfa, 0.5),
        "ttfa_p95_ms": percentile(ttfa, 0.95),
        "asr_p50_ms": percentile([t["asr_ms"] for t in turns], 0.5),
        "safety_p50_ms": percentile([t["safety_ms"] for t in turns], 0.5),
        "llm_first_sentence_p50_ms": percentile([t["llm_first_sentence_ms"] for t in turns], 0.5),
        "tts_p50_ms": percentile([t["tts_ms"] for t in turns], 0.5),
        "model_load_seconds": {"tts": round(tts_load, 1), "asr": round(asr_load, 1)},
        "detail": turns,
    }

    out_dir = ROOT / "evals" / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out = out_dir / f"latency-{stamp}.json"
    out.write_text(json.dumps(summary, indent=2) + "\n")

    target = 2000
    verdict = "PASS" if summary["ttfa_p50_ms"] <= target else "FAIL"
    print(
        f"\n{verdict}  ttfa p50={summary['ttfa_p50_ms']}ms "
        f"p95={summary['ttfa_p95_ms']}ms  (target p50 <= {target}ms)"
    )
    print(f"written to {out.relative_to(ROOT)}")
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
