"""CPU-only checks for portable configuration and private local defaults."""
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class LauncherTests(unittest.TestCase):
    def module(self, env):
        spec = importlib.util.spec_from_file_location('local_serve_under_test', ROOT / 'deployment/local_serve.py')
        module = importlib.util.module_from_spec(spec)
        with patch.dict(os.environ, env, clear=True):
            spec.loader.exec_module(module)
        return module

    def test_data_and_gpu_configuration_are_portable(self):
        with tempfile.TemporaryDirectory() as d:
            env = {'STRATA_DATA_DIR': d, 'DS41_CUDA_VISIBLE_DEVICES': '1,0',
                   'DS41_TELEMETRY_GPUS': '0,1'}
            module = self.module(env)
            with patch.dict(os.environ, env, clear=True):
                cfg = module.configuration()
            self.assertEqual(module.DATA, Path(d).resolve())
            self.assertTrue(module.MODEL.is_relative_to(Path(d)))
            self.assertTrue(module.PACK.is_relative_to(Path(d)))
            self.assertEqual(module.GPUS, '1,0')
            self.assertEqual(cfg['telemetry_gpus'], [0, 1])
            self.assertEqual(cfg['host'], '127.0.0.1')
            self.assertEqual(cfg['args'][cfg['args'].index('--split-layer') + 1], '18')

    def test_invalid_serving_options_are_rejected(self):
        module = self.module({})
        for env in ({'DS41_SPEC': 'unknown'}, {'DS41_PARALLEL': '0'}, {'DS41_PARALLEL': '5'}):
            with patch.dict(os.environ, env, clear=True), self.assertRaises(ValueError):
                module.configuration()

    def test_local_defaults_preserve_explicit_environment(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / '.env').write_text('DS41_PORT=1234\nDS41_PARALLEL=2\n')
            command = 'ROOT="$1"; source "$2"; printf "%s %s" "$DS41_PORT" "$DS41_PARALLEL"'
            result = subprocess.run(['bash', '-c', command, 'test', d, str(ROOT / 'deployment/env.sh')],
                                    env={**os.environ, 'DS41_PORT': '4321'}, capture_output=True,
                                    text=True, check=True)
            self.assertEqual(result.stdout, '4321 2')


if __name__ == '__main__':
    unittest.main()
