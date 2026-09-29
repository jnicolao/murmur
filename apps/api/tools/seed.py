"""Fill the database with invented entries so the timeline can be worked on.

The chart needs weeks of history before it shows anything, and waiting weeks
to style a line is silly. This writes obviously fake entries with no audio.

    apps/api/.venv/bin/python apps/api/tools/seed.py 21
    apps/api/.venv/bin/python apps/api/tools/seed.py --clear

Never run this against a database holding real entries. It says so when you
do, and asks first.
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from murmur.store.db import Store  # noqa: E402

SEED_MARKER = "[seeded]"

OPENINGS = [
    "Work was heavy again today and I kept going over the same conversation.",
    "Quiet day. Not much happened and that was fine.",
    "I slept badly and everything has felt like wading through something.",
    "Good morning, actually. I got out for a walk before anything else started.",
    "I was short with someone I care about and I have been sitting with it.",
    "Nothing in particular is wrong, I just feel a long way from myself.",
    "I finished something I had been avoiding and the relief was bigger than the task.",
    "Long call with my mother. Half comfort, half the usual.",
]


def seed(store: Store, days: int) -> int:
    """A gentle dip in the middle and a recovery, so a trend is visible."""
    random.seed(7)
    made = 0

    for day_offset in range(days, 0, -1):
        if random.random() < 0.2:
            continue  # not every day has an entry

        # A slow arc rather than noise, so the two lines have something to agree on.
        position = (days - day_offset) / max(days - 1, 1)
        arc = -1.0 + 2.0 * abs(position - 0.5) * 2
        mood = max(1, min(5, round(3.1 + arc * 1.1 + random.uniform(-0.4, 0.4))))
        valence = max(-1.0, min(1.0, arc * 0.45 + random.uniform(-0.12, 0.12)))

        entry_id = store.start_entry()
        store.connection.execute(
            "UPDATE entries SET started_at = now() - make_interval(days => %s), "
            "ended_at = now() - make_interval(days => %s), self_mood = %s, summary = %s "
            "WHERE id = %s",
            (day_offset, day_offset, mood, f"{SEED_MARKER} day -{day_offset}", entry_id),
        )

        for seq in range(1, random.randint(2, 4)):
            utterance_id = store.add_utterance(
                entry_id, f"{SEED_MARKER} {random.choice(OPENINGS)}", None, 16_000
            )
            store.connection.execute(
                "UPDATE utterances SET created_at = now() - make_interval(days => %s), "
                "valence_text = %s, arousal_text = %s, pitch_mean = %s, speech_rate = %s "
                "WHERE id = %s",
                (
                    day_offset,
                    round(valence + random.uniform(-0.08, 0.08), 3),
                    round(random.uniform(-0.3, 0.3), 3),
                    round(random.uniform(120, 220), 1),
                    round(random.uniform(2.4, 4.2), 3),
                    utterance_id,
                ),
            )
            store.add_reply(utterance_id, f"{SEED_MARKER} reflective reply", model="seed")
            made += 1

    return made


def real_entries(store: Store) -> int:
    return store.connection.execute(
        "SELECT count(*) AS n FROM entries WHERE summary IS NULL OR summary NOT LIKE %s",
        (f"{SEED_MARKER}%",),
    ).fetchone()["n"]


def clear(store: Store) -> int:
    removed = store.connection.execute(
        "DELETE FROM entries WHERE summary LIKE %s RETURNING id", (f"{SEED_MARKER}%",)
    ).fetchall()
    return len(removed)


def main() -> int:
    store = Store()

    if "--clear" in sys.argv:
        print(f"removed {clear(store)} seeded entries")
        return 0

    days = int(next((a for a in sys.argv[1:] if a.isdigit()), 21))

    existing = real_entries(store)
    if existing and "--force" not in sys.argv:
        print(
            f"There are {existing} entries here that this script did not write. "
            "Seeding would mix invented data into them.\n"
            "Re-run with --force if you are sure, or --clear to remove seeded rows."
        )
        return 1

    print(f"wrote {seed(store, days)} seeded utterances across {days} days")
    print("remove them with: apps/api/.venv/bin/python apps/api/tools/seed.py --clear")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
