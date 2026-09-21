"""Storage for entries, utterances and replies.

Everything is local. The audio sits on disk beside the database and both are
wiped by the same call, because a delete that leaves the recordings behind is
not a delete.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import numpy as np
import psycopg
import soundfile as sf
from psycopg.rows import dict_row

DSN = os.environ.get("MURMUR_DSN", "postgresql://murmur:murmur@127.0.0.1:5433/murmur")
AUDIO_ROOT = Path(os.environ.get("MURMUR_AUDIO", Path.home() / ".murmur" / "audio"))
# Keeping audio lets a better model re-score it later. Turn it off and only
# the transcript survives the turn.
KEEP_AUDIO = os.environ.get("MURMUR_KEEP_AUDIO", "1") != "0"

SCHEMA = Path(__file__).resolve().parent / "schema.sql"


class Store:
    def __init__(self, dsn: str = DSN) -> None:
        self.dsn = dsn
        self.connection = psycopg.connect(dsn, autocommit=True, row_factory=dict_row)
        self.connection.execute(SCHEMA.read_text())

    def close(self) -> None:
        self.connection.close()

    # entries ---------------------------------------------------------------

    def start_entry(self) -> int:
        row = self.connection.execute("INSERT INTO entries DEFAULT VALUES RETURNING id").fetchone()
        return row["id"]

    def end_entry(self, entry_id: int, summary: str | None = None) -> None:
        self.connection.execute(
            "UPDATE entries SET ended_at = now(), summary = COALESCE(%s, summary) WHERE id = %s",
            (summary, entry_id),
        )

    def set_mood(self, entry_id: int, mood: int) -> None:
        self.connection.execute("UPDATE entries SET self_mood = %s WHERE id = %s", (mood, entry_id))

    def entries(self, limit: int = 50) -> list[dict]:
        return self.connection.execute(
            """
            SELECT e.id, e.started_at, e.self_mood, e.summary,
                   count(u.id) AS utterances,
                   bool_or(r.safety_triggered) AS safety_triggered,
                   min(u.transcript) FILTER (WHERE u.seq = 1) AS opening
            FROM entries e
            LEFT JOIN utterances u ON u.entry_id = e.id
            LEFT JOIN replies r ON r.utterance_id = u.id
            WHERE e.deleted_at IS NULL
            GROUP BY e.id
            HAVING count(u.id) > 0
            ORDER BY e.started_at DESC
            LIMIT %s
            """,
            (limit,),
        ).fetchall()

    # one turn --------------------------------------------------------------

    def add_utterance(
        self,
        entry_id: int,
        transcript: str,
        audio: np.ndarray | None,
        sample_rate: int,
        asr_ms: int | None = None,
        ttfa_ms: int | None = None,
    ) -> int:
        seq = self.connection.execute(
            "SELECT coalesce(max(seq), 0) + 1 AS next FROM utterances WHERE entry_id = %s",
            (entry_id,),
        ).fetchone()["next"]

        audio_path = None
        if KEEP_AUDIO and audio is not None and audio.size:
            folder = AUDIO_ROOT / f"entry-{entry_id:06d}"
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / f"{seq:03d}.opus"
            sf.write(path, audio, sample_rate, format="OGG", subtype="OPUS")
            audio_path = str(path)

        row = self.connection.execute(
            "INSERT INTO utterances (entry_id, seq, audio_path, transcript, asr_ms, ttfa_ms) "
            "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
            (entry_id, seq, audio_path, transcript, asr_ms, ttfa_ms),
        ).fetchone()
        return row["id"]

    def add_reply(
        self,
        utterance_id: int,
        text: str,
        *,
        safety_triggered: bool = False,
        safety_stage: str | None = None,
        model: str | None = None,
        prompt_version: str | None = None,
        latency_ms: int | None = None,
    ) -> int:
        row = self.connection.execute(
            "INSERT INTO replies (utterance_id, text, safety_triggered, safety_stage, "
            "model, prompt_version, latency_ms) VALUES (%s, %s, %s, %s, %s, %s, %s) "
            "RETURNING id",
            (
                utterance_id,
                text,
                safety_triggered,
                safety_stage,
                model,
                prompt_version,
                latency_ms,
            ),
        ).fetchone()
        return row["id"]

    def set_ttfa(self, utterance_id: int, ttfa_ms: int) -> None:
        self.connection.execute(
            "UPDATE utterances SET ttfa_ms = %s WHERE id = %s", (ttfa_ms, utterance_id)
        )

    def transcript_of(self, entry_id: int) -> list[dict]:
        return self.connection.execute(
            """
            SELECT u.seq, u.transcript, u.ttfa_ms,
                   r.text AS reply, r.safety_triggered
            FROM utterances u
            LEFT JOIN replies r ON r.utterance_id = u.id
            WHERE u.entry_id = %s
            ORDER BY u.seq
            """,
            (entry_id,),
        ).fetchall()

    # deletion --------------------------------------------------------------

    def delete_entry(self, entry_id: int) -> None:
        """Remove the rows and the recordings together."""
        self.connection.execute("DELETE FROM entries WHERE id = %s", (entry_id,))
        shutil.rmtree(AUDIO_ROOT / f"entry-{entry_id:06d}", ignore_errors=True)

    def forget_everything(self) -> None:
        """Wipe every entry and every recording. There is no undo."""
        self.connection.execute("TRUNCATE entries RESTART IDENTITY CASCADE")
        if AUDIO_ROOT.exists():
            shutil.rmtree(AUDIO_ROOT, ignore_errors=True)
