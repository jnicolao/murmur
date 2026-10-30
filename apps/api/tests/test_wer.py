"""Word error rate and corpus selection. No model and no audio, so this runs in CI."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "evals"))

from corpus import own_clips
from run_asr import normalise, wer


def test_identical_text_has_no_errors():
    assert wer("I had a long day", "I had a long day") == 0.0


def test_punctuation_and_case_are_not_errors():
    # The transcriber punctuates, LibriSpeech transcripts do not. Neither is wrong.
    assert wer("I HAD A LONG DAY", "I had a long day.") == 0.0


def test_one_wrong_word_in_four_is_a_quarter():
    assert wer("I had a day", "I had the day") == 0.25


def test_a_dropped_word_counts():
    assert wer("I had a long day", "I had a day") == 0.2


def test_an_inserted_word_counts():
    assert round(wer("I had a day", "I had a long day"), 4) == 0.25


def test_an_empty_reference_cannot_be_wrong():
    assert wer("", "anything at all") == 0.0


def test_hearing_nothing_is_total_error():
    assert wer("I had a long day", "") == 1.0


def test_normalise_keeps_apostrophes_but_drops_the_rest():
    assert normalise("Don't — really, I'm fine!") == ["don't", "really", "i'm", "fine"]


def test_uncorrected_clips_are_never_scored(tmp_path, monkeypatch):
    """Scoring a model against its own guess would report a perfect result."""
    import corpus

    evalset = tmp_path / "evalset"
    (evalset / "audio").mkdir(parents=True)
    (evalset / "audio" / "a.opus").write_bytes(b"")
    (evalset / "audio" / "b.opus").write_bytes(b"")
    (evalset / "manifest.json").write_text(
        json.dumps(
            {
                "clips": [
                    {"id": "a", "audio": "audio/a.opus", "truth": "checked", "corrected": True},
                    {"id": "b", "audio": "audio/b.opus", "truth": "guessed", "corrected": False},
                ]
            }
        )
    )
    monkeypatch.setattr(corpus, "OWN_SET", evalset)
    clips = own_clips()
    assert [clip.clip_id for clip in clips] == ["a"]


def test_no_manifest_means_no_clips_rather_than_an_error(tmp_path, monkeypatch):
    import corpus

    monkeypatch.setattr(corpus, "OWN_SET", tmp_path / "nothing")
    assert own_clips() == []


def build_fake_librispeech(root: Path, speakers: int, per_speaker: int) -> None:
    """The layout LibriSpeech ships: speaker/chapter/<id>.flac plus a .trans.txt."""
    for speaker in range(1, speakers + 1):
        chapter = root / str(speaker) / "100"
        chapter.mkdir(parents=True)
        lines = []
        for index in range(per_speaker):
            clip_id = f"{speaker}-100-{index:04d}"
            (chapter / f"{clip_id}.flac").write_bytes(b"")
            lines.append(f"{clip_id} SPEAKER {speaker} UTTERANCE {index}")
        (chapter / f"{speaker}-100.trans.txt").write_text("\n".join(lines))


def test_corpus_selection_spreads_across_speakers(tmp_path, monkeypatch):
    """Taking the first N clips would mean a handful of voices."""
    import corpus

    build_fake_librispeech(tmp_path, speakers=10, per_speaker=20)
    monkeypatch.setattr(corpus, "LIBRISPEECH", tmp_path)

    clips = corpus.librispeech_clips(limit=10)
    speakers = {clip.path.parent.parent.name for clip in clips}
    assert len(clips) == 10
    assert len(speakers) == 10, "ten clips should come from ten different speakers"


def test_corpus_selection_stops_at_what_exists(tmp_path, monkeypatch):
    import corpus

    build_fake_librispeech(tmp_path, speakers=2, per_speaker=3)
    monkeypatch.setattr(corpus, "LIBRISPEECH", tmp_path)
    assert len(corpus.librispeech_clips(limit=50)) == 6


def test_a_missing_corpus_is_not_an_error(tmp_path, monkeypatch):
    import corpus

    monkeypatch.setattr(corpus, "LIBRISPEECH", tmp_path / "absent")
    assert corpus.librispeech_clips() == []


def test_transcripts_are_read_with_their_text_intact(tmp_path, monkeypatch):
    import corpus

    build_fake_librispeech(tmp_path, speakers=1, per_speaker=1)
    monkeypatch.setattr(corpus, "LIBRISPEECH", tmp_path)
    clip = corpus.librispeech_clips(limit=1)[0]
    assert clip.truth == "SPEAKER 1 UTTERANCE 0"
    assert clip.source == "librispeech"
