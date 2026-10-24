"""Exercise real streamed package progress and reusable staged downloads offline."""
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from updater import ReleaseAsset, UpdateManager
from update_files import stage_archive, stage_manifest


class UpdateProgressTests(unittest.TestCase):
    def test_archive_download_reports_bytes_and_verification_before_completion(self):
        for known in (True, False):
            with self.subTest(known=known), tempfile.TemporaryDirectory() as folder:
                archive = io.BytesIO()
                with zipfile.ZipFile(archive, "w") as output:
                    output.writestr("FlowTodo/FlowTodo.exe", b"offline fixture" * 30000)
                payload = archive.getvalue()
                response = io.BytesIO(payload)
                response.headers = {"Content-Length": str(len(payload))} if known else {}
                manager = UpdateManager(); manager.cache = Path(folder)
                events = []; manager._received.connect(events.append)
                with patch("updater.urllib.request.urlopen", return_value=response):
                    result = manager._download_asset(ReleaseAsset("FlowTodo.zip", "https://github.com/inksans114/FlowTodo-FluentUI-version/releases/download/v999/FlowTodo.zip"), "999.0")
                self.assertTrue(result.is_file())
                transfer = [event for event in events if "receivedBytes" in event]
                self.assertEqual(transfer[-1]["receivedBytes"], len(payload))
                self.assertEqual(transfer[-1]["progressKnown"], known)
                self.assertEqual(events[-1]["status"], "verifying")
                self.assertTrue(all(event.get("progress", 0) <= 85 for event in events))

    def test_manifest_reports_streaming_bytes_and_counts_reused_files(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); body = b"x" * 600000
            item = {"path":"FlowTodo.exe", "size":len(body), "sha256":hashlib.sha256(body).hexdigest(), "url":"https://example.com/FlowTodo.exe"}
            manifest = {"version":"999.0", "files":[item]}
            events = []
            stage_manifest(manifest, root/"app", root/"stage", opener=lambda *a, **k: io.BytesIO(body), detail=lambda *args: events.append(args))
            self.assertGreater(len(events), 2)
            self.assertEqual(events[-1], (len(body), len(body)))
            events.clear()
            def offline(*args, **kwargs): raise AssertionError("Verified cached file must not be downloaded again")
            stage_manifest(manifest, root/"app", root/"stage", opener=offline, detail=lambda *args: events.append(args))
            self.assertEqual(events[-1], (len(body), len(body)))

    def test_archive_preparation_reports_all_bytes_and_retains_a_valid_plan(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); archive = root/"package.zip"
            with zipfile.ZipFile(archive,"w") as output:
                output.writestr("FlowTodo/FlowTodo.exe", b"fixture")
                output.writestr("FlowTodo/qml/Main.qml", b"qml")
            events = []
            stage_archive(archive,"999.0",root/"app",root/"stage",progress=lambda *args: events.append(args))
            self.assertEqual(events[-1], (10,10))
            self.assertEqual(json.loads((root/"stage/plan.json").read_text())["version"], "999.0")
