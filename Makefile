PY := apps/api/.venv/bin/python
UVICORN := apps/api/.venv/bin/uvicorn
RUFF := apps/api/.venv/bin/ruff

.PHONY: setup web dev db run test units eval eval-asr eval-safety eval-replies corpus recordings lint

setup:
	cd apps/api && uv venv --python 3.12 && uv pip install -e ".[dev]"
	cd apps/web && npm install
	ollama pull qwen3:8b

web:
	cd apps/web && npm run build

dev: db
	@echo "API on :8000, client on :3000"
	@$(UVICORN) --app-dir apps/api murmur.app:app --port 8000 & \
	 cd apps/web && NEXT_PUBLIC_API=http://127.0.0.1:8000 npm run dev

db:
	docker compose up -d

run: db web
	$(UVICORN) --app-dir apps/api murmur.app:app --port 8000

units:
	cd apps/api && .venv/bin/pytest -q

test:
	$(PY) apps/api/tests/test_loop.py

eval:
	$(PY) evals/run_latency.py

eval-asr:
	$(PY) evals/run_asr.py

# Real human speech to score against. CC BY 4.0, about 322 MB, kept outside
# the repository because it is someone else's audio and far too large.
corpus:
	mkdir -p ~/.murmur/corpora
	cd ~/.murmur/corpora && test -d LibriSpeech/dev-clean || \
	  (curl -O https://www.openslr.org/resources/12/dev-clean.tar.gz && \
	   tar xzf dev-clean.tar.gz && rm dev-clean.tar.gz)

# Your own entries, turned into a test set you then correct by hand.
recordings:
	$(PY) apps/api/tools/export_recordings.py

eval-safety:
	$(PY) evals/run_safety.py
	$(PY) evals/check_freshness.py

eval-replies:
	$(PY) evals/run_replies.py

lint:
	$(RUFF) check apps/api/murmur apps/api/tests evals
	cd apps/web && npx tsc --noEmit
