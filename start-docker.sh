#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "$ROOT/deployment/env.sh"
if [[ -z "${STRATA_DATA_DIR:-}" || "$STRATA_DATA_DIR" != /* || ! -d "$STRATA_DATA_DIR" ]]; then
  echo 'Set STRATA_DATA_DIR in .env to the mounted absolute data directory.' >&2
  exit 1
fi
mkdir -p "$ROOT/logs"
docker --context default compose -f "$ROOT/compose.yaml" up --no-build -d --wait --wait-timeout 300 "$@"
echo 'Strata is ready: http://127.0.0.1:8081/v1'
echo 'Logs: docker --context default compose logs -f'
