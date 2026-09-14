# murmur

A space for your inner voice.

Murmur is a voice-first journal that runs entirely on your own machine. You talk, it listens, it answers out loud, and over weeks it shows you how you have been sounding. No accounts, no API keys, no audio or transcript ever leaves the device.

**Status:** design complete, build not started. See [docs/DESIGN.md](docs/DESIGN.md) for scope, architecture, stack, safety, evals, and the phased plan.

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
