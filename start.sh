#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "$ROOT/deployment/env.sh"
mkdir -p "$ROOT/logs"
exec flock --no-fork -n -E 73 "$ROOT/logs/service.lock" \
  "${MAYA_PYTHON:-${DS41_PYTHON:-$ROOT/.venv/bin/python}}" "$ROOT/deployment/maya_local.py" serve "$@"
