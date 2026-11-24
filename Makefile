# Shortcuts: `make serve` (live preview), `make dev` (fake players), `make real` (your sample-data/ copy), `make test`.
.PHONY: serve dev real test

serve:
	MC_SERVER_DIR=$(CURDIR)/tests/fixtures python3 -m mcstats serve --out out --port 8000

dev:
	MC_SERVER_DIR=$(CURDIR)/tests/fixtures python3 -m mcstats build --out out && open out/index.html

real:
	MC_SERVER_DIR=$(CURDIR)/sample-data python3 -m mcstats build --out out && open out/index.html

test:
	python3 -m unittest
	shellcheck deploy/*.sh
