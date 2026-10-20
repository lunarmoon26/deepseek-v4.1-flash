#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "$ROOT/deployment/env.sh"
export PATH="$ROOT/.venv/bin:$PATH"
CMAKE="${DS41_CMAKE:-$(command -v cmake || true)}"
NINJA="${DS41_NINJA:-$(command -v ninja || true)}"
NVCC="${CUDACXX:-$(command -v nvcc || true)}"
for tool in "$CMAKE" "$NINJA" "$NVCC"; do
  if [[ ! -x "$tool" ]]; then
    echo 'CMake, Ninja and a compatible CUDA compiler are required; see README.md.' >&2
    exit 1
  fi
done
"$CMAKE" -S "$ROOT/deployment/cmake" -B "$ROOT/Strata/build-sm120-serving" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_CUDA_ARCHITECTURES=120 \
  -DCMAKE_MAKE_PROGRAM="$NINJA" \
  -DCMAKE_CUDA_COMPILER="$NVCC" \
  -DSTRATA_DS41_SOURCE="$ROOT/Strata" -DSTRATA_DS41_1017=ON -DSTRATA_DS41_STAGE_TESTS=ON
exec "$CMAKE" --build "$ROOT/Strata/build-sm120-serving" --target ds41_serve ds41_generate --parallel "${DS41_BUILD_JOBS:-2}"
