"""Real inference QA from Google's public sample and synthetic text; no live capture."""
from __future__ import annotations

import io
import json
import os
import sys
import time
import threading
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from supervision_vision import CameraDetector, ScreenDetector

# Download a public test image into memory; never enable the user's camera.
with urllib.request.urlopen("https://storage.googleapis.com/mediapipe-assets/pose.jpg", timeout=30) as response:
    sample = response.read(5 * 1024 * 1024)
with Image.open(io.BytesIO(sample)) as photo:
    rgb = np.asarray(photo.convert("RGB"))
camera = CameraDetector()
try:
    full = camera.detect(rgb, 1)
    assert full["present"] and full["upperBody"], full
    # Exercise a desk-style upper-body crop, without requiring legs in view.
    crop = camera.detect(np.ascontiguousarray(rgb[:int(rgb.shape[0] * .65)]), 2)
    assert crop["present"], crop
    blank = camera.detect(np.zeros((480, 640, 3), dtype=np.uint8), 3)
    assert not blank["observable"] and not blank["present"]
    additional = {}
    for index, (name, url) in enumerate((
        ("hands", "https://storage.googleapis.com/mediapipe-tasks/hand_landmarker/woman_hands.jpg"),
        ("face", "https://storage.googleapis.com/mediapipe-assets/portrait.jpg")), 4):
        with urllib.request.urlopen(url, timeout=30) as response:
            content = response.read(5 * 1024 * 1024)
        with Image.open(io.BytesIO(content)) as fixture:
            fixture = fixture.convert("RGB")
            fixture.thumbnail((640, 480))
            # VIDEO tracking first needs to lose the previous subject when a
            # fixture abruptly switches to a different person and resolution.
            for repeat in range(3):
                additional[name] = camera.detect(np.asarray(fixture), index * 1000 + repeat)
    assert additional["hands"]["handCount"] >= 1, additional["hands"]
    assert "eyesX" in additional["face"]["features"], additional["face"]
finally:
    camera.close()
text_image = Image.new("RGB", (900, 400), "white")
font = ImageFont.truetype(str(Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts/msyh.ttc"), 45)
ImageDraw.Draw(text_image).text((40, 80), "物理作业 选择题\n抖音 热门短视频", font=font, fill="black", spacing=20)
ocr = ScreenDetector()
text = ocr.detect(np.asarray(text_image))
assert "物理" in text and "抖音" in text, text

# Exercise the same QVideoFrame -> QImage -> background worker path as a camera.
# The screen capture is substituted with our own generated image.
from unittest.mock import patch
from PySide6.QtCore import QCoreApplication
from PySide6.QtGui import QImage
from PySide6.QtMultimedia import QVideoFrame
from supervision import PatrolWorker
from supervision_policy import options

app = QCoreApplication([])
ready, results = [], {}
worker = PatrolWorker("fixture", options({"camera": True, "cameraConsent": True, "screen": True, "screenConsent": True}))
worker.ready.connect(lambda token, state: ready.append(state))
worker.result.connect(lambda token, kind, result: results.update({kind: result}))


def pump(until):
    deadline = time.monotonic() + 15
    while not until() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(.02)
    assert until(), {"ready": ready, "results": results.keys()}


try:
    worker.start()
    pump(lambda: bool(ready))
    assert ready[0] == {"camera": "ready", "screen": "ready"}, ready
    worker.set_epoch(7, True)
    frame = QVideoFrame(QImage.fromData(sample))
    gui_thread = threading.get_ident()
    conversion_threads = []
    original_conversion = QVideoFrame.toImage
    def convert_in_worker(video_frame):
        conversion_threads.append(threading.get_ident())
        return original_conversion(video_frame)
    with patch.object(QVideoFrame, "toImage", convert_in_worker):
        assert worker.submit("camera", QVideoFrame(frame), {"epoch": 7, "capturedAt": time.monotonic()})
        pump(lambda: "camera" in results)
    assert conversion_threads and all(t != gui_thread for t in conversion_threads)
    with patch("PIL.ImageGrab.grab", side_effect=lambda **kwargs: text_image.copy()):
        assert worker.submit("screen", metadata={"epoch": 7, "capturedAt": time.monotonic(), "hwnd": 1,
                                                "process": "chrome.exe", "title": "测试", "windowKey": "fixture", "allowed": False})
        pump(lambda: len(results) == 2)
    assert results["camera"]["present"] and results["camera"]["upperBody"], results["camera"].get("error")
    assert results["camera"]["preview"].startswith("data:image/jpeg;base64,")
    assert results["screen"]["suspect"] and "title" in results["screen"], results["screen"]
    assert "text" not in results["screen"] and "preview" not in results["screen"]
    worker.set_epoch(8, False)
    assert worker.jobs.empty() and not worker.processing
finally:
    worker.stop()
    worker.wait()
    app.processEvents()
print(json.dumps({"ok": True, "fullBody": full["present"], "upperBody": full["upperBody"],
                  "croppedUpperBody": crop["upperBody"], "darkFrameUnknown": not blank["observable"],
                  "syntheticOcr": text, "realQtFrameWorker": True, "foregroundOcrWorker": True,
                  "screenPixelsAndTextDiscarded": True, "pausedJobsDiscarded": True,
                  "videoConversionOffGuiThread": True, "hands": additional["hands"]["handCount"],
                  "irisLandmarks": True, "eyeCue": additional["face"]["eyeDirection"]}, ensure_ascii=False))
