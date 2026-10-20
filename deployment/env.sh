# Shared local defaults. .env is ignored by Git and never baked into the image.
# Explicit environment assignments take precedence over the local file.
_ds41_keys=(STRATA_DATA_DIR DS41_PYTHON DS41_CMAKE DS41_NINJA CUDACXX
  DS41_CUDA_VISIBLE_DEVICES DS41_TELEMETRY_GPUS DS41_ENGINE DS41_PORT
  DS41_SPEC DS41_PARALLEL DS41_BUILD_JOBS)
declare -A _ds41_saved=()
for _ds41_key in "${_ds41_keys[@]}"; do
  if [[ -v "$_ds41_key" ]]; then
    _ds41_saved["$_ds41_key"]="${!_ds41_key}"
  fi
done
if [[ -f "$ROOT/.env" ]]; then
  set -a
  source "$ROOT/.env"
  set +a
fi
for _ds41_key in "${!_ds41_saved[@]}"; do
  export "$_ds41_key=${_ds41_saved[$_ds41_key]}"
done
unset _ds41_keys _ds41_saved _ds41_key
