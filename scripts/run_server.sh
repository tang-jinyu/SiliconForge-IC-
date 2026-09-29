#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

HOST="${DIGITAL_IC_AGENT_HOST:-0.0.0.0}"
PORT="${DIGITAL_IC_AGENT_PORT:-8000}"
exec .venv/bin/python -m digital_ic_agent serve --host "$HOST" --port "$PORT"
