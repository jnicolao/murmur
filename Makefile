PY := apps/api/.venv/bin/python
UVICORN := apps/api/.venv/bin/uvicorn
RUFF := apps/api/.venv/bin/ruff

.PHONY: setup db run test units eval eval-asr eval-safety lint

setup:
	cd apps/api && uv venv --python 3.12 && uv pip install -e ".[dev]" && uv pip install websockets
	ollama pull qwen3:8b

db:
	docker compose up -d

run: db
	$(UVICORN) --app-dir apps/api murmur.app:app --port 8000 --reload

units:
	cd apps/api && .venv/bin/pytest -q

test:
	$(PY) apps/api/tests/test_loop.py

eval:
	$(PY) evals/run_latency.py

eval-asr:
	$(PY) evals/run_asr.py

eval-safety:
	$(PY) evals/run_safety.py
	$(PY) evals/check_freshness.py

lint:
	$(RUFF) check apps/api/murmur apps/api/tests evals
