#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "$ROOT/deployment/env.sh"
if [[ ! -f "$ROOT/Strata/tools/setup_deepseek_1017.py" ]]; then
  echo 'This engine checkout lacks the native 1017 setup profile; use the reviewed integration revision.' >&2
  exit 1
fi
export STRATA_PYTHON="${DS41_PYTHON:-$ROOT/.venv/bin/python}"
args=(--family deepseek --model 1017-EXL3-2.7BPW --configure-only
  --data-dir "${STRATA_DATA_DIR:-$ROOT/Strata-data}" --log-dir "$ROOT/logs"
  --gpus "${DS41_CUDA_VISIBLE_DEVICES:-${CUDA_VISIBLE_DEVICES:-0,1}}"
  --telemetry-gpus "${DS41_TELEMETRY_GPUS:-0,1}"
  --port "${DS41_PORT:-8081}" --parallelism layer --spec "${DS41_SPEC:-dspark}"
  --parallel "${DS41_PARALLEL:-1}" --context 524288 --no-start --no-browser)
if [[ -n "${DS41_ENGINE:-}" ]]; then args+=(--ds41-engine "$DS41_ENGINE"); fi
exec bash "$ROOT/Strata/setup.sh" "${args[@]}" "$@"
