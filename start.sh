#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "$ROOT/deployment/env.sh"
LAUNCHER="$ROOT/Strata/run-deepseek-1017.sh"
if [[ ! -x "$LAUNCHER" ]]; then
  echo 'Generated launcher is missing; run bash install.sh first.' >&2
  exit 1
fi
exec "$LAUNCHER" "$@"
