"""Fail CI when a committed result predates the wording it claims to measure.

Two prompts drive behaviour here: the crisis classifier and the reflective
reply. Either can be edited without touching a line of logic, and a stale
result would then describe a system that no longer runs. This is the check
that stops that shipping.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLASSIFIER = ROOT / "apps" / "api" / "murmur" / "safety" / "classifier.py"
PROMPTS = ROOT / "apps" / "api" / "murmur" / "llm" / "prompts.py"
RESULTS = ROOT / "evals" / "results"


def version_in(path: Path, name: str) -> str:
    match = re.search(rf'{name} = "([^"]+)"', path.read_text())
    if not match:
        sys.exit(f"could not read {name} from {path.name}")
    return match.group(1)


def newest(pattern: str) -> dict | None:
    results = sorted(RESULTS.glob(pattern))
    return json.loads(results[-1].read_text()) if results else None


def check_safety() -> bool:
    version = version_in(CLASSIFIER, "CLASSIFIER_VERSION")
    latest = newest("safety-*.json")
    if latest is None:
        print("no committed safety result; run evals/run_safety.py")
        return False
    if latest.get("classifier_version") != version:
        print(
            f"stale safety result: committed for "
            f"{latest.get('classifier_version')!r}, code is {version!r}. "
            "Re-run evals/run_safety.py and commit the result."
        )
        return False
    if latest["recall"] < 1.0 or latest["false_positive_rate"] >= 0.05:
        print(
            f"committed safety result does not pass: recall={latest['recall']}, "
            f"false positives={latest['false_positive_rate']}"
        )
        return False
    print(f"safety result is current for {version}")
    return True


def check_replies() -> bool:
    version = version_in(PROMPTS, "PROMPT_VERSION")
    latest = newest(f"replies-{version}-*.json")
    if latest is None:
        print(
            f"no committed reply result for prompt {version!r}. "
            "Re-run evals/run_replies.py and commit the result."
        )
        return False
    print(
        f"reply result is current for {version} "
        f"({latest['clean_rate']:.0%} clean, {latest['cases']} replies)"
    )
    return True


def main() -> int:
    return 0 if all([check_safety(), check_replies()]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
