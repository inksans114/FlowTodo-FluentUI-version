from __future__ import annotations

import unittest
import tempfile
import zipfile
from pathlib import Path

from updater import (
    ReleaseAsset,
    is_newer_version,
    safe_path_component,
    select_windows_asset,
    validate_zip_package,
    version_key,
)


class VersionTests(unittest.TestCase):
    def test_version_key_accepts_common_release_tags(self):
        self.assertEqual(version_key("v1.2.0"), (1, 2))
        self.assertEqual(version_key("FlowTodo_fluent_ui_v2.4.1"), (2, 4, 1))

    def test_newer_version_comparison(self):
        self.assertTrue(is_newer_version("1.1", "1.0"))
        self.assertTrue(is_newer_version("2.0.0", "1.9.9"))
        self.assertFalse(is_newer_version("1.0.0", "1.0"))
        self.assertFalse(is_newer_version("release", "1.0"))


class AssetSelectionTests(unittest.TestCase):
    def test_prefers_named_windows_zip(self):
        assets = [
            ReleaseAsset("OtherApp-Windows.zip", "https://example.test/OtherApp-Windows.zip"),
            ReleaseAsset("FlowTodo-Windows-x64-1.1.zip", "https://example.test/FlowTodo-Windows-x64-1.1.zip"),
            ReleaseAsset("FlowTodo-Setup-1.1.exe", "https://example.test/FlowTodo-Setup-1.1.exe"),
        ]
        self.assertEqual(select_windows_asset(assets).name, "FlowTodo-Windows-x64-1.1.zip")

    def test_rejects_source_and_non_installer_executables(self):
        assets = [
            ReleaseAsset("Source-code.zip", "https://example.test/Source-code.zip"),
            ReleaseAsset("FlowTodo.exe", "https://example.test/FlowTodo.exe"),
        ]
        self.assertIsNone(select_windows_asset(assets))


class PackageSafetyTests(unittest.TestCase):
    def test_release_tag_is_safe_for_local_directory(self):
        self.assertEqual(safe_path_component("v1.1/../../bad"), "v1.1_.._.._bad")

    def test_validates_complete_package(self):
        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory) / "update.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("app.dist/FlowTodo.exe", b"test")
                archive.writestr("app.dist/qml/Main.qml", b"test")
            validate_zip_package(archive_path)

    def test_rejects_archive_without_executable(self):
        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory) / "update.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("README.txt", b"source only")
            with self.assertRaisesRegex(RuntimeError, "FlowTodo.exe"):
                validate_zip_package(archive_path)


if __name__ == "__main__":
    unittest.main()
