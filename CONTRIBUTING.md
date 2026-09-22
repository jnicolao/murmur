# Contributing

Notes to myself, mostly, and to anyone reading the history later.

## The loop

1. **Open an issue first.** State the problem and what done looks like. An
   issue that says "implement prosody" is not useful in three weeks; one that
   says what should be true when it is finished is.
2. **Branch from `main`**, named `<issue-number>-short-slug`, for example
   `2-prosody-features`.
3. **Open a pull request** that references the issue with a closing keyword,
   so merging it closes the issue: `Closes #2`.

Nothing lands on `main` directly.

## Before opening a pull request

```
make lint
make units        # fast, no model required
make test         # needs the server running and the models loaded
```

If the change touches a prompt, a model, or the safety layer, re-run the
evals and commit the results:

```
make eval         # latency
make eval-asr     # transcription
make eval-safety  # the crisis suites, and the freshness check
```

The freshness check fails the build when the committed safety result predates
the current classifier version. That is deliberate. A prompt change shipping
with numbers describing a classifier that no longer runs is the failure it
exists to prevent.

## Things that are not negotiable

- **The crisis check runs before any reply token is generated.** Not beside
  it, not after it. Nothing the model writes may reach someone in crisis.
- **The crisis message is fixed text.** It is never generated, never
  paraphrased, never personalised.
- **Local crisis numbers are only ever added by a person who has called
  them.** An unverified entry in `resources.json` is ignored by design.
- **Nothing leaves the machine.** No telemetry, no error reporting, no model
  API. If a change needs a network call, it needs a conversation first.
- **Time to first audio stays under two seconds at p50.** There is about
  60 ms of headroom. New work in the turn runs alongside the reply, not
  before it.

## Commit messages

Say what changed and why. Explain anything the diff cannot: a decision that
looks arbitrary, a measurement that drove it, something that was tried and
abandoned. No trailers.
