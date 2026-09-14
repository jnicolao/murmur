# Murmur — Design Document

**Tagline:** A space for your inner voice.
**Status:** Draft v1, 2026-09-14
**Owner:** Justine Nicolao
**License target:** Apache-2.0, every dependency free and open source, no paid APIs.

---

## 1. What Murmur is

Murmur is a voice-first journal. You press a button and talk. Murmur transcribes what you said, reflects it back in a short spoken reply, and keeps a private record. Over time it shows you how you have been sounding, not just what you have been saying.

It is a journal with reflection. It is not therapy, not a coach, and not a companion that claims to heal you. That line is drawn on purpose and is enforced in the system prompt, the safety layer, and the copy.

### The three promises

1. **Speak, don't type.** A real-time voice loop: you talk, it listens, it answers out loud, you can interrupt.
2. **Emotional awareness.** Mood is estimated from *how* you sound (prosody) and *what* you say (text), then tracked over weeks.
3. **Private by architecture.** Every model runs on your own machine. No audio or transcript ever leaves the device. Nothing in the stack requires an account or an API key.

### Why this is the flagship

The interesting engineering is in the seams between those promises: streaming audio through four models with sub-two-second time-to-first-audio, fusing two noisy affect signals into one honest trend, building memory that surfaces relevant past entries without being creepy, and evaluating all of it with real ground truth. Each of those is a writeup on its own.

---

## 2. Scope

### v1 (the MVP loop)

- One web page. Press to talk, or hands-free with voice activity detection.
- Live transcript appears as you speak (per utterance, not per word).
- Spoken reply streams back, sentence by sentence. You can talk over it to interrupt.
- After each session, a one-tap mood check-in (1 to 5) and an auto-generated two-line summary.
- Mood timeline: one chart, showing self-reported mood and estimated mood side by side.
- Entry list with search over transcripts.
- Crisis safety path.
- Single user, local-first, no auth.

### Explicitly out of v1

- Mobile app (Flutter). The portfolio card currently promises it; the card will be updated.
- Cloud sync, multi-user, accounts.
- Fine-tuning on the user's data.
- Voice cloning or custom voices.
- Encrypted vault (see Phase 5).
- Browser-only WebGPU mode (see Phase 5).

### Non-goals, permanently

- Diagnosing anything.
- Giving advice on medication, self-harm, or other people's mental health.
- Selling or transmitting user data. There is no server to sell it from.

---

## 3. Architecture

Two processes on one machine, plus Ollama.

```
Browser (Next.js)                        Server (FastAPI, Python)
┌──────────────────────┐   WebSocket    ┌─────────────────────────────────┐
│ mic → AudioWorklet   │ ─ PCM 16k ───▶ │ VAD gate (Silero)               │
│ Silero VAD (onnx)    │                │ ASR: faster-whisper             │
│ transcript pane      │ ◀─ transcript ─│ affect: audio model + prosody   │
│ reply pane           │ ◀─ tokens ─────│ safety classifier               │
│ Web Audio playback   │ ◀─ audio ──────│ memory retrieval (pgvector)     │
│ mood chart (Recharts)│                │ LLM via Ollama (Qwen3)          │
└──────────────────────┘                │ TTS: Kokoro-82M                 │
                                        └──────────┬──────────────────────┘
                                                   │
                                        Postgres + pgvector · Langfuse (self-hosted)
```

### The streaming loop, step by step

