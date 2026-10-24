"""Verify diagnostics in child processes without altering the test runner hooks."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class RuntimeDiagnosticsTests(unittest.TestCase):
    def launch(self, directory, source):
        env = {**os.environ, "FLOWTODO_DATA_DIR": str(Path(directory) / "繁體資料" / "data")}
        result = subprocess.run([sys.executable, "-B", "-c", source], cwd=ROOT,
                                env=env, capture_output=True, timeout=30)
        logs = list((Path(directory) / "繁體資料" / "logs").glob("runtime-*.log"))
        self.assertEqual(len(logs), 1, result.stderr.decode("utf-8", errors="replace"))
        return result, logs[0].read_text(encoding="utf-8")

    def test_windowless_streams_python_and_worker_exceptions_are_captured(self):
        with tempfile.TemporaryDirectory() as directory:
            result, log = self.launch(directory, '''
import sys, threading
sys.stdout = sys.stderr = None
from runtime_diagnostics import install, checkpoint
assert install() == install()
checkpoint("windowless-ready")
def worker():
    raise RuntimeError("worker-test-error")
thread = threading.Thread(target=worker)
thread.start()
thread.join()
raise ValueError("main-test-error")
''')
        self.assertNotEqual(result.returncode, 0)
        for expected in ("windowless-ready", "Unhandled worker exception", "worker-test-error",
                         "Unhandled Python exception", "main-test-error", "Python process exit"):
            self.assertIn(expected, log)
        self.assertEqual(log.count("Process start:"), 1)

    def test_qt_messages_and_native_traceback_use_the_log(self):
        with tempfile.TemporaryDirectory() as directory:
            result, log = self.launch(directory, '''
import faulthandler
from runtime_diagnostics import install, install_qt_logging
path = install()
install_qt_logging()
from PySide6.QtCore import qWarning
qWarning("render-device-test-warning")
# Exercise the same live file descriptor used for native faults.
import runtime_diagnostics
faulthandler.dump_traceback(file=runtime_diagnostics._stream)
''')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("render-device-test-warning", log)
        self.assertIn('File "<string>"', log)

    def test_unwritable_log_locations_do_not_prevent_startup(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, "-B", "-c", '''
from unittest.mock import patch
from runtime_diagnostics import install
with patch("pathlib.Path.mkdir", side_effect=PermissionError("denied")):
    assert install() is None
'''], cwd=ROOT, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
