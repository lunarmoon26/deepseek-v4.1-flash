"""Offline checks for Maya launcher delegation and the shared service lock."""
import fcntl
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
        for name in ("build-local.sh", "install.sh", "start.sh", "check.sh", "smoke-test.sh", "deployment/env.sh"):
            shutil.copyfile(ROOT / name, root / name)
        return root

    def test_explicit_environment_overrides_local_file(self):
        with tempfile.TemporaryDirectory() as d:
            root = self.project(d)
            (root / ".env").write_text("MAYA_CONTEXT=65536\nMAYA_SPEC=none\nMAYA_PREFILL_CHUNK=512\n")
            command = 'ROOT="$1"; source "$2"; printf "%s %s %s" "$MAYA_CONTEXT" "$MAYA_SPEC" "$MAYA_PREFILL_CHUNK"'
            result = subprocess.run(["bash", "-c", command, "test", str(root), str(root / "deployment/env.sh")],
                                    env={**os.environ, "MAYA_CONTEXT": "32768", "MAYA_PREFILL_CHUNK": "2048"},
                                    capture_output=True, text=True, check=True)
            self.assertEqual(result.stdout, "32768 none 2048")

    def test_wrappers_delegate_to_maya_helper(self):
        with tempfile.TemporaryDirectory() as d:
            root = self.project(d)
            helper = root / "deployment/maya_local.py"
            helper.write_text("import sys; print(sys.argv[1])\n")
            for wrapper, action in (("install.sh", "install"), ("check.sh", "check"),
                                    ("smoke-test.sh", "smoke"), ("start.sh", "serve")):
                result = subprocess.run(["bash", str(root / wrapper)],
                                        env={**os.environ, "MAYA_PYTHON": sys.executable},
                                        capture_output=True, text=True, check=True)
                self.assertEqual(result.stdout.strip(), action)

    def test_start_refuses_a_held_service_lock(self):
        with tempfile.TemporaryDirectory() as d:
            root = self.project(d)
            (root / "deployment/maya_local.py").write_text("raise SystemExit(42)\n")
            (root / "logs").mkdir()
            with (root / "logs/service.lock").open("a+") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                result = subprocess.run(["bash", str(root / "start.sh")],
                                        env={**os.environ, "MAYA_PYTHON": sys.executable}, capture_output=True)
            self.assertEqual(result.returncode, 73)

    def test_build_uses_pinned_maya_target(self):
        with tempfile.TemporaryDirectory() as d:
            root = self.project(d)
            tool_dir = root / "tools"
            tool_dir.mkdir()
            git = tool_dir / "git"
            git.write_text("#!/bin/sh\ncase \"$*\" in *rev-parse*) "
                           "printf '%s\\n' c4effee67cb95fb4303720919b075fddf04b4e69;; esac\n")
            git.chmod(0o700)
            receipt = root / "build.jsonl"
            tool = tool_dir / "tool"
            tool.write_text(f'#!{sys.executable}\nimport json,sys\n'
                            f'with open({str(receipt)!r}, "a") as out: out.write(json.dumps(sys.argv[1:])+"\\n")\n')
            tool.chmod(0o700)
            source, engine = root / "source", root / "build/maya-ds4"
            env = {**os.environ, "PATH": str(tool_dir) + os.pathsep + os.environ["PATH"],
                   "MAYA_SOURCE_DIR": str(source), "MAYA_ENGINE": str(engine),
                   "DS41_CMAKE": str(tool), "DS41_NINJA": str(tool), "CUDACXX": str(tool), "DS41_BUILD_JOBS": "3"}
            subprocess.run(["bash", str(root / "build-local.sh")], env=env, capture_output=True, check=True)
            configure, build = [json.loads(line) for line in receipt.read_text().splitlines()]
            self.assertEqual(configure[configure.index("-S") + 1], str(source))
            self.assertEqual(configure[configure.index("-B") + 1], str(engine.parent))
            self.assertIn("-DFETCHCONTENT_FULLY_DISCONNECTED=ON", configure)
            self.assertIn("-DMAYA_ENABLE_CUDA=ON", configure)
            self.assertIn("-DMAYA_NATIVE_EXPERTS=OFF", configure)
            self.assertEqual(build, ["--build", str(engine.parent), "--target", "maya-ds4", "--parallel", "3"])

    def test_provider_matches_initial_capacity(self):
        cfg = json.loads((ROOT / "deployment/opencode-provider.json").read_text())
        model = cfg["models"]["deepseek-v4.1-flash-1017"]
        self.assertEqual(model["limit"], {"context": 32768, "input": 24568, "output": 8192})

    def test_container_config_does_not_overwrite_native_config(self):
        env = {**os.environ, "MAYA_CONTAINER": "1", "PYTHONDONTWRITEBYTECODE": "1"}
        result = subprocess.run([sys.executable, "-c", "from deployment.maya_local import CONFIG; print(CONFIG.name)"],
                                cwd=ROOT, env=env, capture_output=True, text=True, check=True)
        self.assertEqual(result.stdout.strip(), "maya-deepseek-1017.docker.json")


if __name__ == "__main__":
    unittest.main()