1. **Capture.** An AudioWorklet delivers 16 kHz mono PCM frames. Silero VAD runs in the browser so the UI can show "listening" state and cut playback on barge-in without a round trip.
2. **Utterance segmentation.** When VAD closes an utterance (about 500 ms of silence), the browser sends the buffered frames as one message. The server also runs VAD as a guard against noisy clients.
3. **Transcribe.** faster-whisper transcribes the utterance with word timestamps. Target: under 1 s for a 5 s utterance on CPU with `small.en` int8.
4. **Affect.** In parallel with the LLM call: the audio emotion model scores the utterance, and prosodic features are extracted (pitch mean and range, speech rate from word timestamps, pause ratio from VAD). Text affect comes from the LLM's structured output in step 6.
5. **Safety.** A two-stage classifier runs on the transcript before any reply is generated. Stage one is a curated phrase list. Stage two is a small LLM call with a fixed yes/no schema. If either fires, the reply is a fixed human-written message and the reflective loop is bypassed.
6. **Retrieve and respond.** Embed the utterance, pull the top few related past entries within the last 90 days, and build the prompt. Qwen3 streams the reply with thinking disabled. The reply schema asks for the spoken text plus a small JSON block with valence, arousal, and up to two emotion labels for the user's utterance.
7. **Speak.** Reply text is split on sentence boundaries as it streams. Each sentence goes to Kokoro and the resulting audio is sent as soon as it is ready. Target: time-to-first-audio under 2 s end to end.
8. **Persist.** Utterance, transcript, timings, affect scores, and reply are written to Postgres. The audio itself is stored as Opus on local disk and can be deleted per entry or in bulk.

### Why a Python server rather than browser-only

A fully in-browser pipeline (transformers.js Whisper, WebLLM, kokoro-js on WebGPU) would give a free live demo and the cleanest privacy story. It was rejected for v1 because the affect models, the eval harness, and the memory layer are much easier to build and iterate on in Python, and model quality in the browser is capped by download size. The WebSocket protocol is kept model-agnostic so a browser-only runtime can be added later as Phase 5 without touching the UI.

---

## 4. Stack and licenses

| Layer | Choice | License | Notes |
|---|---|---|---|
| Frontend | Next.js 15, TypeScript, Tailwind | MIT | Same stack as the portfolio |
| Browser VAD | Silero VAD via `@ricky0123/vad-web` | MIT / ISC | ONNX Runtime Web |
| Charts | Recharts | MIT | |
| API | FastAPI, uvicorn, websockets | MIT | |
| ASR | faster-whisper, Whisper `small.en` | MIT (code and weights) | Upgrade path: NVIDIA Parakeet-TDT 0.6B (CC-BY-4.0) if latency needs work |
| Server VAD | Silero VAD | MIT | |
| LLM | Qwen3-8B via Ollama | Apache-2.0 / MIT | Qwen3-4B if the 8B is too slow alongside the other models |
| TTS | Kokoro-82M | Apache-2.0 | Runs on CPU faster than real time |
| Audio affect | SpeechBrain `emotion-recognition-wav2vec2-IEMOCAP` | Apache-2.0 | Verify the weight license on Hugging Face before shipping; fallback is prosody-only |
| Prosody | librosa (pyin pitch), numpy | ISC / BSD | |
| Embeddings | bge-m3 via sentence-transformers | MIT / Apache-2.0 | Same as Harmonizer |
| Database | Postgres 16 + pgvector | PostgreSQL license | Docker compose |
| Observability | Langfuse, self-hosted | MIT (core) | Same as Harmonizer |
| Tooling | uv, ruff, pytest, pnpm | MIT / Apache-2.0 | |

Models known to be non-commercial and therefore excluded: audeering's dimensional emotion model (CC-BY-NC-SA) and the RAVDESS dataset (CC-BY-NC). CREMA-D (ODC-BY) is the free dataset used for the audio affect sanity check.

Hardware target: Apple M2 Pro, 16 GB. Budget: Qwen3-8B q4 about 5 GB, Whisper small about 500 MB, Kokoro about 300 MB, wav2vec2 about 1.2 GB, embeddings about 2 GB. Everything fits with headroom, but not all at once under load; see risks.

---

## 5. Data model

```
entries        id, started_at, ended_at, self_mood (1..5, nullable), summary, deleted_at
utterances     id, entry_id, seq, audio_path, transcript, words_json (timestamps),
               asr_ms, ttfa_ms, valence_text, arousal_text, labels_text,
               valence_audio, arousal_audio, labels_audio,
               pitch_mean, pitch_range, speech_rate, pause_ratio
replies        id, utterance_id, text, safety_triggered, model, prompt_version, latency_ms
embeddings     utterance_id, vector(1024)     -- bge-m3
mood_daily     date, self_mood_avg, est_valence_avg, est_arousal_avg, n_utterances
```

