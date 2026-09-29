PY := apps/api/.venv/bin/python
UVICORN := apps/api/.venv/bin/uvicorn
RUFF := apps/api/.venv/bin/ruff

.PHONY: setup web dev db run test units eval eval-asr eval-safety eval-replies lint

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

eval-safety:
	$(PY) evals/run_safety.py
	$(PY) evals/check_freshness.py

eval-replies:
	$(PY) evals/run_replies.py

lint:
	$(RUFF) check apps/api/murmur apps/api/tests evals
	cd apps/web && npx tsc --noEmit
