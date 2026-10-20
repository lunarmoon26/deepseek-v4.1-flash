#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "$ROOT/deployment/env.sh"
exec "${DS41_PYTHON:-$ROOT/.venv/bin/python}" "$ROOT/deployment/local_serve.py" check "$@"
