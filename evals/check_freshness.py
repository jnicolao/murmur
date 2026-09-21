"""Fail CI when the committed safety result predates the current classifier.

A prompt change with a stale result is the failure mode this exists to catch:
the numbers in the README would describe a classifier that no longer runs.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLASSIFIER = ROOT / "apps" / "api" / "murmur" / "safety" / "classifier.py"


def current_version() -> str:
    match = re.search(r'CLASSIFIER_VERSION = "([^"]+)"', CLASSIFIER.read_text())
    if not match:
        sys.exit("could not read CLASSIFIER_VERSION")
    return match.group(1)


def main() -> int:
    version = current_version()
    results = sorted((ROOT / "evals" / "results").glob("safety-*.json"))
    if not results:
        print("no committed safety result; run evals/run_safety.py")
        return 1

    latest = json.loads(results[-1].read_text())
    if latest.get("classifier_version") != version:
        print(
            f"stale: newest safety result is for "
            f"{latest.get('classifier_version')!r}, code is {version!r}. "
            "Re-run evals/run_safety.py and commit the result."
        )
        return 1

    if latest["recall"] < 1.0 or latest["false_positive_rate"] >= 0.05:
        print(
            f"committed result does not pass: recall={latest['recall']}, "
            f"false positives={latest['false_positive_rate']}"
        )
        return 1

    print(f"safety result is current for {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
