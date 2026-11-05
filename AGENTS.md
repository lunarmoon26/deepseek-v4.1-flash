# Local DeepSeek V4.1 Flash deployment

- `Strata/` is the forked engine Git repository, including its local changes and
  build outputs. Follow `Strata/AGENTS.md` when editing engine code.
- Root launchers, `deployment/`, and `compose.yaml` own deployment. `logs/`,
  `Strata-data/`, `.env`, and `.venv/` are local artifacts and must not be committed.
- The root launchers select Project Maya v1.1.55
  (`c4effee67cb95fb4303720919b075fddf04b4e69`) with the existing LibertAIDAI
  **1017 2.9 bpw EXL3** model at revision
  `c178a01284fc5c0e859d8668cffaac81ca8f4042`. The initial context capacity is
  32,768; the measured local installation retains 524,288 capacity and chunk
  4096, tested with actual inputs through 32,768 tokens. Actual 512K inputs
  and broad model quality remain unqualified. See `docs/maya-prefill-analysis.md`.
  Never requantize pretrained weights.
- Keep the listener on `127.0.0.1`; never expose it without an API key.
- Keep model/pack files in the configured data directory. No automatic model
  downloads, background boot services, or simultaneous model-sized GPU tests.
- The two shared Engram shards live under `models/DeepSeek-V4.1-Flash-1017-Engram/`
  in that directory. Maya links to them there; old source paths also remain as
  hard links to the same shards. Preserve the shared shards and Maya's links.
  The other 2.7 source weights and both 2.7 packs have been removed; 2.7 source
  metadata and the download cache have been retained.
- Launch/check with `bash check.sh`, `bash start.sh`, `bash smoke-test.sh`.
  Docker uses the native daemon (`docker --context default compose`).
- Historical measurements remain in ignored local validation storage;
  do not silently overwrite failed receipts or publish private paths/device IDs.
