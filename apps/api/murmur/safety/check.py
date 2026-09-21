"""Two-stage crisis check. Either stage firing triggers the crisis path."""

from __future__ import annotations

from dataclasses import dataclass

from murmur.llm.client import Ollama
from murmur.safety import phrases
from murmur.safety.classifier import CrisisClassifier


@dataclass(frozen=True)
class SafetyVerdict:
    triggered: bool
    stage: str | None = None  # "phrase" or "classifier"
    evidence: str | None = None


class SafetyCheck:
    def __init__(self, llm: Ollama | None = None) -> None:
        self.classifier = CrisisClassifier(llm)

    def run(self, transcript: str) -> SafetyVerdict:
        hit = phrases.matches(transcript)
        if hit:
            return SafetyVerdict(True, "phrase", hit)
        if self.classifier.flags(transcript):
            return SafetyVerdict(True, "classifier")
        return SafetyVerdict(False)
