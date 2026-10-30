"""Split the model's output into words to speak and a block to store.

The reply streams straight into speech synthesis, so the structured part has
to come last and must never leak into the audio. The model is asked to write
the spoken reply first, then a sentinel, then the affect block. This reads the
stream and keeps the two apart.

Everything here fails open. A missing or malformed affect block costs a point
on a chart; a raised exception would cost someone their reply.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass

SENTINEL = "<affect>"
MAX_LABELS = 2
LABEL_PATTERN = re.compile(r"^[a-z][a-z -]{1,23}$")


@dataclass(frozen=True)
class Affect:
    valence: float
    arousal: float
    labels: tuple[str, ...]

    def as_row(self) -> dict:
        return {
            "valence_text": self.valence,
            "arousal_text": self.arousal,
            "labels_text": list(self.labels),
        }


EMPTY_ROW = {"valence_text": None, "arousal_text": None, "labels_text": None}


class ReplyStream:
    """Yields the spoken part of a reply, then exposes the affect block."""

    def __init__(self, tokens: Iterable[str]) -> None:
        self._tokens = iter(tokens)
        self._tail = ""
        self.affect: Affect | None = None

    def spoken(self) -> Iterator[str]:
        """Text up to the sentinel. Everything after it is held back."""
        buffer = ""
        for token in self._tokens:
            buffer += token
            cut = buffer.find(SENTINEL)
            if cut != -1:
                if cut:
                    yield buffer[:cut]
                self._tail = buffer[cut + len(SENTINEL) :]
                self._tail += "".join(self._tokens)
                self.affect = parse(self._tail)
                return

            # The sentinel can arrive split across tokens, so hold back any
            # suffix that could still turn into one.
            keep = _pending_prefix(buffer)
            if keep < len(buffer):
                yield buffer[: len(buffer) - keep]
                buffer = buffer[len(buffer) - keep :]

        if buffer:
            yield buffer

    @property
    def raw_tail(self) -> str:
        return self._tail


def _pending_prefix(buffer: str) -> int:
    """Length of the trailing run that might still become the sentinel."""
    longest = min(len(buffer), len(SENTINEL) - 1)
    for size in range(longest, 0, -1):
        if SENTINEL.startswith(buffer[-size:]):
            return size
    return 0


def parse(tail: str) -> Affect | None:
    match = re.search(r"\{.*?\}", tail, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None

    valence = _bounded(data.get("valence"))
    arousal = _bounded(data.get("arousal"))
    if valence is None or arousal is None:
        return None

    labels = []
    raw_labels = data.get("labels")
    if isinstance(raw_labels, list):
        for item in raw_labels[:MAX_LABELS]:
            if isinstance(item, str) and LABEL_PATTERN.match(item.strip().lower()):
                labels.append(item.strip().lower())

    return Affect(valence=valence, arousal=arousal, labels=tuple(labels))


def _bounded(value: object) -> float | None:
    """A number in [-1, 1], or None. Out-of-range values are clamped rather
    than dropped: a model saying 1.4 means the top of the scale."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if not math.isfinite(number):
        return None
    return round(max(-1.0, min(1.0, number)), 3)
