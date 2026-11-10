PY ?= python3
export PYTHONPATH := src

.PHONY: fetch build all sample test lint clean

fetch:          ## download World Bank annual indicators (needs internet)
	$(PY) -m ngeco fetch
build:          ## outputs from official data in data/raw (run `make fetch` first)
	$(PY) -m ngeco build --mode official
all:            ## fetch + build in one go
	$(PY) -m ngeco all --mode official
sample:         ## try the whole pipeline on SYNTHETIC data (no internet needed)
	$(PY) -m ngeco build --mode sample
test:
	$(PY) -m pytest -q
lint:
	ruff check src tests
clean:
	rm -rf outputs/official outputs/sample .pytest_cache
