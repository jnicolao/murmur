# murmur

A space for your inner voice.

Murmur is a voice-first journal that runs entirely on your own machine. You press a button and talk. It transcribes what you said, reflects it back in a short spoken reply, keeps a private record, and over time shows you how you have been sounding, not just what you have been saying.

Every model runs locally. There are no accounts, no API keys, and no audio or transcript ever leaves the device.

**Status: complete.** v1, November 2026. The voice loop, the crisis path, persistence, mood signals from the voice and from the words, and a timeline that knows when to say nothing. What it does not do is listed near the end, plainly. The full design, and where the build diverged from it, is in [docs/DESIGN.md](docs/DESIGN.md).

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
| Word error rate, real speech | 6.2 percent |
| Replies passing all six rules | 83 percent of 24 |
| Prosody, per utterance | 7 ms |

Latency was measured on 24 September 2026. The files a turn runs through have not changed since, so the figure describes the finished code. It is a five-turn run, so the p50 is the real signal and the p95 is barely more than the worst of five.

---

## How a turn works

```
Browser                                  Server (FastAPI)

  mic -> AudioWorklet, 16 kHz PCM
      ---- binary frames ----------->    buffered
      ---- {"type":"end"} ---------->    transcribe      faster-whisper
      <--- {"type":"transcript"} ----                    prosody starts beside the reply
                                         crisis check    phrases, then model
                                              |
                                    triggered |  not triggered
                                              |
      <--- {"type":"crisis"} --------    fixed text      reflect, streamed
      <--- {"type":"reply"} ---------                    one speech unit at a time
      <--- binary audio, 24 kHz -----    synthesise      Kokoro
                                                         affect block peeled off the end
      <--- {"type":"done"} ----------    persist         Postgres, Opus on disk
```

Barge-in works because the model runs on a worker thread while the socket keeps reading. Pressing the button mid-reply sends a stop and the server abandons the rest of the turn.

Two mood signals are taken from every turn without adding to its latency. **Prosody** (pitch, its spread, speech rate and pausing) is measured from the waveform on a separate thread and written once the reply has been spoken. **Text affect** (valence, arousal and up to two labels) comes back from the same model call as the reply, after a sentinel that is stripped before the speech synthesiser can see it, so no structured output is ever read aloud.

---

## The mood timeline

Two lines over time: how you rated each session, one to five, and how you sounded, estimated from what you said. Both are shown, and neither is presented as the truth about your week.

The harder decision was when to say anything in words. A sentence appears only when the estimate and your own rating move in the same direction. When they disagree, both lines stay on the chart and the text says nothing, because you are the authority on your own week and a confident sentence built on a disagreeing estimate is worse than silence. Any sentence it does produce describes how you *sounded*, never how you *are*.

Four tests assert the silence: too few entries, a steady week, only one signal moving, and the two disagreeing. A fifth asserts that no sentence it can produce names a feeling as a fact. Entries that reached the crisis path never appear on the timeline.

---

## Safety

Murmur is a journal, not therapy. It is not a substitute for a professional, and no person reads or listens to anything recorded in it. That is stated in the interface, not only here.

Anything that invites people to speak freely when they are struggling will eventually hear from someone in crisis. The handling is deliberate:

- **The check runs before a single token of reply is generated.** Nothing the language model writes can reach someone in crisis, because at that point it has written nothing.
- **Two stages.** A curated list of unambiguous phrasings runs first and costs microseconds. It is narrow on purpose, and it is paired with a list of violent English idioms so that "this project is killing me" is never mistaken for a crisis. Anything the list misses goes to a one-word call to the local model, which catches indirect phrasing such as writing goodbye letters, giving belongings away, or cancelling future plans.
- **On a trigger the reflective loop is bypassed entirely.** A fixed, human-written message is shown and spoken verbatim. It acknowledges the person, says plainly that Murmur cannot help with this, and points to real help.
- **That entry is held apart.** It is marked in the database and kept off the timeline and out of the transcription test set by a single view, so the rule is enforced by the schema rather than by remembering to filter in each place.
- **Nothing is reported anywhere.** There is nowhere to report to. The application has no network destination.

### Crisis resources

One resource ships: findahelpline.com, an international directory, checked live on 11 November 2026.

Local numbers are deliberately not in the repository. Murmur runs on the machine of whoever installs it, in whatever country they are in, so local crisis numbers are per-installation configuration rather than code. They go in `apps/api/resources.json`, which git ignores, and the app ignores any entry there until `verified` is set to true. A wrong crisis number is worse than none, so check each one yourself, by calling it, before setting that.

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

