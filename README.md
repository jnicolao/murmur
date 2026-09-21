# murmur

A space for your inner voice.

Murmur is a voice-first journal that runs entirely on your own machine. You talk, it listens, it answers out loud, and over weeks it shows you how you have been sounding. No accounts, no API keys, no audio or transcript ever leaves the device.

**Status:** Phase 2 done. You can talk to it, it remembers, and it knows when to stop being a journal. See [docs/DESIGN.md](docs/DESIGN.md) for scope, architecture, stack, safety, evals, and the phased plan.

| Measured on an M2 Pro, 16 GB | |
|---|---|
| Time to first audio, p50 | 1939 ms |
| Time to first audio, p95 | 2261 ms |
| Transcription, p50 | 372 ms |
| Crisis check, p50 | 337 ms |
| Crisis recall | 100% |
| False positives on ordinary distress | 0% (0/22) |

Numbers come from `make eval`, `make eval-asr` and `make eval-safety`, and every run is committed under `evals/results/`. The voice fixtures are synthesised speech, so the 0% word error rate says the test is easy, not that transcription is solved.

## Safety

Murmur is a journal, not therapy. Before a single token of reply is generated, every utterance goes through a two-stage crisis check: a curated phrase list, then a one-word call to the local model for indirect phrasing. If either fires, the reflective loop is bypassed entirely and a fixed, human-written message is spoken instead. That entry is marked and is never used as context for a later reply. Nothing is reported anywhere, because there is nowhere to report to.

The shipped resource list is an international helpline directory. Local numbers are deliberately not hardcoded: a wrong crisis number is worse than none, so they are set in `apps/api/resources.json` and have to be marked verified by a person.

## Running it

```
make setup        # venv, dependencies, and the Qwen3 model
make run          # postgres, then http://127.0.0.1:8000
make units        # fast checks, no model needed
make test         # drives the socket with fixtures: reply, barge-in, crisis
make eval-safety  # the crisis suites, the gate for Phase 2
```

Everything runs on your own machine. Nothing is sent anywhere.

## Stack

Every component is free and open source.

- Web: Next.js, TypeScript, Tailwind
- API: FastAPI over one WebSocket
- Speech to text: faster-whisper
- Reply: Qwen3 via Ollama
- Text to speech: Kokoro-82M
- Voice activity: Silero VAD
- Mood signals: wav2vec2 audio emotion model plus prosody, fused with the user's own check-ins
- Memory: bge-m3 embeddings in Postgres with pgvector
- Tracing: self-hosted Langfuse

## License

Apache-2.0. See [LICENSE](LICENSE).
