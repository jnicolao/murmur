"""How something was said, measured from the waveform alone.

No model and no extra transcription pass. Everything here comes from the
audio already in hand, which is what keeps it off the critical path.

Two measurements shaped the implementation:

- `librosa.pyin`, which the plan called for, takes about 37 seconds for a
  6.5 second clip. Its Viterbi decoding is not worth that. `librosa.yin`
  returns pitch for the same clip in 8 milliseconds, and pairing it with an
  energy-based voicing mask recovers the accuracy that pyin's voicing
  probabilities would have given.
- Word-level timestamps from faster-whisper cost about 40 milliseconds, and
  they sit in the critical path where roughly 60 milliseconds of headroom is
  left. Speech rate is derived from voiced duration instead, so transcription
  is untouched.
"""

from __future__ import annotations

from dataclasses import dataclass

import librosa
import numpy as np

# A speaking voice lives inside this range. Anything outside is an artefact.
F0_MIN_HZ = 65.0
F0_MAX_HZ = 400.0

FRAME = 1024
HOP = 256

# Voicing threshold relative to the loudest frame, so it survives whatever
# gain the microphone happens to be running at.
VOICING_RATIO = 0.08
SILENCE_FLOOR = 1e-4


@dataclass(frozen=True)
class Prosody:
    pitch_mean: float | None
    pitch_range: float | None
    speech_rate: float | None
    pause_ratio: float | None

    def as_row(self) -> dict:
        return {
            "pitch_mean": self.pitch_mean,
            "pitch_range": self.pitch_range,
            "speech_rate": self.speech_rate,
            "pause_ratio": self.pause_ratio,
        }


EMPTY = Prosody(None, None, None, None)


def extract(audio: np.ndarray, sample_rate: int, word_count: int) -> Prosody:
    """Pitch, pace and pausing for one utterance.

    Fields are None when the audio cannot support them, which is better than
    a confident zero: a silent clip has no pitch, not a pitch of nothing.
    """
    if audio.size < sample_rate // 4:
        return EMPTY

    rms = librosa.feature.rms(y=audio, frame_length=FRAME, hop_length=HOP)[0]
    if rms.size == 0 or not np.isfinite(rms).any():
        return EMPTY

    threshold = max(float(rms.max()) * VOICING_RATIO, SILENCE_FLOOR)
    voiced = rms > threshold
    if not voiced.any():
        return EMPTY

    # Leading and trailing silence is not a pause in what was said, so pausing
    # is measured only between the first and last voiced frame.
    first, last = int(np.argmax(voiced)), int(len(voiced) - np.argmax(voiced[::-1]))
    inside = voiced[first:last]
    pause_ratio = float(1.0 - inside.mean()) if inside.size else None

    seconds_per_frame = HOP / sample_rate
    voiced_seconds = float(voiced.sum()) * seconds_per_frame
    speech_rate = word_count / voiced_seconds if voiced_seconds > 0.2 and word_count else None

    f0 = librosa.yin(
        audio, fmin=F0_MIN_HZ, fmax=F0_MAX_HZ, sr=sample_rate, frame_length=FRAME, hop_length=HOP
    )
    usable = f0[: len(voiced)][voiced[: len(f0)]]
    usable = usable[np.isfinite(usable)]
    usable = usable[(usable >= F0_MIN_HZ) & (usable <= F0_MAX_HZ)]

    pitch_mean = pitch_range = None
    if usable.size >= 8:
        pitch_mean = float(np.median(usable))
        # Percentiles rather than min to max: yin drops the occasional octave
        # and a single bad frame should not define the range.
        low, high = np.percentile(usable, [10, 90])
        pitch_range = float(high - low)

    return Prosody(
        pitch_mean=_round(pitch_mean, 1),
        pitch_range=_round(pitch_range, 1),
        speech_rate=_round(speech_rate, 3),
        pause_ratio=_round(pause_ratio, 4),
    )


def _round(value: float | None, places: int) -> float | None:
    return None if value is None else round(value, places)
