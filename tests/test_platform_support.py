"""Platform regressions without launching apps or contacting update servers."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app_paths import user_data_dir
from tools.macos_recipe import resource_entries


class DataLocationTests(unittest.TestCase):
    def test_windows_retains_existing_data_location(self):
        self.assertEqual(user_data_dir('win32', {'LOCALAPPDATA': 'local'}, 'home'),
                         Path('local/FlowTodo/data'))

    def test_mac_data_is_outside_the_application_bundle(self):
        self.assertEqual(user_data_dir('darwin', {}, '/Users/test'),
                         Path('/Users/test/Library/Application Support/FlowTodo/data'))

    def test_explicit_data_location_overrides_every_platform(self):
        for platform in ('win32', 'darwin', 'linux'):
            self.assertEqual(user_data_dir(platform, {'FLOWTODO_DATA_DIR': 'isolated'}, 'home'),
                             Path('isolated'))

    def test_linux_respects_xdg_data_home(self):
        self.assertEqual(user_data_dir('linux', {'XDG_DATA_HOME': 'xdg'}, 'home'),
                         Path('xdg/FlowTodo/data'))


class PlatformActionTests(unittest.TestCase):
    def test_mac_autostart_never_reads_or_writes_windows_startup_entries(self):
        from main import BackendBridge
        backend = SimpleNamespace(settings_database={'autoStart': True})
        with patch('main.sys.platform', 'darwin'):
            self.assertFalse(BackendBridge._is_auto_start_enabled(backend))
            self.assertTrue(BackendBridge._set_auto_start_enabled(backend, False))
            self.assertFalse(backend.settings_database['autoStart'])
            with self.assertRaisesRegex(RuntimeError, '暂不支持'):
                BackendBridge._set_auto_start_enabled(backend, True)

    def test_mac_release_check_cannot_select_a_windows_installer(self):
        from updater import UpdateManager, ReleaseInfo, ReleaseAsset
        release = ReleaseInfo('v999.0', 'Future release', 'https://example.test/release',
                              (ReleaseAsset('FlowTodo-Windows-x64.zip', 'https://example.test/windows.zip'),))
        backend = SimpleNamespace(_busy=True, statusChanged=SimpleNamespace(emit=Mock()),
                                  _received=SimpleNamespace(emit=Mock()))
        with patch('updater.sys.platform', 'darwin'), \
             patch('updater.fetch_latest_release', return_value=release), \
             patch('updater.select_windows_asset') as select:
            UpdateManager._check_worker(backend)
        select.assert_not_called()
        self.assertFalse(backend._busy)
        self.assertIn(release.page_url, backend.statusChanged.emit.call_args.args[2])


class BundleResourcesTests(unittest.TestCase):
    def test_bundle_excludes_private_working_files_and_preserves_resource_subpaths(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name in ('qml/pages/Focus.qml', 'focus-studio/assets/rain.wav',
                         'qml/__pycache__/unwanted.pyc', 'qml/.DS_Store',
                         'data/settings.json', '.superdesign/private.json'):
                file = root / name
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text('sample', encoding='utf-8')
            entries = dict(resource_entries(root))
            self.assertEqual(Path(entries[str(root / 'qml/pages/Focus.qml')]), Path('qml/pages'))
            self.assertEqual(Path(entries[str(root / 'focus-studio/assets/rain.wav')]), Path('focus-studio/assets'))
            for unwanted in ('qml/__pycache__/unwanted.pyc', 'qml/.DS_Store',
                             'data/settings.json', '.superdesign/private.json'):
                self.assertNotIn(str(root / unwanted), entries)


if __name__ == '__main__':
    unittest.main()
