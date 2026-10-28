"""Configure, check and serve the existing DeepSeek 1017 Maya assets offline."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "logs" / ("maya-deepseek-1017.docker.json" if os.environ.get("MAYA_CONTAINER") == "1"
                           else "maya-deepseek-1017.json")
OWNER = "deepseek-v4.1-flash/deployment/maya_local.py"
MAYA_REVISION = "249f9a87d1a9d72bec2b684d704b0aa9296b1c9c"
MODEL_REVISION = "c178a01284fc5c0e859d8668cffaac81ca8f4042"
MODEL_SOURCE = "LibertAIDAI-DeepSeek-V4.1-Flash-1017-EXL3-2.9bpw"
MODEL_ID = "deepseek-v4.1-flash-1017"
CONTEXTS = (32768, 65536, 131072, 262144, 524288, 1048576)
ENGRAM = {"model-00047-of-00048.safetensors", "model-00048-of-00048.safetensors"}


def absolute(value: str, label: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise ValueError(f"{label} must be an absolute path")
    return path.resolve()


def config_from_env() -> dict:
    data = absolute(os.environ.get("STRATA_DATA_DIR", str(ROOT / "Strata-data")), "STRATA_DATA_DIR")
    source = absolute(os.environ.get("MAYA_SOURCE_DIR", str(ROOT / "Project-Maya")), "MAYA_SOURCE_DIR")
    engine = absolute(os.environ.get("MAYA_ENGINE", str(data / "builds/project-maya-249f9a87-sm120/maya-ds4")),
                      "MAYA_ENGINE")
    pack = absolute(os.environ.get("MAYA_PACK_DIR", str(data / "packs/project-maya-249f9a87-libertaidai-29")),
                    "MAYA_PACK_DIR")
    context = int(os.environ.get("MAYA_CONTEXT", "32768"))
    port = int(os.environ.get("DS41_PORT", "8081"))
    spec = os.environ.get("MAYA_SPEC", "on")
    if context not in CONTEXTS or not 1 <= port <= 65535 or spec not in ("on", "none"):
        raise ValueError("Choose a supported MAYA_CONTEXT, DS41_PORT 1–65535, and MAYA_SPEC on or none")
    gpu = os.environ.get("DS41_CUDA_VISIBLE_DEVICES", "0,1")
    devices = [item.strip() for item in gpu.split(",")]
    if len(devices) != 2 or not all(devices) or len(set(devices)) != 2:
        raise ValueError("DS41_CUDA_VISIBLE_DEVICES must select two GPUs")
    return {
        "_generated_by": OWNER,
        "_deployment": {"data_dir": str(data), "cuda_visible_devices": gpu,
                        "context": context, "spec": spec},
        "exe": str(engine), "cwd": str(source),
        "args": ["--pack", str(pack), "--gpus", "0,1", "--max-context", str(context),
                 "--reserve-mib", "4096", "--cpu-threads", "8", "--mmap-experts", "on",
                 "--dspark", spec, "--vision", "off", "--tp", "1", "--threads", "on",
                 "--prefill-chunk", "512", "--expert-profile", "none", "--suffix-draft", "0"],
        "tokenizer": str(pack / "tokenizer"), "model_name": MODEL_ID,
        "log": str(ROOT / "logs/maya-deepseek-1017.log"),
        "host": "127.0.0.1", "port": port, "reasoning_effort": "none", "open_browser": False,
    }


def validate(cfg: dict) -> None:
    """Check identity and small metadata; never map or read the model tensors."""
    keys = {"_generated_by", "_deployment", "exe", "cwd", "args", "tokenizer", "model_name", "log",
            "host", "port", "reasoning_effort", "open_browser"}
    if (set(cfg) != keys or cfg.get("_generated_by") != OWNER or cfg.get("host") != "127.0.0.1" or
            cfg.get("model_name") != MODEL_ID or cfg.get("reasoning_effort") != "none" or
            cfg.get("open_browser") is not False or cfg.get("log") != str(ROOT / "logs/maya-deepseek-1017.log")):
        raise ValueError("Unrecognized Maya configuration; rerun bash install.sh")
    deploy = cfg["_deployment"]
    if set(deploy) != {"data_dir", "cuda_visible_devices", "context", "spec"}:
        raise ValueError("Unrecognized Maya deployment settings; rerun bash install.sh")
    data = absolute(deploy["data_dir"], "data directory")
    source = absolute(cfg["cwd"], "Maya source")
    engine = absolute(cfg["exe"], "Maya engine")
    args = cfg["args"]
    pack = absolute(args[args.index("--pack") + 1], "Maya pack")
    context = int(deploy["context"])
    spec = deploy["spec"]
    devices = [item.strip() for item in deploy["cuda_visible_devices"].split(",")]
    expected_args = ["--pack", str(pack), "--gpus", "0,1", "--max-context", str(context),
                     "--reserve-mib", "4096", "--cpu-threads", "8", "--mmap-experts", "on",
                     "--dspark", spec, "--vision", "off", "--tp", "1", "--threads", "on",
                     "--prefill-chunk", "512", "--expert-profile", "none", "--suffix-draft", "0"]
    if (args != expected_args or context not in CONTEXTS or spec not in ("on", "none") or
            not 1 <= int(cfg["port"]) <= 65535 or len(devices) != 2 or not all(devices) or
            len(set(devices)) != 2):
        raise ValueError("Maya settings differ from the installed profile; rerun bash install.sh")
    if not data.is_dir() or not pack.is_relative_to(data / "packs"):
        raise ValueError("Maya pack must be in the configured data directory")
    if not engine.is_file() or not os.access(engine, os.X_OK):
        raise ValueError("Maya engine missing or not executable")
    rev = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    if rev != MAYA_REVISION:
        raise ValueError("Maya source checkout does not match the pinned revision")
    dirty_serve = subprocess.check_output(
        ["git", "-C", str(source), "status", "--porcelain", "--untracked-files=all", "--", "serve",
         "tools/maya_names.py", "tools/maya_quants.py", "tools/strata_tokenizer.py"], text=True)
    if dirty_serve:
        raise ValueError("Maya server sources have local changes; review before serving")
    if not (source / "serve/server.py").is_file():
        raise ValueError("Maya server is missing")
    for name in ("ds4.txt", "tensors.txt", "engram.bin", "tokenizer/vocab.json", "tokenizer/merges.txt",
                 "tokenizer/tokenizer.json", "tokenizer/token_type.json", "tokenizer/chat_template.jinja"):
        if not (pack / name).is_file():
            raise ValueError(f"Maya pack is missing {name}")
    if absolute(cfg["tokenizer"], "tokenizer") != pack / "tokenizer":
        raise ValueError("Maya tokenizer does not belong to the installed pack")
    fields = dict(line.split(None, 1) for line in (pack / "ds4.txt").read_text().splitlines() if line.strip())
    model = absolute(fields["model_dir"], "model directory")
    if (not model.is_relative_to(data / "models") or model.name != MODEL_REVISION or
            model.parent.name != MODEL_SOURCE):
        raise ValueError("Maya pack does not point to the pinned 2.9-bpw model")
    indexed = set(json.loads((model / "model.safetensors.index.json").read_text())["weight_map"].values())
    packed = set()
    with (pack / "tensors.txt").open() as tensors:
        for line in tensors:
            if not line.startswith("file "):
                break
            _, index, name = line.rstrip("\n").split(maxsplit=2)
            if index != str(len(packed)) or name in packed or Path(name).name != name:
                raise ValueError("Maya pack contains an invalid shard entry")
            packed.add(name)
    # The LibertAIDAI index names 43 EXL3 shards; Maya adds the two shared
    # Engram shards separately when it writes its pack.
    if not indexed or packed != indexed | ENGRAM:
        raise ValueError("Maya pack shard list differs from the model index")
    for name in packed:
        shard = model / name
        if not shard.is_file() or not shard.resolve().is_relative_to(data / "models"):
            raise ValueError(f"Missing model shard or target outside data directory: {name}")
        if name in ENGRAM and (not shard.is_symlink() or
                shard.resolve() != data / "models/DeepSeek-V4.1-Flash-1017-Engram" / name):
            raise ValueError(f"Engram shard does not point to the shared directory: {name}")


def load_config(path: Path | None = None) -> dict:
    path = path or CONFIG
    if path.is_symlink():
        raise ValueError("Refusing a symlinked Maya config")
    cfg = json.loads(path.read_text())
    validate(cfg)
    return cfg


def install() -> None:
    cfg = config_from_env()
    validate(cfg)
    ROOT.joinpath("logs").mkdir(exist_ok=True)
    if CONFIG.is_symlink():
        raise ValueError("Refusing a symlinked Maya config")
    if CONFIG.exists():
        old = json.loads(CONFIG.read_text())
        if not isinstance(old, dict) or old.get("_generated_by") != OWNER:
            raise ValueError("Refusing to overwrite a config not owned by this installer")
        if old == cfg:
            CONFIG.chmod(0o600)
            print("Maya configuration is unchanged; no server was started.")
            return
        fd, backup = tempfile.mkstemp(prefix=CONFIG.name + ".bak-", dir=CONFIG.parent)
        os.close(fd)
        shutil.copyfile(CONFIG, backup)
    fd, temporary = tempfile.mkstemp(prefix=CONFIG.name + ".tmp-", dir=CONFIG.parent)
    try:
        with os.fdopen(fd, "w") as out:
            json.dump(cfg, out, indent=2)
            out.write("\n")
        os.chmod(temporary, 0o600)
        os.replace(temporary, CONFIG)
    finally:
        Path(temporary).unlink(missing_ok=True)
    print("Installed Maya configuration; no server was started.")


def serve(cfg: dict) -> None:
    with socket.socket() as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("127.0.0.1", cfg["port"]))
    env = os.environ.copy()
    env.update({"CUDA_VISIBLE_DEVICES": cfg["_deployment"]["cuda_visible_devices"],
                "MAYA_DS4_DISK_SKIP_W": "0", "MAYA_DS4_DISK_SKIP_AUTO": "0",
                "MAYA_DS4_RAM_SKIP_W": "0", "MAYA_DS4_SLOT_KEEP": "0", "MAYA_DS4_RAM_TIER": "0",
                "STRATA_DS4_DISK_SKIP_W": "0", "STRATA_DS4_DISK_SKIP_AUTO": "0",
                "STRATA_DS4_RAM_SKIP_W": "0", "STRATA_DS4_SLOT_KEEP": "0", "STRATA_DS4_RAM_TIER": "0",
                "DS4_YOCO": "1",
                "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1"})
    os.chdir(cfg["cwd"])
    os.execve(sys.executable, [sys.executable, "-u", "-m", "serve.server", "--engine", "strata",
                               "--config", str(CONFIG), "--host", "127.0.0.1", "--port", str(cfg["port"])], env)


def smoke(cfg: dict) -> None:
    def request(path: str, body: dict | None = None) -> dict:
        headers = {"Content-Type": "application/json"}
        if os.environ.get("STRATA_API_KEY"):
            headers["Authorization"] = "Bearer " + os.environ["STRATA_API_KEY"]
        req = urllib.request.Request(f"http://127.0.0.1:{cfg['port']}{path}",
                                     None if body is None else json.dumps(body).encode(), headers)
        with urllib.request.urlopen(req, timeout=180) as response:
            return json.load(response)
    health = request("/health")
    if health.get("status") != "ok" or health.get("unloaded") or health.get("max_context") != cfg["_deployment"]["context"]:
        raise ValueError("Server is not loaded with the installed context")
    if not any(model["id"] == MODEL_ID for model in request("/v1/models")["data"]):
        raise ValueError("Server does not advertise the installed model")
    result = request("/v1/chat/completions", {
        "model": MODEL_ID, "messages": [{"role": "user", "content": "What is 17 * 19? Reply with only the integer."}],
        "temperature": 0, "max_tokens": 128, "chat_template_kwargs": {"enable_thinking": False}})
    if result["choices"][0]["message"]["content"].strip() != "323":
        raise ValueError("Arithmetic smoke check failed")
    print(json.dumps({"status": "pass", "context": health["max_context"], "answer": "323"}))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("install", "check", "serve", "smoke"))
    action = parser.parse_args().action
    if action == "install":
        install()
        return
    cfg = load_config()
    if action == "check":
        print(f"Checked: {MODEL_ID}, pinned Maya and 2.9-bpw pack, context {cfg['_deployment']['context']}")
    elif action == "serve":
        serve(cfg)
    else:
        smoke(cfg)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, IndexError, subprocess.CalledProcessError) as error:
        raise SystemExit(str(error))
