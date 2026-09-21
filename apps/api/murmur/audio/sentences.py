"""Split a token stream into speech units as soon as each one is complete.

Kokoro synthesises a whole unit before returning any audio, so a long first
sentence delays the first sound by over a second. Time-to-first-audio is what
the person actually feels, so a long run is cut at a clause boundary instead
of waiting for the full stop. Later units keep arriving while the first plays.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator

SENTENCE_END = ".!?"
CLAUSE_END = ",;:"
# Below this a cut would produce a clipped-sounding fragment.
MIN_CHARS = 12
# Past this, a clause boundary is worth taking rather than waiting for a stop.
CLAUSE_AFTER = 60


def stream_sentences(tokens: Iterable[str]) -> Iterator[str]:
    """Yield speech units from a stream of model tokens."""
    buffer = ""
    for token in tokens:
        buffer += token
        while True:
            cut = _find_cut(buffer)
            if cut is None:
                break
            unit, buffer = buffer[:cut].strip(), buffer[cut:]
            if unit:
                yield unit
    tail = buffer.strip()
    if tail:
        yield tail


def _find_cut(buffer: str) -> int | None:
    """Index just past a boundary worth cutting at, or None to keep buffering."""
    for i, char in enumerate(buffer):
        if i + 1 < MIN_CHARS:
            continue
        is_sentence = char in SENTENCE_END
        is_clause = char in CLAUSE_END and i + 1 >= CLAUSE_AFTER
        if not (is_sentence or is_clause):
            continue
        if i + 1 == len(buffer):
            # The terminator is the last thing we have. More text may follow
            # and change its meaning (a decimal point, an abbreviation), so
            # wait for the next token.
            return None
        if buffer[i + 1] in " \n":
            return i + 1
    return None
