"""Update controls must not interrupt work or quit when the helper fails."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from PySide6.QtCore import QObject, Signal
from updater import UpdateManager, APP_VERSION
from update_files import file_hash
from update_installer import launch_pending


class Backend(QObject):
    accountChanged = Signal()
    settingsChanged = Signal()
    def __init__(self):
        super().__init__()
        self.settings_database = {}
        self._cloud = SimpleNamespace(logged_in=lambda: False)


def synchronous_thread(**kwargs):
    return SimpleNamespace(start=kwargs["target"])


class UpdateControlTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="flow-update-controls-")
        self.addCleanup(self.directory.cleanup)
        self.env = patch.dict(os.environ, LOCALAPPDATA=self.directory.name)
        self.env.start(); self.addCleanup(self.env.stop)
        self.backend = Backend()
        self.manager = UpdateManager(backend=self.backend)

    def test_automatic_updates_default_on_and_off_stops_automatic_checks(self):
        self.assertTrue(self.manager.view()["autoDownload"])
        self.backend.settings_database["updateAutoDownload"] = False
        with patch.object(self.manager, "check_for_updates") as check:
            self.manager.automatic_check()
            self.manager._account_changed()
        check.assert_not_called()
        with patch("updater.windows_package_family", return_value=""), patch("updater.threading.Thread") as thread:
            self.manager.check_for_updates(manual=True)
        thread.assert_called_once()

    def test_download_stages_update_without_starting_installer_or_quitting(self):
        self.manager.manifest = {"version": "999.0"}
        quit_calls = Mock()
        self.manager.quitRequested.connect(quit_calls)
        with patch("update_files.stage_manifest"), patch("update_installer.launch_pending") as launch:
            self.manager._download_worker("999.0")
        launch.assert_not_called(); quit_calls.assert_not_called()
        self.assertTrue(self.manager.view()["ready"])
        pending = json.loads((self.manager.cache / "pending.json").read_text(encoding="utf-8"))
        self.assertEqual(pending["version"], "999.0")

    def test_failed_installer_keeps_application_running_and_update_retryable(self):
        self.manager._view.update(ready=True, availableVersion="999.0")
        quit_calls = Mock(); self.manager.quitRequested.connect(quit_calls)
        with patch("updater.is_packaged_build", return_value=True), \
             patch("updater.windows_package_family", return_value=""), \
             patch("updater.sys.platform", "win32"), \
             patch("updater.threading.Thread", side_effect=synchronous_thread), \
             patch("update_installer.launch_pending", side_effect=OSError("helper unavailable")):
            self.manager.install_update()
        quit_calls.assert_not_called()
        self.assertFalse(self.manager._busy)
        self.assertTrue(self.manager._view["ready"])
        self.assertEqual(self.manager._view["status"], "error")

    def test_only_confirmed_helper_can_request_quit(self):
        self.manager._view.update(ready=True, availableVersion="999.0")
        quit_calls = Mock(); self.manager.quitRequested.connect(quit_calls)
        with patch("updater.is_packaged_build", return_value=True), \
             patch("updater.windows_package_family", return_value=""), \
             patch("updater.sys.platform", "win32"), \
             patch("updater.threading.Thread", side_effect=synchronous_thread), \
             patch("update_installer.launch_pending", return_value=True):
            self.manager.install_update()
        quit_calls.assert_called_once()

    def test_pending_update_is_restored_after_restart_without_installing(self):
        stage = self.manager.cache / "999.0/stage"
        stage.mkdir(parents=True)
        (stage / "plan.json").write_text(json.dumps({"format": "flowtodo-staged-v1", "version": "999.0", "install_root": str(Path(sys.executable).resolve().parent)}))
        (self.manager.cache / "pending.json").write_text(json.dumps({"version": "999.0", "stage": str(stage)}))
        with patch("updater.is_packaged_build", return_value=True), patch("updater.windows_package_family", return_value=""), patch("updater.sys.platform", "win32"), patch("update_installer.launch_pending") as launch:
            self.manager._restore_pending()
        self.assertTrue(self.manager._view["ready"])
        launch.assert_not_called()

    def test_all_sources_offline_is_an_error_instead_of_up_to_date(self):
        with patch("updater.sys.platform", "win32"), patch("updater.fetch_latest_release", side_effect=OSError("offline")), patch("updater._request_bytes", side_effect=OSError("offline")):
            self.manager._check_worker()
        self.assertEqual(self.manager._view["status"], "error")
        self.assertFalse(self.manager._busy)


class HelperHandshakeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="flow-helper-handshake-")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.exe = self.root / "app/FlowTodo.exe"
        self.exe.parent.mkdir(); self.exe.write_bytes(b"inert test file")
        self.stage = self.root / "updates/999.0/stage"
        (self.stage / "files").mkdir(parents=True)
        source = self.stage / "files/FlowTodo.exe"
        source.write_bytes(b"inert updated test file")
        plan = {"format": "flowtodo-staged-v1", "version": "999.0", "install_root": str(self.exe.parent), "files": [{"path": "FlowTodo.exe", "size": source.stat().st_size, "sha256": file_hash(source)}]}
        (self.stage / "plan.json").write_text(json.dumps(plan))
        self.pending = self.root / "updates/pending.json"
        self.pending.write_text(json.dumps({"stage": str(self.stage), "version": "999.0"}))

    def launch(self):
        with patch("update_installer.sys.executable", str(self.exe)):
            return launch_pending(self.pending, APP_VERSION, lambda candidate, current: True)

    def test_process_creation_alone_is_not_success(self):
        with patch("update_installer.subprocess.Popen", return_value=SimpleNamespace(poll=lambda: 1)):
            with self.assertRaisesRegex(RuntimeError, "提前退出"):
                self.launch()
        self.assertTrue(self.pending.is_file())
        self.assertEqual(self.exe.read_bytes(), b"inert test file")

    def test_ready_acknowledgment_is_required_and_output_is_redirected(self):
        def popen(command, **kwargs):
            Path(command[command.index("-Ready") + 1]).write_text("ready", encoding="utf-8-sig")
            self.assertEqual(kwargs["stdin"], subprocess.DEVNULL)
            self.assertEqual(kwargs["stderr"], subprocess.STDOUT)
            self.assertIsNotNone(kwargs["stdout"])
            return SimpleNamespace(poll=lambda: None)
        with patch("update_installer.subprocess.Popen", side_effect=popen):
            self.assertTrue(self.launch())
        self.assertFalse(list(self.pending.parent.glob("installer-ready-*.txt")))


if __name__ == "__main__":
    unittest.main()
