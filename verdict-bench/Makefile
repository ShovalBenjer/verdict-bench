.PHONY: run report export ui check docker docker-run clean

PROMPT ?= v4
MODELS ?= gemini-flash

run:            ## run the suite: make run PROMPT=v4 MODELS="gemini-flash claude-haiku"
	python3 engine/runner.py --prompt $(PROMPT) --models $(MODELS)

report:         ## print the benchmark table
	python3 engine/runner.py --report

export:         ## regenerate ui/public/benchmark.json from sqlite
	python3 engine/export.py

ui: export      ## export + rebuild the web bundle (Tauri and web both read dist/)
	cd ui && npm run build && cp public/benchmark.json dist/benchmark.json

check:          ## tests + lint + type check + compile check
	python3 -m py_compile engine/*.py
	python3 -m ruff check engine/
	python3 -m mypy engine
	python3 -m pytest -q tests/
	python3 engine/runner.py --report >/dev/null && echo "check: report OK"

docker:         ## build the container (engine + built UI)
	docker build -t verdict-bench .

docker-run:     ## serve the UI + expose the report from the container
	docker run --rm -p 8080:8080 -v $(PWD)/state:/app/state verdict-bench

clean:
	rm -rf ui/dist ui/node_modules engine/__pycache__
