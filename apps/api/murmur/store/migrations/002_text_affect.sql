-- Valence, arousal and labels for what was said, returned by the reflective
-- model alongside the reply. Nullable: the model may omit or malform the
-- block, and a missing reading must never cost someone their entry.
ALTER TABLE utterances ADD COLUMN IF NOT EXISTS valence_text REAL;
ALTER TABLE utterances ADD COLUMN IF NOT EXISTS arousal_text REAL;
ALTER TABLE utterances ADD COLUMN IF NOT EXISTS labels_text  TEXT[];
