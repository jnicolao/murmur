"""Prosody checks. Synthetic tones, so these need no model and run in CI."""

from __future__ import annotations

import numpy as np

from murmur.affect.prosody import extract

RATE = 16_000


def tone(hz: float, seconds: float, amplitude: float = 0.3) -> np.ndarray:
    t = np.arange(int(RATE * seconds)) / RATE
    # A couple of harmonics, because pitch trackers key on a periodic waveform
    # rather than a pure sinusoid.
    wave = np.sin(2 * np.pi * hz * t) + 0.5 * np.sin(4 * np.pi * hz * t)
    return (amplitude * wave / np.abs(wave).max()).astype(np.float32)


def silence(seconds: float) -> np.ndarray:
    return np.zeros(int(RATE * seconds), dtype=np.float32)


def test_pitch_is_found_and_close_to_the_tone():
    result = extract(tone(180, 2.0), RATE, word_count=6)
    assert result.pitch_mean is not None
    assert 160 < result.pitch_mean < 200


def test_a_steady_tone_has_a_narrow_pitch_range():
    result = extract(tone(180, 2.0), RATE, word_count=6)
    assert result.pitch_range is not None
    assert result.pitch_range < 30


def test_silence_yields_nothing_rather_than_zero():
    result = extract(silence(2.0), RATE, word_count=0)
    assert result == extract(silence(2.0), RATE, word_count=0)
    assert result.pitch_mean is None
    assert result.pause_ratio is None
    assert result.speech_rate is None


def test_a_clip_too_short_to_measure_yields_nothing():
    assert extract(tone(180, 0.1), RATE, word_count=1).pitch_mean is None


def test_a_gap_in_the_middle_raises_the_pause_ratio():
    continuous = extract(tone(180, 2.0), RATE, word_count=6)
    broken = extract(
        np.concatenate([tone(180, 0.8), silence(0.8), tone(180, 0.8)]), RATE, word_count=6
    )
    assert broken.pause_ratio > continuous.pause_ratio


def test_leading_silence_is_not_counted_as_a_pause():
    plain = extract(tone(180, 1.5), RATE, word_count=5)
    padded = extract(np.concatenate([silence(1.0), tone(180, 1.5)]), RATE, word_count=5)
    assert abs(padded.pause_ratio - plain.pause_ratio) < 0.05


def test_more_words_in_the_same_audio_means_a_faster_rate():
    slow = extract(tone(180, 2.0), RATE, word_count=4)
    fast = extract(tone(180, 2.0), RATE, word_count=12)
    assert fast.speech_rate > slow.speech_rate


def test_values_are_json_serialisable_for_the_database():
    import json

    row = extract(tone(180, 2.0), RATE, word_count=6).as_row()
    assert set(row) == {"pitch_mean", "pitch_range", "speech_rate", "pause_ratio"}
    json.dumps(row)
