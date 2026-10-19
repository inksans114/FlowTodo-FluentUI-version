import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import supervision_environment as environment


class EnvironmentTests(unittest.TestCase):
    def test_missing_dependencies_name_the_actual_environment(self):
        with patch.object(environment, "package_issue", side_effect=lambda name: "当前启动环境未安装 " + name):
            state = environment.availability()
        self.assertFalse(state["camera"])
        self.assertFalse(state["screen"])
        self.assertIn("mediapipe", state["cameraReason"])
        self.assertEqual(state["interpreter"], sys.executable)
        self.assertIn("setup_supervision.py", state["repairCommand"])

    def test_loaded_compiled_module_does_not_need_import_spec(self):
        with patch.dict(sys.modules, {"fixture_compiled": SimpleNamespace(__spec__=None)}):
            self.assertEqual(environment.package_issue("fixture_compiled"), "")

    def test_model_files_missing_report_exact_names(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(environment, "MODEL_DIR", Path(folder)), patch.object(environment, "package_issue", return_value=""):
                state = environment.availability()
        self.assertFalse(state["camera"])
        for name in environment.MODEL_FILES:
            self.assertIn(name, state["cameraReason"])

    def test_one_broken_dependency_does_not_skip_the_other(self):
        def importer(name):
            if name == "mediapipe":
                raise OSError("missing native DLL")
            return SimpleNamespace()
        with patch.dict(environment.IMPORT_ERRORS, {}, clear=True), patch.object(environment.importlib, "import_module", side_effect=importer) as load:
            environment.bootstrap()
            self.assertEqual(load.call_count, 2)
            self.assertIn("missing native DLL", environment.package_issue("mediapipe"))
            self.assertNotIn("rapidocr_onnxruntime", environment.IMPORT_ERRORS)

    def test_old_pillow_cannot_claim_screen_support(self):
        with patch.object(environment, "package_issue", return_value=""), patch.object(environment.sys, "platform", "win32"), patch("PIL.ImageGrab.grab", lambda bbox=None: None):
            state = environment.availability()
        self.assertFalse(state["screen"])
        self.assertIn("Pillow 11.2", state["screenReason"])


if __name__ == "__main__":
    unittest.main()