Raw audio lives on disk under a per-entry folder. Deleting an entry deletes its folder. A "forget everything" button truncates all tables and wipes the folder.

---

## 6. Emotional awareness, honestly

Two signals are estimated per utterance and one is reported by the user.

- **Text affect**: valence and arousal on a -1 to 1 scale plus labels, from the LLM's structured output.
- **Audio affect**: categorical output from the wav2vec2 model mapped to the same valence/arousal space, plus raw prosody features.
- **Self-report**: the 1 to 5 check-in after each session. This is the ground truth.

The timeline shows self-report as the primary line and the estimated valence as a secondary line. The product never tells the user "you are sad." It says things like "you sounded flatter this week than last," and only when the fused estimate and the self-report agree in direction. Where they disagree, the chart shows both and says nothing.

Fusion for v1 is a plain weighted average, weights chosen on the dev set (section 8). Anything fancier is deferred until the eval shows the simple version is the bottleneck.

---

## 7. Safety

This is a product people will talk to when they are at their worst. The safety layer is not optional and is the first thing built after the voice loop.

**Positioning.** The onboarding screen and the footer say, in plain words, that Murmur is a journal, is not a substitute for a professional, and is not monitored by any person.

**Crisis path.** Trigger conditions: phrase list hit, or the classifier returns yes. On trigger:
- The reflective loop is bypassed. No LLM-generated text is spoken.
- A fixed, human-written message is shown and spoken. It acknowledges what the person said, states that Murmur cannot help with this, and gives a configurable list of resources. Default resource list points to an international helpline directory; a local list is set in config.
- The entry is saved with `safety_triggered = true` and is never used as retrieval context for future prompts.
- Nothing is sent anywhere. There is no reporting.

**System prompt rules for the reflective loop.**
- Reflect and ask, at most one question per reply. Never advise.
- Never diagnose, name a condition, or speculate about medication.
- Never claim to be a therapist, doctor, or friend.
- Never discourage seeking human help.
- Keep replies under about 60 words. This is a journal, not a chat.

**Tests.** A fixed suite of crisis phrasings, including indirect ones, must trigger the path 100 percent of the time. A suite of ordinary sad or angry entries must not trigger it. Both run in CI.

---

## 8. Evaluation

Evals are what separate this from a wrapper. Each has a dataset, a metric, and a place where the number is recorded.

| What | Dataset | Metric | Where it runs |
|---|---|---|---|
| ASR accuracy | 50 of the owner's own recordings, hand-corrected | WER | `make eval-asr`, local |
| ASR and loop latency | Same recordings replayed | p50 / p95 ASR ms, time-to-first-audio | `make eval-latency`, local |
| Audio affect sanity | CREMA-D subset | Accuracy vs. acted labels | `make eval-affect`, local |
| Mood estimate vs. truth | Owner's real entries with self-report | Spearman correlation, per week | `make eval-mood`, local |
| Reply quality | 50 fixed transcripts | LLM-as-judge rubric: reflective, no advice, no diagnosis, brevity, correct use of memory | `make eval-replies`, local, Qwen3 as judge |
| Safety | Crisis and non-crisis phrase suites | Recall on crisis, false-positive rate on non-crisis | CI, every push |
| Unit and protocol | Segmentation, schema parsing, retrieval | pytest | CI, every push |

Local evals write a JSON result to `evals/results/` which is committed, so the history of every number lives in git. CI runs only what a free GitHub runner can run: safety suites, unit tests, and a check that eval results are not older than the prompt version they claim to measure.

Prompt changes require re-running the reply and safety evals before merge. This is enforced by the CI freshness check, not by discipline.

---

## 9. Observability

Every turn is a Langfuse trace with spans for VAD, ASR, affect, safety, retrieval, LLM, and each TTS sentence. The time-to-first-audio number in the eval table is computed from these spans, not from a separate stopwatch. Traces are stored locally in the self-hosted Langfuse and contain transcripts, so the same delete-everything action that wipes entries also wipes traces.

---

## 10. Repository layout

