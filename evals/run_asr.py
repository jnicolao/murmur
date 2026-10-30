"""Compare Whisper sizes on speed and accuracy, on speech worth testing.

This used to score only synthesised fixtures, where every model size got
every word right. That said the test was easy, not that transcription was
solved, and the default model was chosen on the strength of it.

It now scores whatever real speech is on this machine:

- the owner's own recordings, once exported and hand-corrected
- a slice of LibriSpeech dev-clean, real human audio under CC BY 4.0
- the synthetic fixtures, kept only as a smoke test

    apps/api/.venv/bin/python evals/run_asr.py [clips per source]
"""

from __future__ import annotations

import json
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))
sys.path.insert(0, str(ROOT / "evals"))

from corpus import DOWNLOAD_HINT, Clip, available, load_audio

from murmur.audio.asr import Transcriber

SIZES = ["tiny.en", "base.en", "small.en"]


def normalise(text: str) -> list[str]:
    return re.sub(r"[^a-z0-9' ]", " ", text.lower()).split()


def wer(reference: str, hypothesis: str) -> float:
    """Word error rate by Levenshtein distance over words."""
    ref, hyp = normalise(reference), normalise(hypothesis)
    if not ref:
        return 0.0
    previous = list(range(len(hyp) + 1))
    for i, want in enumerate(ref, 1):
        current = [i]
        for j, got in enumerate(hyp, 1):
            current.append(
                min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (want != got))
            )
        previous = current
    return previous[-1] / len(ref)


def score(transcriber: Transcriber, clips: list[Clip]) -> dict:
    times, errors, worst = [], [], None
    for clip in clips:
        audio = load_audio(clip.path)
        started = time.perf_counter()
        heard = transcriber.transcribe(audio)
        times.append((time.perf_counter() - started) * 1000)
        rate = wer(clip.truth, heard)
        errors.append(rate)
        if worst is None or rate > worst["wer"]:
            worst = {"wer": rate, "truth": clip.truth, "heard": heard, "id": clip.clip_id}

    ordered = sorted(times)
    return {
        "clips": len(clips),
        "mean_ms": round(sum(times) / len(times)),
        "p95_ms": round(ordered[min(int(len(ordered) * 0.95), len(ordered) - 1)]),
        "mean_wer": round(sum(errors) / len(errors), 4),
        "perfect": sum(1 for e in errors if e == 0),
        "worst": worst,
    }


def main() -> int:
    limit = int(next((a for a in sys.argv[1:] if a.isdigit()), 100))
    sources = available(limit)

    if "librispeech" not in sources:
        print(f"LibriSpeech dev-clean\n{DOWNLOAD_HINT}\n")
    if "own" not in sources:
        print(
            "No corrected recordings of your own yet. They are the only source that "
            "says how this performs for you.\n"
            "  apps/api/.venv/bin/python apps/api/tools/export_recordings.py\n"
        )
    if not sources:
        print("Nothing to score.")
        return 1

    results: dict[str, dict] = {}
    for size in SIZES:
        transcriber = Transcriber(model_size=size)
        transcriber.transcribe(load_audio(next(iter(sources.values()))[0].path))  # warm
        results[size] = {name: score(transcriber, clips) for name, clips in sources.items()}
        line = "  ".join(f"{name} {results[size][name]['mean_wer']:.1%}" for name in sources)
        print(f"{size:<10} {line}")

    summary = {
        "ran_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "sources": {name: len(clips) for name, clips in sources.items()},
        "models": results,
    }
    out = ROOT / "evals" / "results" / f"asr-{datetime.now(UTC):%Y%m%dT%H%M%SZ}.json"
    out.write_text(json.dumps(summary, indent=2) + "\n")

    print(f"\n{'model':<10} {'source':<12} {'clips':>5} {'mean ms':>8} {'WER':>7} {'perfect':>8}")
    for size in SIZES:
        for name in sources:
            row = results[size][name]
            print(
                f"{size:<10} {name:<12} {row['clips']:>5} {row['mean_ms']:>8} "
                f"{row['mean_wer']:>6.1%} {row['perfect']:>7}/{row['clips']}"
            )

    real = [name for name in sources if name != "synthetic"]
    if real:
        print("\nworst clip per model, on real speech:")
        for size in SIZES:
            worst = max((results[size][name]["worst"] for name in real), key=lambda w: w["wer"])
            print(f"  {size:<10} {worst['wer']:>5.0%}  heard: {worst['heard'][:62]}")

    print(f"\nwritten to {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
