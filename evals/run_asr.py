"""Compare Whisper sizes on speed and accuracy.

The latency spike put ASR at roughly half the time-to-first-audio budget, so
this measures what a smaller model actually costs in words. Ground truth is
exact: the fixtures were synthesised from known text.

    apps/api/.venv/bin/python evals/run_asr.py
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

from run_latency import UTTERANCES, build_fixtures, load_16k

from murmur.audio.asr import Transcriber

SIZES = ["tiny.en", "base.en", "small.en"]


def normalise(text: str) -> list[str]:
    return re.sub(r"[^a-z0-9' ]", " ", text.lower()).split()


def wer(reference: str, hypothesis: str) -> float:
    """Word error rate by Levenshtein distance over words."""
    ref, hyp = normalise(reference), normalise(hypothesis)
    if not ref:
        return 0.0
    prev = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        cur = [i]
        for j, h in enumerate(hyp, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (r != h)))
        prev = cur
    return prev[-1] / len(ref)


def main() -> int:
    from murmur.audio.tts import Speaker

    paths = build_fixtures(Speaker())
    clips = [load_16k(p) for p in paths]

    rows = []
    for size in SIZES:
        print(f"\n{size}")
        t = time.perf_counter()
        transcriber = Transcriber(model_size=size)
        load_s = time.perf_counter() - t

        transcriber.transcribe(clips[0])  # warm

        times, errors = [], []
        for clip, truth in zip(clips, UTTERANCES, strict=True):
            t = time.perf_counter()
            text = transcriber.transcribe(clip)
            times.append((time.perf_counter() - t) * 1000)
            errors.append(wer(truth, text))
            print(f"  {times[-1]:6.0f}ms  wer={errors[-1]:.1%}  {text[:64]}")

        row = {
            "model": size,
            "load_seconds": round(load_s, 1),
            "mean_ms": round(sum(times) / len(times)),
            "max_ms": round(max(times)),
            "mean_wer": round(sum(errors) / len(errors), 4),
        }
        rows.append(row)
        print(f"  -> mean {row['mean_ms']}ms, wer {row['mean_wer']:.1%}")

    out = {
        "ran_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "clips": len(clips),
        "note": "Ground truth is exact; fixtures are synthesised from known text.",
        "models": rows,
    }
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = ROOT / "evals" / "results" / f"asr-{stamp}.json"
    path.write_text(json.dumps(out, indent=2) + "\n")

    print("\nmodel      mean_ms   wer")
    for row in rows:
        print(f"{row['model']:<10} {row['mean_ms']:>6}  {row['mean_wer']:>6.1%}")
    print(f"\nwritten to {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
