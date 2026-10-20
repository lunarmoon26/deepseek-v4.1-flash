"""Manual, local-only launch/check/smoke workflow for the pinned 1017 pack."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import socket
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
ENGINE_ROOT = ROOT / 'Strata'
sys.path.insert(0, str(ENGINE_ROOT))
DATA = Path(os.environ.get('STRATA_DATA_DIR', ROOT / 'Strata-data')).expanduser().resolve()
REVISION = '22205b9aff07ae7b999d466aaf96446c20f4ea97'
MODEL = (DATA / 'models/sudoingx-DeepSeek-V4.1-Flash-1017-EXL3-2.7bpw' / REVISION).resolve()
PACK = (DATA / 'packs/sudoingx-1017-22205b9a-EXL3-2.7bpw-dspark').resolve()
MODEL_ID = 'deepseek-v4.1-flash-1017'
GPUS = os.environ.get('DS41_CUDA_VISIBLE_DEVICES', os.environ.get('CUDA_VISIBLE_DEVICES', '0,1'))


def configuration():
    spec = os.environ.get('DS41_SPEC', 'none')
    parallel = int(os.environ.get('DS41_PARALLEL', '1'))
    if spec not in ('none', 'suffix', 'dspark') or not 1 <= parallel <= 4:
        raise ValueError('DS41_SPEC must be none|suffix|dspark; DS41_PARALLEL must be 1..4')
    built = ENGINE_ROOT / 'build-sm120-serving/bin/ds41_serve'
    if not built.exists():
        built = ENGINE_ROOT / 'build-sm120-split/bin/ds41_serve'
    exe = Path(os.environ.get('DS41_ENGINE', built)).resolve()
    return {
        'format': 'deepseek_v41', 'model_name': MODEL_ID, 'aliases': ['strata'],
        'tokenizer': str(MODEL), 'exe': str(exe), 'cwd': str(ENGINE_ROOT),
        'args': ['--pack', str(PACK), '--devices', '0,1', '--split-layer', '18',
                 '--max-context', '524288', '--threads', '2', '--ram-budget-gib', '0',
                 '--adapt-every', '0', '--vram-slots', '-1', '--vram-reserve-mib', '1024',
                 '--prefill-chunk', '1024', '--prefill-batch', '256', '--snapshots', '4',
                 '--batch', str(parallel if parallel > 1 else 0), '--spec', spec],
        'parallel': parallel, 'sampling': {'temperature': 0},
        'telemetry_gpus': [int(x) for x in os.environ.get('DS41_TELEMETRY_GPUS', '0,1').split(',')],
        'host': '127.0.0.1', 'log': str(ROOT / 'logs/engine.log'),
    }


def check(cfg):
    if not DATA.is_dir():
        raise ValueError('Data directory is missing; configure STRATA_DATA_DIR in .env')
    if not Path(cfg['exe']).is_file():
        raise ValueError(f"engine is missing: {cfg['exe']}; run bash build-local.sh")
    info = dict(line.split(None, 1) for line in (PACK / 'pack_info.txt').read_text().splitlines() if line.strip())
    if info.get('finished') != '1' or Path(info.get('source', '')).resolve() != MODEL:
        raise ValueError('pack is unfinished or not from the pinned sudoingx checkpoint')
    for name in ('dense.bin', 'experts.bin', 'mtp_experts.bin', 'engram.txt', 'engram_hash.txt', 'index.txt'):
        if not (PACK / name).is_file():
            raise ValueError(f'pack file missing: {name}')
    for name in ('model-00047-of-00048.safetensors', 'model-00048-of-00048.safetensors'):
        p = MODEL / name
        if not p.is_file() or p.is_symlink():
            raise ValueError(f'Engram shard is missing or still symlink-dependent: {p}')
    from serve.deepseek import DeepSeekTokenizer
    tok = DeepSeekTokenizer(MODEL)
    if tok.eos_id != 1:
        raise ValueError('wrong tokenizer EOS')
    print(f'Checked: {MODEL_ID}, published EXL3 bytes, two-GPU layer-18 split, 524288 capacity', flush=True)


def request(port, path, body=None):
    key = os.environ.get('STRATA_API_KEY')
    headers = {'Content-Type': 'application/json'}
    if key:
        headers['Authorization'] = 'Bearer ' + key
    req = urllib.request.Request(f'http://127.0.0.1:{port}{path}',
                                 None if body is None else json.dumps(body).encode(), headers)
    with urllib.request.urlopen(req, timeout=180) as response:
        return json.load(response)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('action', choices=['check', 'start', 'smoke', 'config'])
    ap.add_argument('--port', type=int, default=int(os.environ.get('DS41_PORT', '8081')))
    a = ap.parse_args()
    if a.action == 'smoke':
        health = request(a.port, '/health')
        assert health['loaded'] and health['max_context'] == 524288, health
        models = request(a.port, '/v1/models')
        assert any(m['id'] == MODEL_ID for m in models['data']), models
        result = request(a.port, '/v1/chat/completions', {
            'model': MODEL_ID, 'messages': [{'role': 'user', 'content': 'What is 17 * 19? Reply with only the integer.'}],
            'temperature': 0, 'max_tokens': 128, 'chat_template_kwargs': {'enable_thinking': False}})
        assert result['choices'][0]['message']['content'].strip() == '323', result
        print(json.dumps({'status': 'pass', 'health': health, 'answer': '323'}, indent=2))
        return
    cfg = configuration()
    if a.action == 'config':
        print(json.dumps(cfg, indent=2)); return
    check(cfg)
    if a.action == 'check':
        return
    # Refuse a second launch before loading either GPU. The shell's flock also
    # serializes native and Docker launches from this project.
    with socket.socket() as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(('127.0.0.1', a.port))
    (ROOT / 'logs').mkdir(exist_ok=True)
    config = ROOT / 'logs/strata-runtime.json'
    config.write_text(json.dumps(cfg, indent=2) + '\n')
    os.environ['CUDA_VISIBLE_DEVICES'] = GPUS
    os.environ['DS41_ROUTE_TAIL_SKIP'] = os.environ['DS41_SSD_TAIL_SKIP'] = '0'
    os.environ['DS41_GRAPH'] = '1'
    print(f'Starting http://127.0.0.1:{a.port}; spec={os.environ.get("DS41_SPEC", "none")}; Ctrl+C stops it.', flush=True)
    os.chdir(ENGINE_ROOT)
    os.execv(sys.executable, [sys.executable, '-m', 'serve.server', '--engine', 'strata',
                            '--config', str(config), '--host', '127.0.0.1', '--port', str(a.port)])


if __name__ == '__main__':
    sys.path.insert(0, str(ROOT))
    try:
        main()
    except (ValueError, OSError, AssertionError) as e:
        raise SystemExit(str(e))
