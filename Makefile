PY := apps/api/.venv/bin/python
UVICORN := apps/api/.venv/bin/uvicorn

.PHONY: setup run test eval eval-asr lint

setup:
	cd apps/api && uv venv --python 3.12 && uv pip install -e ".[dev]" && uv pip install websockets
	ollama pull qwen3:8b

run:
	$(UVICORN) --app-dir apps/api murmur.app:app --port 8000 --reload

test:
	$(PY) apps/api/tests/test_loop.py

eval:
	$(PY) evals/run_latency.py

eval-asr:
	$(PY) evals/run_asr.py

lint:
	cd apps/api && .venv/bin/ruff check murmur tests ../../evals
