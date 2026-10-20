# Local DeepSeek V4.1 Flash 1017 with Strata

Standalone launchers for the native [Strata-DS engine](https://github.com/lunarmoon26/Strata-DS).
The engine and its Git history live in **`Strata/`**, independently of this
deployment repository. Model-specific settings are not copied from Qwen.

## Configuration

- Only `sudoingx/DeepSeek-V4.1-Flash-1017-EXL3-2.7bpw`, revision
  `22205b9aff07ae7b999d466aaf96446c20f4ea97`.
- Two RTX PRO 6000 Blackwell GPUs, resident layers 0–17 / 18–39. The heavier
  first stage uses the headless GPU. No backbone CPU fallback or expert eviction.
- Capacity **524,288**. Published YaRN factor 16 remains unchanged.
- Models and lossless packs stay under the configured `STRATA_DATA_DIR`.
  `Strata-data/` provides convenient links; it does not duplicate weights.
- Local API and browser chat: **http://127.0.0.1:8081** (Qwen keeps `:8080`).

## Commands

Clone the pinned engine separately; it is not vendored or automatically updated:

```bash
git clone https://github.com/lunarmoon26/deepseek-v4.1-flash.git
cd deepseek-v4.1-flash
git clone https://github.com/lunarmoon26/Strata-DS.git Strata
git -C Strata checkout --detach ccd8cf28e4d72095fef96e00114105b52afc55d4
python3 -m venv .venv
.venv/bin/pip install -r deployment/requirements.txt
cp .env.example .env
```

Edit `.env` with your **absolute data directory**, CUDA device order and optional
tool paths. Use a CUDA toolkit compatible with SM120 (the native build was
validated with CUDA 13.4 and GCC 15). No model download or quantization is run by
these commands. The pinned source identity is in `deployment/strata-source.json`.

Provision the verified source model and lossless pack under this data layout:

```text
STRATA_DATA_DIR/
  models/sudoingx-DeepSeek-V4.1-Flash-1017-EXL3-2.7bpw/<pinned revision>/
  packs/sudoingx-1017-22205b9a-EXL3-2.7bpw-dspark/
```

Engram files must remain available independently of obsolete model directories.
The `-dspark` pack includes the published MTP experts; no Qwen-style standalone
`mtp/` directory is required. Optional `Strata-data/models/` and
`Strata-data/packs/` links can point to the data disk; they stay out of Git.

Then:

```bash
bash build-local.sh
bash check.sh
bash start.sh          # foreground; Ctrl+C stops it
```

In another terminal:

```bash
bash smoke-test.sh
```

OpenAI clients use `http://127.0.0.1:8081/v1`, model
`deepseek-v4.1-flash-1017` (alias `strata`). The server also exposes
`/v1/responses` and `/v1/messages`. Images are not supported. Do not tunnel or
publish the unauthenticated listener. No automatic boot service is installed.

`deployment/local_serve.py` owns configuration generation and validates the pinned
pack before launch. The wrappers load ignored `.env` defaults; explicit environment
assignments win. Python defaults to `.venv/bin/python` (`DS41_PYTHON` overrides it).
`DS41_PORT` selects a different **localhost** port. `DS41_SPEC=none|suffix|dspark`
selects greedy drafting; default `none` avoids reference-verification overhead.
`DS41_PARALLEL=2` enables two isolated concurrent sessions with serial GPU
scheduling, not fused batch acceleration. Batch decode and sampled requests use
ordinary decoding, even when a drafter is loaded. No speedup is claimed for the
snapshot/replay verifier. DSpark uses the actual published MTP weights; draft
experts alone use bounded streaming, never backbone eviction or requantization.

To rebuild the current local source: `bash build-local.sh`. No download or model
conversion occurs. CMake and Ninja are found in `.venv/bin` or `PATH`;
`DS41_CMAKE`, `DS41_NINJA` and `CUDACXX` override them. `DS41_CUDA_VISIBLE_DEVICES`
sets CUDA ordering independently of physical `DS41_TELEMETRY_GPUS` monitoring IDs.

## OpenCode

`deployment/opencode-provider.json` is a **provider fragment**, not a complete
global configuration. Merge it under `providers.strata-deepseek` in your OpenCode
configuration after making a local backup, preserving other providers and defaults.
The selectable ID is **`strata-deepseek/deepseek-v4.1-flash-1017`**, with `fast`
(thinking disabled) and `thinking` variants. Context is 524,288 total, with an
8,192-token output cap and input limited to 516,088 for the native safety margin.
No personal OpenCode configuration or backup is included here.

## Docker

```bash
docker --context default compose build
bash start-docker.sh
docker --context default compose logs -f
bash stop-docker.sh
```

Set an absolute `STRATA_DATA_DIR` in `.env` before using Compose. Builds compile
the local `Strata/` checkout for SM120 and install Python/CUDA dependencies, but
never download weights. Model and pack mounts are read-only and keep their
absolute paths for Engram row reads. Linux host networking preserves loopback
binding. The native and container launchers share a lock; do not load a competing
model onto the same GPUs simultaneously. Automatic restart is disabled. Stop removes the container, not
models, packs or images. The image builds successfully; GPU container runtime
validation is not completed. The current running service uses the validated
native launcher, not Docker.

## Validation

The real-input ladder passed at 32,768, 131,072, 262,144 and **524,256 tokens**.
The final test generated the expected `BRONZE-73921`; prefill took **531.73 s
(985.95 tokens/s)** and the complete native test took 552.90 s, with no swap/OOM
or backbone expert streaming. This is a synthetic repeated-filler retrieval
fixture, not a broad long-context benchmark or an HTTP throughput measurement.

Native serving passes real-model OpenAI streaming/nonstreaming, Responses,
Anthropic Messages, tool calls, concurrent session isolation, disconnect/recovery,
context overflow rejection and browser chat. The latest eight stage/component
CTest cases, 32 packer tests and 27 protocol/parser/cancellation tests pass.
Published DSpark execution, confidence, replay and live API arithmetic pass;
suffix mode passes the real API checks. These functional checks are not a broad
coding-agent quality benchmark or evidence that speculation is faster. The
running default therefore uses ordinary decode (`DS41_SPEC=none`).

Current measurements and limits belong to `Strata/docs/MULTI_GPU.md`. Raw local
receipts and failures are not published here. Engine changes are merged into
the fork's `main` as `ccd8cf2` ([PR #2](https://github.com/lunarmoon26/Strata-DS/pull/2)).
This repository publishes portable launchers and templates, not `.env`, device
UUIDs, private client configuration, model links, weights, builds or logs.
