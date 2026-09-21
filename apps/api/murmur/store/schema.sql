-- Murmur, Phase 2. Affect columns arrive with Phase 3 and embeddings with
-- Phase 4; this is only what the voice loop and the crisis path need.

CREATE TABLE IF NOT EXISTS entries (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    started_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at    TIMESTAMPTZ,
    self_mood   SMALLINT CHECK (self_mood BETWEEN 1 AND 5),
    summary     TEXT,
    deleted_at  TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS utterances (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    entry_id    BIGINT NOT NULL REFERENCES entries(id) ON DELETE CASCADE,
    seq         INTEGER NOT NULL,
    audio_path  TEXT,
    transcript  TEXT NOT NULL,
    asr_ms      INTEGER,
    ttfa_ms     INTEGER,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (entry_id, seq)
);

CREATE TABLE IF NOT EXISTS replies (
    id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    utterance_id     BIGINT NOT NULL REFERENCES utterances(id) ON DELETE CASCADE,
    text             TEXT NOT NULL,
    safety_triggered BOOLEAN NOT NULL DEFAULT FALSE,
    safety_stage     TEXT,
    model            TEXT,
    prompt_version   TEXT,
    latency_ms       INTEGER,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Entries that tripped the crisis path are never used as context for a later
-- reply. Phase 4 retrieval joins against this view, not the raw table.
CREATE OR REPLACE VIEW recallable_utterances AS
SELECT u.*
FROM utterances u
JOIN entries e ON e.id = u.entry_id
WHERE e.deleted_at IS NULL
  AND NOT EXISTS (
      SELECT 1 FROM replies r
      WHERE r.utterance_id = u.id AND r.safety_triggered
  );

CREATE INDEX IF NOT EXISTS utterances_entry_idx ON utterances(entry_id, seq);
CREATE INDEX IF NOT EXISTS entries_started_idx ON entries(started_at DESC);
