# Local DeepSeek V4.1 Flash deployment

- `Strata/` is the forked engine Git repository, including its local changes and
  build outputs. Follow `Strata/AGENTS.md` when editing engine code.
- Root launchers, `deployment/`, and `compose.yaml` own deployment. `logs/`,
  `Strata-data/`, `.env`, and `.venv/` are local artifacts and must not be committed.
- Only the pinned sudoingx DeepSeek V4.1 Flash **1017 2.7 bpw EXL3** release is a
  supported deployment target. Never requantize pretrained weights.
- Keep the listener on `127.0.0.1`; never expose it without an API key.
- Keep model/pack files in the configured data directory. No automatic model
  downloads, background boot services, or simultaneous model-sized GPU tests.
- Launch/check with `bash check.sh`, `bash start.sh`, `bash smoke-test.sh`.
  Docker uses the native daemon (`docker --context default compose`).
- Historical measurements remain in ignored local validation storage;
  do not silently overwrite failed receipts or publish private paths/device IDs.
