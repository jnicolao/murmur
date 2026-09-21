"""The fixed crisis reply.

Written by a person, spoken verbatim, never generated. The text is short
because it is heard aloud by someone who is struggling, and it does not ask a
question, because this is the one moment Murmur should stop being a journal.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

CRISIS_MESSAGE = (
    "I heard you, and what you said matters too much for me to be the one "
    "holding it. Murmur is a journal. It cannot help with this, and you "
    "deserve a person. Please reach out to someone tonight. There are people "
    "trained for exactly this, and they are awake right now."
)

# Only an international directory ships by default. Local numbers are not
# hardcoded here on purpose: a wrong crisis number is worse than none, so they
# have to be set deliberately and verified by a human.
DEFAULT_RESOURCES = [
    {
        "label": "Find a helpline in your country",
        "detail": "findahelpline.com",
        "verified": True,
    }
]

CONFIG_PATH = Path(
    os.environ.get("MURMUR_RESOURCES", Path(__file__).resolve().parents[2] / "resources.json")
)


def resources() -> list[dict]:
    """Local resource list if one is configured, otherwise the directory."""
    if CONFIG_PATH.exists():
        entries = json.loads(CONFIG_PATH.read_text())
        verified = [e for e in entries if e.get("verified")]
        if verified:
            return verified + DEFAULT_RESOURCES
    return DEFAULT_RESOURCES
