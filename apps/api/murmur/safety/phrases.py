"""Stage one of the crisis check: a curated list of unambiguous phrasings.

This runs in microseconds and catches direct statements. It is deliberately
narrow. Everything it misses is the classifier's job, and the idiom list below
exists because English is full of violent figures of speech that have nothing
to do with crisis.
"""

from __future__ import annotations

import re

# Each pattern must be unambiguous on its own. If a phrase needs context to be
# alarming, it belongs to the classifier, not here.
CRISIS_PATTERNS: tuple[str, ...] = (
    r"\bkill(?:ing)?\s+(?:my\s?self|myself)\b",
    r"\bend(?:ing)?\s+(?:my|it)\s+(?:life|all)\b",
    r"\btake\s+my\s+own\s+life\b",
    r"\bsuicid(?:e|al)\b",
    r"\b(?:want|wanted|wanting)\s+to\s+die\b",
    r"\bwish\s+(?:i\s+(?:was|were)\s+dead|i\s+could\s+die)\b",
    r"\b(?:better|best)\s+off\s+(?:dead|without\s+me)\b",
    r"\b(?:hurt(?:ing)?|harm(?:ing)?|cut(?:ting)?)\s+(?:my\s?self|myself)\b",
    r"\bno\s+(?:reason|point)\s+(?:to|in)\s+(?:live|living|being here)\b",
    r"\bnothing\s+(?:left\s+)?to\s+live\s+for\b",
    r"\bdon'?t\s+want\s+to\s+(?:be\s+here|wake\s+up|exist)\b",
    r"\bdon'?t\s+want\s+to\s+live\b",
    r"\bcan'?t\s+(?:do|go\s+on|keep\s+going)\b.{0,20}\banymore\b",
    r"\boverdose\b|\bod\s+on\b",
    r"\bend\s+the\s+pain\b",
)

# Figures of speech that contain alarming words but are not crisis. These are
# checked first and, when one covers the whole match, the hit is dropped.
IDIOMS: tuple[str, ...] = (
    r"\b(?:this|it|work|the heat|my boss|that commute)\s+is\s+killing\s+me\b",
    r"\b(?:i'?m|i am)\s+dying\s+to\b",
    r"\b(?:i|we)\s+could\s+kill\s+for\b",
    r"\bkilled\s+it\b",
    r"\bdead\s+tired\b",
    r"\bmy\s+(?:phone|laptop|battery|car)\s+died\b",
    r"\bdeadline\b",
)

_CRISIS = [re.compile(p, re.IGNORECASE) for p in CRISIS_PATTERNS]
_IDIOMS = [re.compile(p, re.IGNORECASE) for p in IDIOMS]


def matches(text: str) -> str | None:
    """Return the matched phrase, or None. Idioms win over crisis patterns."""
    idiom_spans = [m.span() for pattern in _IDIOMS for m in pattern.finditer(text)]
    for pattern in _CRISIS:
        for hit in pattern.finditer(text):
            start, end = hit.span()
            inside_idiom = any(s <= start and end <= e for s, e in idiom_spans)
            if not inside_idiom:
                return hit.group(0)
    return None
