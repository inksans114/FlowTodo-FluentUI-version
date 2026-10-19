"""Native launch paths and real Windows .lnk files, outside the user's Startup folder."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from startup_manager import LaunchTarget, StartupShortcut, resolve_launch


class LaunchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="flow-startup-")
        self.addCleanup(self.temp.cleanup)
        self.root = (Path(self.temp.name) / "FlowTodo 中文 with spaces").resolve()
        self.root.mkdir()
        (self.root / "app.py").touch()
        self.python = self.root / "venv" / "python.exe"
        self.python.parent.mkdir()
        self.python.touch()

    def resolve(self, **kwargs):
        return resolve_launch(self.root, executable=self.python, frozen=False, **kwargs)

    def test_source_targets_native_app_with_correct_quotes_and_working_directory(self):
        launch = self.resolve()
        self.assertEqual(launch.executable, str(self.python))
        self.assertEqual(launch.arguments, subprocess.list2cmdline([str(self.root / "app.py")]))
        self.assertEqual(launch.working_directory, str(self.root))
        self.assertNotIn("main.py", launch.command)

    def test_source_prefers_same_venv_pythonw_without_console(self):
        pythonw = self.python.with_name("pythonw.exe")
        pythonw.touch()
        self.assertEqual(self.resolve().executable, str(pythonw))

    def test_pyinstaller_uses_outer_executable_without_python_arguments(self):
        exe = self.root / "FlowTodo.exe"
        exe.touch()
        extraction = self.root / "_MEI-extraction"
        launch = resolve_launch(extraction, executable=exe, frozen=True)
        self.assertEqual(launch, LaunchTarget(str(exe), "", str(self.root)))

    def test_nuitka_onefile_never_persists_extraction_executable(self):
        outer = self.root / "FlowTodo.exe"
        outer.touch()
        extraction = self.root / "onefile_temp" / "app.exe"
        launch = resolve_launch(extraction.parent, executable=extraction, argv0=str(outer),
                                frozen=False, compiled=SimpleNamespace(containing_dir=str(self.root)))
        self.assertEqual(launch, LaunchTarget(str(outer), "", str(self.root)))

    def test_nuitka_relative_invocation_uses_compiled_containing_directory(self):
        exe = self.root / "FlowTodo.exe"
        exe.touch()
        launch = self.resolve(argv0="FlowTodo.exe", compiled=SimpleNamespace(containing_dir=str(self.root)))
        self.assertEqual(launch.executable, str(exe))

    def test_missing_native_script_cannot_enable_startup(self):
        (self.root / "app.py").unlink()
        with self.assertRaisesRegex(RuntimeError, "app.py"):
            self.resolve()

    def test_missing_packaged_executable_is_reported(self):
        with self.assertRaisesRegex(RuntimeError, "不存在"):
            self.resolve(argv0=str(self.root / "removed.exe"), compiled=SimpleNamespace())


@unittest.skipUnless(sys.platform == "win32", "Windows .lnk integration")
class ShortcutTests(unittest.TestCase):
    def test_real_shortcut_enable_repair_idempotence_and_disable(self):
        with tempfile.TemporaryDirectory(prefix="flow-shortcut-") as directory:
            folder = Path(directory) / "启动 文件夹"
            root = Path(__file__).resolve().parents[1]
            launch = resolve_launch(root)
            shortcut = StartupShortcut(folder)
            self.assertFalse(shortcut.matches(launch))
            shortcut.enable(launch)
            self.assertTrue(shortcut.matches(launch))
            unchanged = shortcut.path.stat().st_mtime_ns
            shortcut.enable(launch)
            self.assertEqual(shortcut.path.stat().st_mtime_ns, unchanged)
            altered = LaunchTarget(launch.executable, '"old main.py"', launch.working_directory)
            shortcut.enable(altered)
            self.assertFalse(shortcut.matches(launch))
            shortcut.enable(launch)
            self.assertTrue(shortcut.matches(launch))
            unrelated = folder / "OtherApp.lnk"
            unrelated.write_bytes(b"unrelated")
            shortcut.disable()
            shortcut.disable()
            self.assertFalse(shortcut.path.exists())
            self.assertTrue(unrelated.exists())
            self.assertEqual(sorted(p.name for p in folder.iterdir()), ["OtherApp.lnk"])

    def test_failed_shortcut_write_preserves_existing_entry_and_cleans_temporary_file(self):
        with tempfile.TemporaryDirectory() as directory:
            shortcut = StartupShortcut(directory)
            launch = resolve_launch(Path(__file__).resolve().parents[1])
            shortcut.path.write_bytes(b"existing")
            shell = Mock()
            shell.CreateShortcut.side_effect = PermissionError("denied")
            shortcut.shell_factory = lambda: shell
            with self.assertRaises(PermissionError):
                shortcut.enable(launch)
            self.assertEqual(shortcut.path.read_bytes(), b"existing")
            self.assertEqual(list(Path(directory).iterdir()), [shortcut.path])

    def test_empty_working_directory_is_not_mistaken_for_current_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            shortcut = StartupShortcut(directory)
            shortcut.path.touch()
            launch = LaunchTarget(sys.executable, "", os.getcwd())
            link = SimpleNamespace(TargetPath=sys.executable, Arguments="", WorkingDirectory="")
            shell = SimpleNamespace(CreateShortcut=lambda _: link)
            shortcut.shell_factory = lambda: shell
            self.assertFalse(shortcut.matches(launch))


class BackendTests(unittest.TestCase):
    def setUp(self):
        from main import BackendBridge
        from compat_backend import RinUIBackend
        self.bridge = BackendBridge
        self.native = RinUIBackend

    def test_enable_verifies_shortcut_and_cleans_only_owned_legacy_entries(self):
        launch = LaunchTarget(sys.executable, '"app.py"', os.getcwd())
        backend = SimpleNamespace(settings_database={"autoStart": False}, settings_file="isolated.json",
                                  _auto_start_launch=Mock(return_value=launch),
                                  _delete_registry_auto_start_value=Mock(), _delete_legacy_startup_entry=Mock(),
                                  _is_auto_start_enabled=Mock(return_value=True), _save_json=Mock())
        with patch("main.sys.platform", "win32"), patch("main.StartupShortcut") as shortcut:
            self.assertTrue(self.bridge._set_auto_start_enabled(backend, True))
        shortcut.return_value.enable.assert_called_once_with(launch)
        backend._delete_registry_auto_start_value.assert_called_once()
        backend._delete_legacy_startup_entry.assert_called_once()
        backend._save_json.assert_called_once_with("isolated.json", {"autoStart": True})

    def test_disable_does_not_require_launch_target_still_exists(self):
        backend = SimpleNamespace(settings_database={"autoStart": True}, settings_file="isolated.json",
                                  _auto_start_launch=Mock(side_effect=RuntimeError("missing EXE")),
                                  _delete_registry_auto_start_value=Mock(), _delete_legacy_startup_entry=Mock(),
                                  _is_auto_start_enabled=Mock(return_value=False), _save_json=Mock())
        with patch("main.sys.platform", "win32"), patch("main.StartupShortcut") as shortcut:
            self.bridge._set_auto_start_enabled(backend, False)
        shortcut.return_value.disable.assert_called_once()
        backend._auto_start_launch.assert_not_called()
        self.assertFalse(backend.settings_database["autoStart"])

    def test_write_failure_returns_real_state_and_native_error_notification(self):
        backend = SimpleNamespace(settings_database={"autoStart": False},
                                  _set_auto_start_enabled=Mock(side_effect=PermissionError("启动目录不可写")),
                                  _is_auto_start_enabled=Mock(return_value=False),
                                  settingsChanged=SimpleNamespace(emit=Mock()),
                                  messageRequested=SimpleNamespace(emit=Mock()))
        backend.set_auto_start_enabled = lambda value: self.bridge.set_auto_start_enabled(backend, value)
        self.assertFalse(self.native.setAutoStartEnabled(backend, True))
        self.assertFalse(backend.settings_database["autoStart"])
        self.assertEqual(backend.messageRequested.emit.call_args.args[0], "error")
        self.assertIn("不可写", backend.messageRequested.emit.call_args.args[2])

    def test_other_settings_do_not_touch_startup_and_old_setter_routes_to_verified_path(self):
        backend = SimpleNamespace(settings_database={"autoStart": True}, save_settings=Mock(),
                                  _json=json.dumps, setAutoStartEnabled=Mock(),
                                  settingsChanged=SimpleNamespace(emit=Mock()))
        self.native.setSetting(backend, "focusDuration", 40)
        self.assertNotIn("autoStart", json.loads(backend.save_settings.call_args.args[0]))
        self.native.setSetting(backend, "autoStart", False)
        backend.setAutoStartEnabled.assert_called_once_with(False)

    def test_switch_reads_real_registration_even_when_saved_flag_is_stale(self):
        backend = SimpleNamespace(settings_database={"autoStart": True},
                                  _is_auto_start_enabled=Mock(return_value=False))
        self.assertFalse(self.native.getSetting(backend, "autoStart", True))

    def test_full_settings_payload_does_not_rewrite_unchanged_startup(self):
        backend = SimpleNamespace(settings_database={"autoStart": True}, settings_file="isolated.json",
                                  _set_auto_start_enabled=Mock(), _save_json=Mock(),
                                  _apply_island_preferences_to_active=Mock(), _process_daily_tasks=Mock())
        self.bridge.save_settings(backend, json.dumps({"autoStart": True, "focusDuration": 40}))
        backend._set_auto_start_enabled.assert_not_called()
        self.assertEqual(backend.settings_database["focusDuration"], 40)
        self.assertTrue(backend.settings_database["autoStart"])


if __name__ == "__main__":
    unittest.main()