```
murmur/
├── apps/
│   ├── web/              # Next.js
│   └── api/              # FastAPI
│       ├── murmur/
│       │   ├── audio/    # vad, asr, tts, prosody
│       │   ├── affect/   # audio model, text schema, fusion
│       │   ├── safety/   # phrase list, classifier, fixed message
│       │   ├── memory/   # embeddings, retrieval
│       │   ├── llm/      # ollama client, prompts (versioned)
│       │   └── ws/       # protocol, session loop
│       └── tests/
├── evals/
│   ├── datasets/         # CREMA-D subset manifest, phrase suites, fixed transcripts
│   ├── results/          # committed JSON, one file per eval per run
│   └── run_*.py
├── docs/
│   ├── DESIGN.md         # this file
│   └── writeups/         # one post per hard problem
├── docker-compose.yml    # postgres+pgvector, langfuse
├── Makefile
└── README.md
```

---

## 11. Plan

Each phase ends with something that runs and one number that is measured.

**Phase 1 — The loop (2 weeks).** Press to talk, transcript, streamed spoken reply, barge-in. No memory, no affect, no persistence beyond a session log. Done when: time-to-first-audio p50 under 2 s on the M2 Pro, measured from Langfuse spans.

**Phase 2 — Safety and persistence (1 week).** Crisis path, system prompt rules, Postgres schema, entry list, delete-everything. Done when: safety suites pass in CI at 100 percent recall and under 5 percent false positives.

**Phase 3 — Affect and timeline (2 weeks).** Prosody features, audio model, text schema, fusion, self-report check-in, the mood chart. Done when: four weeks of the owner's own entries exist and the mood eval reports a Spearman number, whatever it is.

**Phase 4 — Memory and evals (2 weeks).** pgvector retrieval, memory in the prompt, reply-quality judge, ASR and latency evals, results committed. Done when: every row in the eval table has a number in git and the README shows them.

**Phase 5 — After v1, pick one.** Browser-only WebGPU runtime for a hosted live demo; encrypted vault with SQLCipher or pgcrypto; nightly wind-down mode; Flutter app.

Sequencing against Harmonizer: Phase 1 does not start until Harmonizer v1 is shippable. Total v1 estimate is seven weeks of part-time work.

---

## 12. Portfolio presentation

The models cannot run on free hosting, so the portfolio card links to:

- A 60-second screen recording of a real session, with the transcript and timeline visible.
- The repo, whose README leads with the eval table and the architecture diagram.
- Writeups in `docs/writeups/`, one per hard problem: the streaming loop and barge-in, fusing two affect signals, memory without creepiness, evaluating a journal.

The portfolio card stack list changes to: Next.js, FastAPI, Whisper, Qwen3, Kokoro, pgvector, Langfuse. Flutter, OpenAI, and Supabase are removed.

---

## 13. Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Four models on 16 GB contend for memory and latency blows past 2 s | High | Measure in Phase 1 before anything else is added. Fall back to Qwen3-4B, Whisper `base.en`, and lazy-load the affect model only after the reply has started speaking. |
| Audio affect model is unreliable on real, non-acted speech | High | It is a secondary signal by design. The chart leads with self-report. Prosody-only fallback if the model adds nothing on the mood eval. |
| The affect model weight license is not what Hugging Face says | Medium | Verify before Phase 3. Prosody-only is the fallback. |
| Safari lacks AudioWorklet or VAD support in some configuration | Low | Develop and demo on Chrome. Note the requirement in the README. |
| Scope creep toward "companion" | High | Section 2 non-goals and the 60-word reply cap. Every feature request is checked against "is this a journal?" |
| Building this while Harmonizer is unfinished | High | Section 11 gate: Phase 1 starts only after Harmonizer v1 ships. |

---

## 14. Open questions

1. Default helpline list: which country or countries should ship in config?
2. Should raw audio be kept at all after transcription, or only for the eval set? Keeping it enables re-scoring with better affect models later; deleting it is simpler and more private. Current lean: keep, with a per-entry delete and a setting to disable.
3. Should the check-in be a 1 to 5 scale or two sliders (valence and energy)? Two sliders give better ground truth for the fusion eval but add friction. Current lean: 1 to 5 in v1.
4. Reply voice: Kokoro ships several voices. Pick one calm voice and do not offer a chooser in v1.
