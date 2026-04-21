.PHONY: install seed test eval-offline eval-live serve dashboard demo docker-up docker-down clean help

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:  ## Install dependencies via uv (fast, reproducible)
	uv sync --all-extras || pip install -e ".[dev]"

seed:  ## Seed the pre-baked demo corpus (<5s, no downloads, verifies SHA256)
	python3 scripts/seed_demo.py

test: seed  ## Run unit + judge + streamlit tests (depends on seed)
	python3 -m pytest tests/ -q

mutmut: seed  ## Run mutation tests against critical validation modules (requires: pip install -e ".[test]")
	python3 -m mutmut run || true
	python3 -m mutmut results

tune: seed  ## Run chunk-strategy × top_k tuning sweep and print best cell
	python3 scripts/tuning_experiments.py --json-out docs/tuning_results.json

eval-offline: seed  ## Run eval against mock LLM fixtures (free, no API key needed)
	python3 ai/week1-rag/evals/offline_eval.py --mode offline --fixtures fixtures/mock_llm_responses.json

eval-live: seed  ## Run eval against real LLM (requires OPENAI_API_KEY, costs ~$0.15)
	@test -n "$$OPENAI_API_KEY" || (echo "OPENAI_API_KEY not set" && exit 1)
	python3 ai/week1-rag/evals/offline_eval.py --mode live

serve: seed  ## Start FastAPI backend on :8001 (depends on seed)
	uvicorn backend.main:app --host 0.0.0.0 --port 8001 --reload

dashboard:  ## Start Streamlit monitoring dashboard on :8501
	streamlit run monitoring/dashboard.py --server.port 8501 --server.headless true

demo: seed  ## Start Streamlit demo UI on :8502 (depends on seed so default tab works on first clone)
	streamlit run demo_ui/app.py --server.port 8502 --server.headless true

docker-up:  ## docker compose up (all-in-one: backend + dashboard + demo UI)
	docker compose up -d

docker-down:  ## docker compose down
	docker compose down

clean:  ## Remove caches, but keep demo corpus
	rm -rf .pytest_cache .ruff_cache __pycache__ */__pycache__ */*/__pycache__ */*/*/__pycache__
