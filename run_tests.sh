#!/usr/bin/env bash
# Runs every backend test with coverage inside the api container (real Postgres), then writes COVERAGE.json.
set -euo pipefail
cd "$(dirname "$0")"
export DAY1_SALT="${DAY1_SALT:-test-salt}"
docker compose up -d --build
# wait for the API (startup creates tables and seeds)
# (python inside the container, so the host needs nothing but Docker)
PY_GET='import sys,urllib.request; urllib.request.urlopen("http://localhost:8080/health", timeout=2)'
for i in $(seq 1 60); do docker compose exec -T api python -c "$PY_GET" >/dev/null 2>&1 && break; sleep 2; done
docker compose exec -T api rm -rf /srv/tests
docker compose cp tests api:/srv/tests
docker compose exec -T api python -m pytest tests/backend -q -p no:cacheprovider --cov=app --cov-report=json:/tmp/coverage.json
docker compose exec -T api python tests/coverage_areas.py /tmp/coverage.json > COVERAGE.json
# leave the stack in its baseline state for whoever uses it next
docker compose exec -T api python -c 'import urllib.request; urllib.request.urlopen(urllib.request.Request("http://localhost:8080/audit/v1/reset", data=b"", method="POST"))' >/dev/null
cat COVERAGE.json
