-- How each utterance sounded, independent of what it said. Nullable because
-- a clip can be too short or too quiet to support any of these.
ALTER TABLE utterances ADD COLUMN IF NOT EXISTS pitch_mean   REAL;
ALTER TABLE utterances ADD COLUMN IF NOT EXISTS pitch_range  REAL;
ALTER TABLE utterances ADD COLUMN IF NOT EXISTS speech_rate  REAL;
ALTER TABLE utterances ADD COLUMN IF NOT EXISTS pause_ratio  REAL;
