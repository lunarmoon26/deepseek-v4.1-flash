"""Deployment wrappers delegate to the fork; no model or GPU use."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class LauncherTests(unittest.TestCase):
    def project(self, directory):
        root = Path(directory) / "project with 'quotes'"
        (root / "deployment").mkdir(parents=True)
        (root / "Strata/tools").mkdir(parents=True)
        for name in ("build-local.sh", "install.sh", "start.sh", "check.sh", "smoke-test.sh", "deployment/env.sh"):
            shutil.copyfile(ROOT / name, root / name)
        return root

    def test_local_defaults_preserve_explicit_environment(self):
        with tempfile.TemporaryDirectory() as d:
            root = self.project(d)
            (root / ".env").write_text("DS41_PORT=1234\nDS41_PARALLEL=2\n")
            command = 'ROOT="$1"; source "$2"; printf "%s %s" "$DS41_PORT" "$DS41_PARALLEL"'
            result = subprocess.run(["bash", "-c", command, "test", str(root), str(root / "deployment/env.sh")],
                                    env={**os.environ, "DS41_PORT": "4321"}, capture_output=True, text=True, check=True)
            self.assertEqual(result.stdout, "4321 2")

    def test_build_uses_native_resident_targets_without_downloads(self):
        with tempfile.TemporaryDirectory() as d:
            root = self.project(d)
            receipt = root / "build.jsonl"
            tool = root / "fake-tool"
            tool.write_text(f'#!{sys.executable}\nimport json,sys\n'
                            f'with open({str(receipt)!r}, "a") as out: out.write(json.dumps(sys.argv[1:])+"\\n")\n')
            tool.chmod(0o700)
            subprocess.run(["bash", str(root / "build-local.sh")], check=True,
                           env={**os.environ, "DS41_CMAKE": str(tool), "DS41_NINJA": str(tool),
                                "CUDACXX": str(tool), "DS41_BUILD_JOBS": "3"}, capture_output=True)
            configure, build = [json.loads(line) for line in receipt.read_text().splitlines()]
            self.assertEqual(configure[configure.index("-S") + 1], str(root / "Strata"))
            self.assertEqual(configure[configure.index("-B") + 1], str(root / "Strata/build-sm120-resident"))
            for option in ("-DSTRATA_ENABLE_DS41=ON", "-DSTRATA_DS41_STANDALONE=ON",
                           "-DFETCHCONTENT_FULLY_DISCONNECTED=ON", "-DSTRATA_DS41_STAGE_TESTS=ON"):
                self.assertIn(option, configure)
            self.assertEqual(build, ["--build", str(root / "Strata/build-sm120-resident"), "--parallel", "3"])

    def test_installer_forwards_native_profile_options_without_writing_config(self):
        with tempfile.TemporaryDirectory() as d:
            root = self.project(d)
            receipt = root / "receipt.json"
            (root / "Strata/tools/setup_deepseek_1017.py").touch()
            (root / "Strata/setup.sh").write_text(
                f'#!/bin/sh\nexec "$STRATA_PYTHON" -c \'import json,sys; '
                f'from pathlib import Path; Path(sys.argv[1]).write_text(json.dumps(sys.argv[2:]))\' '
                f'"{receipt}" "$@"\n')
            result = subprocess.run(["bash", str(root / "install.sh")], env={**os.environ,
                                     "DS41_PYTHON": sys.executable, "DS41_CUDA_VISIBLE_DEVICES": "1,0",
                                     "DS41_SPEC": "",
                                     "DS41_ENGINE": str(root / "engine")}, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            args = json.loads(receipt.read_text())
            for flag, value in (("--family", "deepseek"), ("--model", "1017-EXL3-2.7BPW"),
                                ("--gpus", "1,0"), ("--log-dir", str(root / "logs")),
                                ("--ds41-engine", str(root / "engine")),
                                ("--parallelism", "layer"), ("--spec", "dspark")):
                self.assertEqual(args[args.index(flag) + 1], value)
            self.assertIn("--configure-only", args)
            self.assertIn("--no-start", args)
            self.assertFalse((root / "Strata/strata-deepseek-1017.json").exists())
            subprocess.run(["bash", str(root / "install.sh")], env={**os.environ,
                           "DS41_PYTHON": sys.executable, "DS41_SPEC": "none"},
                           capture_output=True, check=True)
            args = json.loads(receipt.read_text())
            self.assertEqual(args[args.index("--spec") + 1], "none")

    def test_start_requires_install_and_delegates_without_python(self):
        with tempfile.TemporaryDirectory() as d:
            root = self.project(d)
            command = ["bash", str(root / "start.sh")]
            self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)
            launcher = root / "Strata/run-deepseek-1017.sh"
            launcher.write_text("#!/bin/sh\nexit 73\n")
            launcher.chmod(0o700)
            self.assertEqual(subprocess.run(command, capture_output=True).returncode, 73)

    def test_installer_refuses_an_older_fork_before_bootstrap(self):
        with tempfile.TemporaryDirectory() as d:
            root = self.project(d)
            (root / "Strata/setup.sh").write_text("#!/bin/sh\nexit 42\n")
            result = subprocess.run(["bash", str(root / "install.sh")], capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn("lacks the native 1017 setup profile", result.stderr)

    def test_checks_use_native_helper(self):
        with tempfile.TemporaryDirectory() as d:
            root = self.project(d)
            helper = root / "Strata/tools/setup_deepseek_1017.py"
            helper.write_text("import sys; print(sys.argv[1])\n")
            for wrapper, action in (("check.sh", "check"), ("smoke-test.sh", "smoke")):
                result = subprocess.run(["bash", str(root / wrapper)],
                                        env={**os.environ, "DS41_PYTHON": sys.executable},
                                        capture_output=True, text=True, check=True)
                self.assertEqual(result.stdout.strip(), action)


if __name__ == "__main__":
    unittest.main()
