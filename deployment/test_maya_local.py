"""Offline tests for the Maya deployment contract; no model or GPU needed."""
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from deployment import maya_local as maya


class MayaDeploymentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "logs").mkdir()
        self.data = self.root / "data"
        self.model = self.data / "models" / maya.MODEL_SOURCE / maya.MODEL_REVISION
        self.model.mkdir(parents=True)
        self.shared = self.data / "models/DeepSeek-V4.1-Flash-1017-Engram"
        self.shared.mkdir()
        self.pack = self.data / "packs/maya"
        self.pack.mkdir(parents=True)
        self.source = self.root / "maya-source"
        (self.source / "serve").mkdir(parents=True)
        (self.source / "serve/server.py").touch()
        self.engine = self.root / "maya-ds4"
        self.engine.write_text("engine")
        self.engine.chmod(0o700)
        (self.model / "model-00001.safetensors").write_bytes(b"x")
        (self.model / "model.safetensors.index.json").write_text(
            json.dumps({"weight_map": {"weight": "model-00001.safetensors"}}))
        for name in maya.ENGRAM:
            (self.shared / name).write_bytes(b"engram")
            (self.model / name).symlink_to(self.shared / name)
        (self.pack / "ds4.txt").write_text(f"model_dir {self.model}\n")
        names = ["model-00001.safetensors", *sorted(maya.ENGRAM)]
        (self.pack / "tensors.txt").write_text("".join(f"file {n} {name}\n" for n, name in enumerate(names)) +
                                              "t sample BF16 0 0 1 1\n")
        (self.pack / "engram.bin").write_bytes(b"hash")
        (self.pack / "tokenizer").mkdir()
        for name in ("vocab.json", "merges.txt", "tokenizer.json", "token_type.json", "chat_template.jinja"):
            (self.pack / "tokenizer" / name).write_text("x")
        self.environment = {"STRATA_DATA_DIR": str(self.data), "MAYA_SOURCE_DIR": str(self.source),
                            "MAYA_ENGINE": str(self.engine), "MAYA_PACK_DIR": str(self.pack),
                            "DS41_CUDA_VISIBLE_DEVICES": "0,1"}
        self.patches = [mock.patch.object(maya, "ROOT", self.root),
                        mock.patch.object(maya, "CONFIG", self.root / "logs/maya-deepseek-1017.json"),
                        mock.patch.dict(os.environ, self.environment, clear=True),
                        mock.patch.object(maya.subprocess, "check_output", side_effect=[maya.MAYA_REVISION + "\n", ""] * 20)]
        for patch in self.patches:
            patch.start()
            self.addCleanup(patch.stop)

    def test_default_profile_and_offline_validation(self):
        cfg = maya.config_from_env()
        maya.validate(cfg)
        self.assertEqual(cfg["_deployment"]["context"], 32768)
        self.assertEqual(cfg["_deployment"]["spec"], "on")
        self.assertEqual(cfg["host"], "127.0.0.1")
        self.assertEqual(cfg["model_name"], maya.MODEL_ID)
        self.assertEqual(cfg["args"][cfg["args"].index("--dspark") + 1], "on")
        self.assertEqual(cfg["args"][cfg["args"].index("--suffix-draft") + 1], "0")

    def test_explicit_context_and_spec_and_invalid_values(self):
        os.environ.update(MAYA_CONTEXT="524288", MAYA_SPEC="none")
        cfg = maya.config_from_env()
        maya.validate(cfg)
        self.assertEqual(cfg["_deployment"]["context"], 524288)
        self.assertEqual(cfg["_deployment"]["spec"], "none")
        os.environ["MAYA_CONTEXT"] = "32000"
        with self.assertRaises(ValueError):
            maya.config_from_env()

    def test_missing_and_outside_shards_fail_closed(self):
        cfg = maya.config_from_env()
        name = sorted(maya.ENGRAM)[0]
        (self.shared / name).unlink()
        with self.assertRaisesRegex(ValueError, "Missing model shard"):
            maya.validate(cfg)
        outside = self.root / name
        outside.write_bytes(b"external")
        (self.model / name).unlink()
        (self.model / name).symlink_to(outside)
        with self.assertRaisesRegex(ValueError, "outside data directory"):
            maya.validate(cfg)

    def test_pack_index_and_model_identity_are_checked(self):
        cfg = maya.config_from_env()
        with (self.pack / "tensors.txt").open("a") as out:
            out.write("irrelevant tensor\n")
        maya.validate(cfg)
        (self.pack / "tensors.txt").write_text("file 0 unknown.safetensors\n")
        with self.assertRaisesRegex(ValueError, "shard list differs"):
            maya.validate(cfg)
        (self.pack / "ds4.txt").write_text(f"model_dir {self.shared}\n")
        with self.assertRaisesRegex(ValueError, "pinned 2.9"):
            maya.validate(cfg)

    def test_pack_rejects_duplicate_or_out_of_order_shard_entries(self):
        cfg = maya.config_from_env()
        (self.pack / "tensors.txt").write_text("file 1 model-00001.safetensors\n")
        with self.assertRaisesRegex(ValueError, "invalid shard entry"):
            maya.validate(cfg)

    def test_remote_binding_or_modified_engine_arguments_rejected(self):
        cfg = maya.config_from_env()
        cfg["host"] = "0.0.0.0"
        with self.assertRaises(ValueError):
            maya.validate(cfg)
        cfg = maya.config_from_env()
        cfg["args"] += ["--vision", "on"]
        with self.assertRaises(ValueError):
            maya.validate(cfg)
        cfg = maya.config_from_env()
        cfg["mcp_servers"] = {"unapproved": {"command": "anything"}}
        with self.assertRaises(ValueError):
            maya.validate(cfg)

    def test_engram_must_target_the_shared_directory(self):
        name = sorted(maya.ENGRAM)[0]
        other = self.data / "models/other-engram"
        other.mkdir()
        (other / name).write_bytes(b"engram")
        (self.model / name).unlink()
        (self.model / name).symlink_to(other / name)
        with self.assertRaisesRegex(ValueError, "shared directory"):
            maya.validate(maya.config_from_env())

    def test_source_pin_and_dirty_server_rejected(self):
        cfg = maya.config_from_env()
        with mock.patch.object(maya.subprocess, "check_output", return_value="wrong-revision\n"):
            with self.assertRaisesRegex(ValueError, "pinned revision"):
                maya.validate(cfg)
        with mock.patch.object(maya.subprocess, "check_output", side_effect=[maya.MAYA_REVISION, " M serve/server.py"]):
            with self.assertRaisesRegex(ValueError, "server sources"):
                maya.validate(cfg)

    def test_install_is_private_idempotent_and_preserves_existing_files(self):
        maya.install()
        cfg = maya.load_config()
        self.assertEqual(maya.CONFIG.stat().st_mode & 0o777, 0o600)
        original = maya.CONFIG.read_bytes()
        maya.CONFIG.chmod(0o644)
        maya.install()
        self.assertEqual(maya.CONFIG.read_bytes(), original)
        self.assertEqual(maya.CONFIG.stat().st_mode & 0o777, 0o600)
        os.environ["MAYA_CONTEXT"] = "65536"
        maya.install()
        backups = list(maya.CONFIG.parent.glob(maya.CONFIG.name + ".bak-*"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), original)
        self.assertEqual(maya.load_config()["_deployment"]["context"], 65536)
        self.assertEqual(cfg["_deployment"]["context"], 32768)

    def test_install_refuses_unowned_file_and_symlink(self):
        maya.CONFIG.write_text('{"user_owned": true}')
        with self.assertRaisesRegex(ValueError, "not owned"):
            maya.install()
        self.assertEqual(maya.CONFIG.read_text(), '{"user_owned": true}')
        maya.CONFIG.unlink()
        target = self.root / "other.json"
        target.write_text("keep")
        maya.CONFIG.symlink_to(target)
        with self.assertRaisesRegex(ValueError, "symlinked"):
            maya.install()
        self.assertEqual(target.read_text(), "keep")

    def test_smoke_checks_model_context_and_optional_key(self):
        cfg = maya.config_from_env()
        os.environ["STRATA_API_KEY"] = "test-key"
        replies = [
            {"status": "ok", "max_context": 32768, "unloaded": False},
            {"data": [{"id": maya.MODEL_ID}]},
            {"choices": [{"message": {"content": "323"}}]},
        ]
        requests = []

        def urlopen(request, timeout):
            requests.append(request)
            return io.BytesIO(json.dumps(replies.pop(0)).encode())

        with mock.patch.object(maya.urllib.request, "urlopen", side_effect=urlopen):
            maya.smoke(cfg)
        self.assertEqual(len(requests), 3)
        self.assertEqual(requests[2].get_header("Authorization"), "Bearer " + os.environ["STRATA_API_KEY"])
        self.assertEqual(json.loads(requests[2].data)["model"], maya.MODEL_ID)

    def test_serve_disables_inherited_approximate_expert_skips(self):
        cfg = maya.config_from_env()
        os.environ.update(STRATA_DS4_DISK_SKIP_W="0.9", STRATA_DS4_RAM_SKIP_W="0.9", DS4_YOCO="2")
        with mock.patch.object(maya.socket, "socket"), mock.patch.object(maya.os, "chdir"), \
                mock.patch.object(maya.os, "execve") as execute:
            maya.serve(cfg)
        env = execute.call_args.args[2]
        self.assertEqual(env["STRATA_DS4_DISK_SKIP_W"], "0")
        self.assertEqual(env["STRATA_DS4_RAM_SKIP_W"], "0")
        self.assertEqual(env["DS4_YOCO"], "1")


if __name__ == "__main__":
    unittest.main()
