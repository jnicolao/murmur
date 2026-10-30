"""Where transcription test clips come from.

Three sources, deliberately separate, because they answer different questions:

- **own**: recordings of the person who uses this. The only source that says
  how Murmur performs for them, in their room, with their accent. Built from
  entries the app has already stored, then hand-corrected. Never committed:
  it is somebody's voice saying real things.
- **librispeech**: read audiobook speech from strangers, CC BY 4.0. Real
  human audio, so unlike synthesised fixtures it can actually separate one
  model size from another. Downloaded on demand, never committed.
- **synthetic**: the original Kokoro fixtures. Kept only as a smoke test.
  Every model scores zero errors on them, which says the test is easy rather
  than that transcription works.

Nothing here lives in git. Audio is either somebody's voice or hundreds of
megabytes of someone else's, and neither belongs in a repository.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf

MURMUR_HOME = Path(os.environ.get("MURMUR_HOME", Path.home() / ".murmur"))
CORPORA = MURMUR_HOME / "corpora"
OWN_SET = Path(os.environ.get("MURMUR_EVALSET", MURMUR_HOME / "evalset"))
LIBRISPEECH = CORPORA / "LibriSpeech" / "dev-clean"

SAMPLE_RATE = 16_000
DOWNLOAD_HINT = (
    "Not found. Fetch it with:\n"
    "  mkdir -p ~/.murmur/corpora && cd ~/.murmur/corpora\n"
    "  curl -O https://www.openslr.org/resources/12/dev-clean.tar.gz\n"
    "  tar xzf dev-clean.tar.gz"
)


@dataclass(frozen=True)
class Clip:
    clip_id: str
    path: Path
    truth: str
    source: str


def load_audio(path: Path) -> np.ndarray:
    """Mono float32 at 16 kHz, whatever the file started as."""
    audio, rate = sf.read(path, dtype="float32")
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    if rate != SAMPLE_RATE:
        n = round(len(audio) * SAMPLE_RATE / rate)
        audio = np.interp(
            np.linspace(0, len(audio), n, endpoint=False), np.arange(len(audio)), audio
        ).astype(np.float32)
    return audio


def librispeech_clips(limit: int = 100) -> list[Clip]:
    """A deterministic slice of dev-clean, spread across speakers.

    Taking the first N would mean a handful of voices. One clip per speaker
    per pass, cycling, gives a spread without randomness.
    """
    if not LIBRISPEECH.is_dir():
        return []

    by_speaker: dict[str, list[Clip]] = {}
    for transcript_file in sorted(LIBRISPEECH.rglob("*.trans.txt")):
        speaker = transcript_file.parent.parent.name
        for line in transcript_file.read_text().splitlines():
            clip_id, _, truth = line.partition(" ")
            audio_path = transcript_file.parent / f"{clip_id}.flac"
            if truth and audio_path.exists():
                by_speaker.setdefault(speaker, []).append(
                    Clip(clip_id, audio_path, truth.strip(), "librispeech")
                )

    speakers = sorted(by_speaker)
    chosen: list[Clip] = []
    depth = 0
    while len(chosen) < limit and speakers:
        progressed = False
        for speaker in speakers:
            clips = by_speaker[speaker]
            if depth < len(clips):
                chosen.append(clips[depth])
                progressed = True
                if len(chosen) == limit:
                    return chosen
        if not progressed:
            break
        depth += 1
    return chosen


def own_clips() -> list[Clip]:
    """The owner's own recordings, exported from the app and hand-corrected.

    Only entries marked corrected are used. An uncorrected transcript is
    whatever the model guessed, and scoring a model against its own output
    would report a perfect result every time.
    """
    manifest = OWN_SET / "manifest.json"
    if not manifest.exists():
        return []

    clips = []
    for row in json.loads(manifest.read_text())["clips"]:
        if not row.get("corrected"):
            continue
        path = Path(row["audio"])
        if not path.is_absolute():
            path = OWN_SET / path
        if path.exists() and row.get("truth", "").strip():
            clips.append(Clip(row["id"], path, row["truth"].strip(), "own"))
    return clips


def synthetic_clips() -> list[Clip]:
    """The original Kokoro fixtures, regenerated if missing."""
    from run_latency import FIXTURES, UTTERANCES, build_fixtures

    from murmur.audio.tts import Speaker

    if not FIXTURES.is_dir() or not any(FIXTURES.glob("*.wav")):
        build_fixtures(Speaker())
    return [
        Clip(path.stem, path, truth, "synthetic")
        for path, truth in zip(sorted(FIXTURES.glob("*.wav")), UTTERANCES, strict=False)
    ]


def available(limit: int = 100) -> dict[str, list[Clip]]:
    """Every source that has clips on this machine right now."""
    sources = {
        "own": own_clips(),
        "librispeech": librispeech_clips(limit),
        "synthetic": synthetic_clips(),
    }
    return {name: clips for name, clips in sources.items() if clips}
