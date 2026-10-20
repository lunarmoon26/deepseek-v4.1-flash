#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "$ROOT/deployment/env.sh"
exec "${DS41_PYTHON:-$ROOT/.venv/bin/python}" "$ROOT/Strata/tools/setup_deepseek_1017.py" smoke "$@"
