#!/usr/bin/env bash
# Start RefiMatch API for live demos (mock LLM, in-memory RAG — no API keys or Postgres).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
API="$ROOT/services/api"

cd "$API"

if [[ ! -d .venv ]]; then
  echo "Creating virtualenv and installing dependencies…"
  python3 -m venv .venv
  # shellcheck disable=SC1091
  source .venv/bin/activate
  python -m pip install -U pip
  python -m pip install -e "$ROOT/packages/scoring" -e "$ROOT/services/agent" -r requirements.txt
else
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

export PYTHONPATH=.
export REFIMATCH_LLM_MOCK=1
export REFIMATCH_RAG_BACKEND=memory

echo ""
echo "RefiMatch demo API"
echo "  Web demo      : http://127.0.0.1:8080"
echo "  Swagger UI   : http://127.0.0.1:8080/docs"
echo "  Health       : http://127.0.0.1:8080/health"
echo ""
echo "One-shot demo  : curl -s -X POST http://127.0.0.1:8080/v1/demo/run -H 'Content-Type: application/json' -d '{}'"
echo "iOS app        : Open ios/RefiMatch/Package.swift in Xcode → iPhone Simulator"
echo "Web demo       : http://127.0.0.1:8080 (same as API — no extra setup)"
echo ""

exec python -m uvicorn app.main:app --host 0.0.0.0 --port 8080
