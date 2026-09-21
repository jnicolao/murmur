"""Checks that need no model, so a hosted runner can gate on them."""

from __future__ import annotations

import json
from pathlib import Path

from murmur.audio.sentences import stream_sentences
from murmur.safety import phrases

SUITES = Path(__file__).resolve().parents[3] / "evals" / "datasets" / "safety"


def cases(name: str) -> list[dict]:
    return json.loads((SUITES / f"{name}.json").read_text())["cases"]


def test_phrase_list_catches_direct_crisis():
    direct = [c for c in cases("crisis") if c["kind"] == "direct"]
    missed = [c["text"] for c in direct if phrases.matches(c["text"]) is None]
    assert not missed, f"phrase list missed direct crisis: {missed}"


def test_phrase_list_ignores_idioms():
    idioms = [c for c in cases("ordinary") if c["kind"] == "idiom"]
    flagged = [c["text"] for c in idioms if phrases.matches(c["text"])]
    assert not flagged, f"idiom flagged as crisis: {flagged}"


def test_phrase_list_ignores_ordinary_distress():
    ordinary = [c for c in cases("ordinary") if c["kind"] != "idiom"]
    flagged = [c["text"] for c in ordinary if phrases.matches(c["text"])]
    assert not flagged, f"ordinary distress flagged as crisis: {flagged}"


def test_splitter_does_not_break_decimals():
    assert list(stream_sentences(["I slept 6", ".5 hours", ". It helped", " a lot."])) == [
        "I slept 6.5 hours.",
        "It helped a lot.",
    ]


def test_splitter_cuts_long_runs_at_a_clause():
    long_run = (
        "It sounds like that conversation has been taking up a lot of room in "
        "your head, and that it left you unsettled."
    )
    units = list(stream_sentences([long_run]))
    assert len(units) == 2
    assert units[0].endswith(",")


def test_splitter_keeps_short_sentences_whole():
    assert list(stream_sentences(["You finished it.", " That matters."])) == [
        "You finished it.",
        "That matters.",
    ]
