#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "$ROOT/deployment/env.sh"
export PATH="$ROOT/.venv/bin:$PATH"
SOURCE="${MAYA_SOURCE_DIR:-$ROOT/Project-Maya}"
DATA="${STRATA_DATA_DIR:-$ROOT/Strata-data}"
ENGINE="${MAYA_ENGINE:-$DATA/builds/project-maya-c4effee-sm120/maya-ds4}"
if [[ "$(git -C "$SOURCE" rev-parse HEAD)" != c4effee67cb95fb4303720919b075fddf04b4e69 ]]; then
  echo 'Maya checkout must match the pinned revision.' >&2
  exit 1
fi
if [[ -n "$(git -C "$SOURCE" status --porcelain --untracked-files=all -- src include cmake third_party CMakeLists.txt)" ]]; then
  echo 'Maya engine source has local changes; review before building.' >&2
  exit 1
fi
CMAKE="${DS41_CMAKE:-$(command -v cmake || true)}"
NINJA="${DS41_NINJA:-$(command -v ninja || true)}"
NVCC="${CUDACXX:-$(command -v nvcc || true)}"
for tool in "$CMAKE" "$NINJA" "$NVCC"; do
  if [[ ! -x "$tool" ]]; then
    echo 'CMake, Ninja and a compatible CUDA compiler are required; see README.md.' >&2
    exit 1
  fi
done
"$CMAKE" -S "$SOURCE" -B "$(dirname "$ENGINE")" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_CUDA_ARCHITECTURES=120 \
  -DCMAKE_MAKE_PROGRAM="$NINJA" \
  -DCMAKE_CUDA_COMPILER="$NVCC" \
  -DMAYA_ENABLE_CUDA=ON -DMAYA_BUILD_TESTS=OFF -DMAYA_NATIVE_EXPERTS=OFF \
  -DFETCHCONTENT_FULLY_DISCONNECTED=ON
exec "$CMAKE" --build "$(dirname "$ENGINE")" --target maya-ds4 --parallel "${DS41_BUILD_JOBS:-2}"
