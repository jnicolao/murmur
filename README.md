# murmur

A space for your inner voice.

Murmur is a voice-first journal that runs entirely on your own machine. You press a button and talk. It transcribes what you said, reflects it back in a short spoken reply, and keeps a private record. Over time it is meant to show you how you have been sounding, not just what you have been saying.

Every model runs locally. There are no accounts, no API keys, and no audio or transcript ever leaves the device.

**Status:** two of four phases complete. The voice loop works and the crisis path works. Affect tracking and the mood timeline are next. This is not finished software.

---

## Why it exists

Journalling apps assume you want to type. Most people process difficult feelings by talking, and the gap between having a thought and writing it down is where the thought usually gets lost.

Three things have to be true for a voice journal to be worth using:

1. **It has to feel like speaking, not dictating.** A reply that arrives four seconds later is a transaction. Under two seconds it starts to feel like being heard.
2. **It has to notice something you would not.** A record of what you said is a diary. Noticing that you have sounded flatter for two weeks is worth more than that.
3. **It has to be genuinely private.** People do not say the true thing into a microphone that uploads.

Those constraints are what make this an engineering problem rather than a wrapper around a chat API. Each one is measured rather than asserted.

---

## Results

Measured on an Apple M2 Pro with 16 GB of memory. Every run is written to `evals/results/` and committed, so the history of each number lives in git.

| | |
|---|---|
| Time to first audio, p50 | 1767 ms |
| Time to first audio, p95 | 2013 ms |
| Transcription, p50 | 383 ms |
| Crisis check, p50 | 332 ms |
| Crisis recall, 20 entries | 100 percent |
| False positives, 22 ordinary entries | 0 percent |
| Word error rate on voice fixtures | 0 percent |
| Replies passing all six rules | 83 percent of 24 |

Two caveats the numbers do not carry on their own. The voice fixtures are synthesised speech, so a zero word error rate means the test is easy, not that transcription is solved. And the latency run is five turns, so the p50 is the real signal while the p95 is barely more than the worst of five.

---

## How a turn works

```
Browser                                  Server (FastAPI)

  mic -> AudioWorklet, 16 kHz PCM
      ---- binary frames ----------->    buffered
      ---- {"type":"end"} ---------->    transcribe      faster-whisper
      <--- {"type":"transcript"} ----
                                         crisis check    phrases, then model
                                              |
                                    triggered |  not triggered
                                              |
      <--- {"type":"crisis"} --------    fixed text      reflect, streamed
      <--- {"type":"reply"} ---------                    one speech unit at a time
      <--- binary audio, 24 kHz -----    synthesise      Kokoro
      <--- {"type":"done"} ----------    persist         Postgres, Opus on disk
```

Barge-in works because the model runs on a worker thread while the socket keeps reading. Pressing the button mid-reply sends a stop and the server abandons the rest of the turn.

---

## Safety

Murmur is a journal, not therapy. It is not a substitute for a professional, and no person reads or listens to anything recorded in it. That is stated in the interface, not only here.

Anything that invites people to speak freely when they are struggling will eventually hear from someone in crisis. The handling is deliberate:

- **The check runs before a single token of reply is generated.** Nothing the language model writes can reach someone in crisis, because at that point it has written nothing.
- **Two stages.** A curated list of unambiguous phrasings runs first and costs microseconds. It is narrow on purpose, and it is paired with a list of violent English idioms so that "this project is killing me" is never mistaken for a crisis. Anything the list misses goes to a one-word call to the local model, which catches indirect phrasing such as writing goodbye letters, giving belongings away, or cancelling future plans.
- **On a trigger the reflective loop is bypassed entirely.** A fixed, human-written message is shown and spoken verbatim. It acknowledges the person, says plainly that Murmur cannot help with this, and points to real help.
- **That entry is held apart.** It is marked in the database and excluded from future context by a view, so the rule is enforced by the schema rather than by remembering to filter.
- **Nothing is reported anywhere.** There is nowhere to report to. The application has no network destination.

### Crisis resources

Only an international helpline directory ships by default. Local crisis numbers are deliberately not hardcoded, because a wrong crisis number is worse than none. They belong in `apps/api/resources.json`, and an entry there is ignored until a person sets `verified` to true. Copy `resources.json.example` and check the numbers yourself before trusting them.

---

## Privacy

- Every model runs locally. Nothing is sent to any third party.
- Recordings are stored as Opus under `~/.murmur/audio`, outside the repository.
- Deleting an entry deletes its rows and its recordings together. A delete that leaves the audio behind is not a delete.
- Forget everything truncates the database and removes the audio directory. There is no undo, and it requires typing a confirmation phrase.
- Keeping audio at all is optional. Set `MURMUR_KEEP_AUDIO=0` and only the transcript survives the turn.

---

## Running it

### Prerequisites

