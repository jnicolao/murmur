"""Speech to text via faster-whisper. Runs locally on CPU."""

from __future__ import annotations

import os

import numpy as np
from faster_whisper import WhisperModel

SAMPLE_RATE = 16_000
# base.en is the default: on clean speech it matched small.en exactly while
# running three times faster. Revisit once real recordings exist.
DEFAULT_MODEL = os.environ.get("MURMUR_ASR_MODEL", "base.en")


class Transcriber:
    def __init__(self, model_size: str = DEFAULT_MODEL, compute_type: str = "int8") -> None:
        self.model = WhisperModel(model_size, device="cpu", compute_type=compute_type)

    def transcribe(self, audio: np.ndarray) -> str:
        """audio: float32 mono at 16 kHz, range [-1, 1]."""
        segments, _ = self.model.transcribe(
            audio,
            language="en",
            beam_size=1,
            vad_filter=False,
            condition_on_previous_text=False,
        )
        return "".join(segment.text for segment in segments).strip()
