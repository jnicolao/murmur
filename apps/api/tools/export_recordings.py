"""Turn your own entries into a transcription test set.

Every utterance Murmur hears is already stored with its audio, so the test
set does not need recording separately. It needs correcting: the stored
transcript is what the model guessed, and scoring a model against its own
guess reports a perfect result every time.

    apps/api/.venv/bin/python apps/api/tools/export_recordings.py
    # then edit ~/.murmur/evalset/manifest.json, fixing each transcript
    # and setting "corrected": true on the ones you have checked
    make eval-asr

The export lands outside the repository and stays there. It is your voice
saying real things, and it is not something to commit.

Entries that reached the crisis path are skipped. They are held apart from
everything that looks backwards, and a test set is exactly that.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from murmur.store.db import Store  # noqa: E402

OUT = Path.home() / ".murmur" / "evalset"
MANIFEST = OUT / "manifest.json"


def existing() -> dict[str, dict]:
    if not MANIFEST.exists():
        return {}
    return {row["id"]: row for row in json.loads(MANIFEST.read_text())["clips"]}


def main() -> int:
    store = Store()
    rows = store.connection.execute(
        """
        SELECT u.id, u.audio_path, u.transcript
        FROM recallable_utterances u
        WHERE u.audio_path IS NOT NULL
        ORDER BY u.id
        """
    ).fetchall()

    if not rows:
        print(
            "No recordings to export yet.\n"
            "Murmur keeps audio for every entry, so this fills up as you use it. "
            "If MURMUR_KEEP_AUDIO is set to 0, nothing is kept and this will stay empty."
        )
        return 1

    (OUT / "audio").mkdir(parents=True, exist_ok=True)
    known = existing()
    added = 0

    for row in rows:
        clip_id = f"own-{row['id']:06d}"
        source = Path(row["audio_path"])
        if not source.exists():
            continue

        destination = OUT / "audio" / f"{clip_id}{source.suffix}"
        if not destination.exists():
            shutil.copy2(source, destination)

        if clip_id in known:
            continue  # never overwrite a transcript somebody has corrected

        known[clip_id] = {
            "id": clip_id,
            "audio": f"audio/{destination.name}",
            # What the model heard. Fix it, then set corrected to true.
            "truth": row["transcript"],
            "corrected": False,
        }
        added += 1

    clips = [known[key] for key in sorted(known)]
    MANIFEST.write_text(
        json.dumps(
            {
                "note": (
                    "Correct each transcript to what was actually said, then set "
                    "corrected to true. Only corrected clips are scored."
                ),
                "clips": clips,
            },
            indent=2,
        )
        + "\n"
    )

    ready = sum(1 for clip in clips if clip["corrected"])
    print(f"{len(clips)} clips in {MANIFEST}")
    print(f"  {added} newly exported, {ready} corrected and ready to score")
    if ready < len(clips):
        print("\nCorrect the rest, set corrected to true on each, then run: make eval-asr")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
