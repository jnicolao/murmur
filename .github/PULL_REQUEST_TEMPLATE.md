Closes #

## What changed

<!-- What this does and why it is done this way. Mention anything you tried
     that did not work, and anything a reviewer would otherwise have to
     reverse engineer from the diff. -->

## Checks

- [ ] `make lint` and `make units` pass
- [ ] `make test` passes, if the voice loop or the crisis path was touched
- [ ] Evals re-run and results committed, if a prompt, a model, or the
      safety layer changed
- [ ] `PROMPT_VERSION` or `CLASSIFIER_VERSION` bumped, if the wording changed
- [ ] Documentation updated, if behaviour or setup changed

## Measurements

<!-- Numbers before and after, if this touches latency, transcription, or
     the crisis suites. Say plainly if a number got worse. -->
