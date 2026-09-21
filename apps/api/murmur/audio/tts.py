"""Text to speech via Kokoro-82M. Synthesises one sentence at a time so the
first sentence can start playing while the model is still writing the rest."""

from __future__ import annotations

import numpy as np

SAMPLE_RATE = 24_000
DEFAULT_VOICE = "af_heart"


class Speaker:
    def __init__(self, voice: str = DEFAULT_VOICE) -> None:
        from kokoro import KPipeline

        self.voice = voice
        self.pipeline = KPipeline(lang_code="a")

    def say(self, text: str) -> np.ndarray:
        """Return float32 mono audio at 24 kHz for one sentence."""
        chunks = [audio for _, _, audio in self.pipeline(text, voice=self.voice)]
        if not chunks:
            return np.zeros(0, dtype=np.float32)
        return np.concatenate([np.asarray(c, dtype=np.float32) for c in chunks])
