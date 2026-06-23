.PHONY: setup aggregates web demo test lint build-web clean
PY ?= python3

setup:        ## install package + dev deps (uv if present, else pip)
	@command -v uv >/dev/null 2>&1 && uv pip install -e ".[dev,ml]" || $(PY) -m pip install -e ".[dev,ml]"

aggregates:   ## regenerate web/data/aggregates.json from data/raw/*.csv
	$(PY) -m pravah.build_aggregates

web:          ## serve the command centre at http://localhost:8000 (dev; fetch works)
	@cd web && $(PY) -m http.server 8000

demo:         ## open the offline command centre (data inlined)
	@echo "Open web/index.html in a browser (offline-safe)."

test:         ## run unit tests (add -m 'not data' to skip data-gated tests)
	$(PY) -m pytest -q

lint:         ## ruff check
	@command -v ruff >/dev/null 2>&1 && ruff check . || echo "ruff not installed (make setup)"

build-web:    ## M6: emit a single self-contained offline file into dist/
	@echo "M6 task: inline web/data/aggregates.json into web/index.html -> dist/pravah.html"

clean:
	rm -rf dist __pycache__ .pytest_cache src/pravah/__pycache__
