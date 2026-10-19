"""Prepare public MediaPipe models at build/setup time, never during patrol."""
from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "supervision-models"
URLS = {
    "pose_landmarker_lite.task": "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task",
    "efficientdet_lite0.tflite": "https://storage.googleapis.com/mediapipe-models/object_detector/efficientdet_lite0/int8/1/efficientdet_lite0.tflite",
    "hand_landmarker.task": "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task",
    "face_landmarker.task": "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task",
}


def verify():
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    for name in URLS:
        data = (ROOT / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != manifest[name]["sha256"]:
            raise RuntimeError(f"Model checksum mismatch: {name}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        verify()
        print("[OK] Supervision models verified.")
        return
    ROOT.mkdir(exist_ok=True)
    manifest_path = ROOT / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else {}
    for name, url in URLS.items():
        if name in manifest and (ROOT / name).is_file():
            if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == manifest[name]["sha256"]:
                continue
        with urllib.request.urlopen(url, timeout=60) as response:
            data = response.read(32 * 1024 * 1024 + 1)
        if not 100000 < len(data) <= 32 * 1024 * 1024:
            raise RuntimeError(f"Unexpected model size: {name}")
        (ROOT / name).write_bytes(data)
        manifest[name] = {"url": url, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
        print(f"[OK] {name}: {len(data)} bytes")
    (ROOT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    verify()


if __name__ == "__main__":
    main()
