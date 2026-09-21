# murmur

A space for your inner voice.

Murmur is a voice-first journal that runs entirely on your own machine. You talk, it listens, it answers out loud, and over weeks it shows you how you have been sounding. No accounts, no API keys, no audio or transcript ever leaves the device.

**Status:** Phase 1 done. You can talk to it. See [docs/DESIGN.md](docs/DESIGN.md) for scope, architecture, stack, safety, evals, and the phased plan.

| Measured on an M2 Pro, 16 GB | |
|---|---|
| Time to first audio, p50 | 1836 ms |
| Time to first audio, p95 | 2517 ms |
| Transcription, mean | 388 ms |
| Word error rate on fixtures | 0% |

Numbers come from `make eval` and `make eval-asr`, and every run is committed under `evals/results/`. The fixtures are synthesised speech, so the error rate says the test is easy, not that transcription is solved.

## Running it

```
make setup     # venv, dependencies, and the Qwen3 model
make run       # http://127.0.0.1:8000
make test      # drives the socket with a fixture, checks barge-in
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