- macOS or Linux, Python 3.12, [uv](https://docs.astral.sh/uv/), and Node 22 or later
- [Ollama](https://ollama.com)
- Docker, for Postgres
- Roughly 8 GB of disk for model weights, and 16 GB of memory to run comfortably

### Setup

```
make setup     # virtualenv, client dependencies, and the Qwen3 model
make run       # starts Postgres, builds the client, serves on http://127.0.0.1:8000
```

The first start downloads model weights and takes a few minutes. Later starts take about ten seconds.

### Everything else

```
make units        # fast checks, no model required
make test         # drives the socket with recorded audio: reply, barge-in, crisis path
make eval         # end to end latency
make eval-asr     # transcription speed and accuracy, on real speech
make eval-safety  # the crisis suites, and the freshness check CI gates on
make eval-replies # judge the reflective reply against its six rules
make corpus       # fetch LibriSpeech dev-clean for the transcription eval
make recordings   # export your own entries as a transcription test set
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
| Prosody | librosa | ISC |
| API | FastAPI over one WebSocket | MIT |
| Database | Postgres 16 with pgvector | PostgreSQL |
| Client | Next.js, TypeScript, Tailwind, Recharts | MIT |

The client is a static export served by the API process, so running Murmur is one command.

---

## Layout

```
apps/api/murmur/
  audio/      transcription, synthesis, sentence splitting
  affect/     prosody, and the rule for when the timeline may speak
  llm/        Ollama client, versioned prompts, the trailing affect block
  safety/     phrase list, classifier, fixed crisis response
  store/      schema, migrations, persistence
  ws/         protocol and the session loop
apps/api/tools/
  seed.py               invented entries, for working on the chart
  export_recordings.py  your own entries, as a test set to correct
apps/web/     the client, built as a static export
evals/
  datasets/   crisis, ordinary and reply suites
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
| Transcription | LibriSpeech dev-clean; your own recordings once corrected | Word error rate per source |
| Latency | Recorded utterances replayed | Time to first audio, p50 under 2000 ms |
| Reply quality | 24 fixed transcripts, judged against the six rules | Compared across prompt versions |
| Model-free checks | Phrase list, splitter, prosody, affect block, timeline rule, word error rate | Run on every push |

A freshness check fails the build when a committed result predates the wording it claims to measure, for both the crisis classifier and the reply prompt. The failure it exists to prevent is a prompt change shipping alongside numbers that describe a classifier no longer running.

The crisis suites need Ollama and a 5 GB model, which a hosted CI runner does not have. CI therefore gates on the committed evidence through that freshness check, and the suites themselves run locally.

---

## Choosing the transcription model

Scored on 100 clips of real human speech from LibriSpeech dev-clean, spread across 40 speakers:

| Model | Word error rate | Mean time | Clips with no errors |
|---|---|---|---|
| `tiny.en` | 7.7% | 201 ms | 43/100 |
| **`base.en`** | **6.2%** | **389 ms** | **56/100** |
| `small.en` | 5.8% | 1247 ms | 58/100 |

`base.en` is the default. Moving up to `small.en` buys about four tenths of a percentage point for 858 ms, close to half the entire two second budget for a reply. Moving down to `tiny.en` saves 188 ms and costs about a point and a half, which is the wrong trade when the transcript is the thing being kept.

Two things make these figures slightly pessimistic. Number formatting counts as an error, so `small.en` hearing "seventeen seventeen" as "1717" scores as completely wrong. And the corpus contains very short clips, where one missed proper noun in a two-word utterance also scores as completely wrong.

---

## What measuring changed

Most of the decisions here exist because something was measured rather than assumed.

- **Transcription was half the latency budget.** Moving from `small.en` to `base.en` bought back most of a second, which is the difference between passing the two second target and missing it.
- **A long first sentence delayed the first sound by over a second.** Kokoro returns no audio until a whole unit is synthesised, so the splitter cuts long runs at a clause boundary and speech starts while the model is still writing the rest.
- **The first crisis classifier missed a quarter of its suite.** Every miss was indirect and calmly worded. Rewriting the prompt around recognised warning signs, and stating plainly that a missed yes costs more than a wrong yes, took recall from 75 percent to 100 percent without a single false positive.
- **A unit test caught a pattern that could never match.** `cut(?:ing)?` does not match "cutting", so a direct statement of self-harm was falling through to the slower stage instead of being caught instantly.
- **The pitch tracker in the plan was unusable.** `librosa.pyin` took 37 seconds for a 6.5 second clip. `librosa.yin`, paired with an energy-based voicing mask, does the same job in 7 milliseconds.
- **The first transcription test could not tell the models apart.** Every size scored zero errors on synthesised speech, so the default had never really been chosen. Rebuilt on real speech, the test separates them and confirms the default for a stated reason rather than by accident.

---

## What it does not do

- **It does not know whether its mood estimate is right.** Checking it means scoring the estimate against your own ratings over about four weeks of real entries, and that measurement was never run. The timeline speaks only when the estimate and your rating agree precisely because the estimate is unvalidated.
- **It does not read emotion from the voice itself.** Pitch, speech rate and pausing are measured and stored for every utterance, but they are not folded into the estimate. Choosing how to weight them needs the same four weeks of data.
- **It does not remember.** Each reply sees only what you have just said. Retrieval over earlier entries was planned and not built.
- **It has not been measured on its owner's voice.** Transcription is scored on strangers reading audiobooks. The tooling to score your own recordings exists; no corrected clips do.
- **Its automated tests do not use a microphone.** They drive the WebSocket with recorded audio, so browser capture is outside what they cover.
- **It ships no local crisis numbers.** By design, as set out under Safety.
- **It is observed only through JSON timings.** Fine at five stages. It would not be at ten.
- **It needs a capable machine.** Four models in 16 GB works, but tightly. Latency measured on a machine that is already swapping describes the machine rather than the code, and that happened twice during development.

---

## What I would build next

In order, because each depends on the one before:

1. **Validate the estimate.** Use it for four weeks, then score the estimate against the ratings. Everything after this depends on that number.
2. **Fold in prosody, but only if it helps.** Add it to the estimate and keep it only if the correlation with your ratings improves.
3. **Memory,** with an eval for whether recalled entries are actually relevant before any reply is allowed to use them.
4. **A browser-only build** on WebGPU, so there could be a demo that needs no installation.
5. **Tracing,** once there are enough stages that JSON timings stop being readable.

The audio emotion model in the original plan is deliberately not on this list. Prosody and text already give two independent signals, its weight licence was never confirmed, and it would add 1.2 GB to a machine with none to spare.

---

## License

Apache-2.0. See [LICENSE](LICENSE).