- macOS or Linux, Python 3.12, and [uv](https://docs.astral.sh/uv/)
- [Ollama](https://ollama.com)
- Docker, for Postgres
- Roughly 8 GB of disk for model weights, and 16 GB of memory to run comfortably

### Setup

```
make setup     # virtualenv, dependencies, and the Qwen3 model
make run       # starts Postgres, then serves on http://127.0.0.1:8000
```

The first start downloads model weights and takes a few minutes. Later starts take about ten seconds.

### Everything else

```
make units        # fast checks, no model required
make test         # drives the socket with fixtures: reply, barge-in, crisis path
make eval         # end to end latency, writes to evals/results
make eval-asr     # transcription speed and accuracy across model sizes
make eval-safety  # the crisis suites, and the freshness check CI gates on
make eval-replies # judge the reflective reply against its six rules
make web          # build the client
make dev          # API on :8000 and the client dev server on :3000
make lint
```

### Configuration

| Variable | Default | Purpose |
|---|---|---|
| `MURMUR_ASR_MODEL` | `base.en` | Whisper size. `tiny.en` is faster, `small.en` slower |
| `MURMUR_DSN` | local Postgres on port 5433 | Database connection |
| `MURMUR_AUDIO` | `~/.murmur/audio` | Where recordings are kept |
| `MURMUR_KEEP_AUDIO` | `1` | Set to `0` to discard audio after transcription |
| `MURMUR_RESOURCES` | `apps/api/resources.json` | Local crisis resources |

---

## Stack

Everything is free and open source. No component requires a paid API or an account.

| Layer | Choice | License |
|---|---|---|
| Speech to text | faster-whisper, `base.en` | MIT |
| Reflection | Qwen3 8B via Ollama | Apache-2.0 |
| Text to speech | Kokoro-82M | Apache-2.0 |
| API | FastAPI over one WebSocket | MIT |
| Database | Postgres 16 with pgvector | PostgreSQL |
| Client | Next.js, TypeScript, Tailwind, Recharts | MIT |

The client is a static export served by the API process, so running Murmur is still one command. `make dev` runs the Next.js dev server against the API when working on the interface.

---

## Layout

```
apps/api/murmur/
  audio/      transcription, synthesis, sentence splitting
  llm/        Ollama client and versioned prompts
  safety/     phrase list, classifier, fixed crisis response
  store/      schema and persistence
  ws/         protocol and the session loop
  static/     the client
evals/
  datasets/   the crisis and ordinary suites
  results/    every eval run, committed
docs/
  DESIGN.md   scope, architecture, decisions, risks, the full plan
```

---

## Evaluation

Evals are the point here, not an afterthought. Each has a dataset, a metric, and a committed result.

| What | Ground truth | Gate |
|---|---|---|
| Crisis recall and precision | 20 crisis entries, 22 ordinary | 100 percent recall, under 5 percent false positives |
| Transcription | Fixtures synthesised from known text | Word error rate |
| Latency | The same fixtures replayed | Time to first audio, p50 under 2000 ms |
| Reply quality | 24 fixed transcripts, judged against the six rules | Compared across prompt versions |
| Phrase list and splitter | Unit tests, no model needed | Runs on any CI machine |

A freshness check fails the build when a committed result predates the wording it claims to measure, for both the crisis classifier and the reply prompt. The failure it exists to prevent is a prompt change shipping alongside numbers that describe a classifier no longer running.

---

## What measuring changed

Three decisions here exist because something was measured rather than assumed. They are why the evals were wired in from the first phase rather than added at the end.

- **Transcription was half the latency budget.** The `small.en` model took 1353 ms per utterance against 371 ms for `base.en`, for identical transcripts on the fixtures. Switching the default bought back most of a second.
- **A long first sentence delayed the first sound by over a second.** Kokoro returns no audio until a whole unit is synthesised. The splitter now cuts long runs at a clause boundary, so speech starts while the model is still writing the rest.
- **The first crisis classifier missed a quarter of its suite.** Every miss was indirect and calmly worded. Rewriting the prompt around recognised warning signs, and stating plainly that a missed yes costs more than a wrong yes, took recall from 75 percent to 100 percent without costing a single false positive.

A unit test also caught a regular expression that could never match. The pattern `cut(?:ing)?` does not match "cutting", so a direct statement of self-harm was falling through to the slower stage instead of being caught instantly.

---

## Roadmap

- **Phase 1, done.** The voice loop: press to talk, streamed spoken reply, barge-in.
- **Phase 2, done.** The crisis path, persistence, entry list, delete everything.
- **Phase 3.** Mood estimated from prosody and from the text, scored against your own check-ins, and a timeline that shows the trend. The latency budget has about 60 ms of headroom, so this has to run beside the reply rather than before it.
- **Phase 4.** Memory: retrieval over past entries so a reply can refer to what you said last week, with an eval for whether recalled context is actually relevant.
- **Later.** An encrypted vault, a browser-only build for a hosted demo, and a mobile client.

Known gaps, stated plainly: the transcription fixtures are synthetic and need replacing with real recordings; local crisis resources still need to be chosen and verified by a person; and observability is plain JSON timings rather than proper tracing, which is fine at five stages and will not be at ten.

---

## License

Apache-2.0. See [LICENSE](LICENSE).
