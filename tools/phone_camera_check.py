"""Check Qt pairing and QR generation with loopback TLS, without a camera."""
from __future__ import annotations

import base64
import json
import ssl
import sys
import tempfile
import urllib.request
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from supervision_environment import bootstrap
bootstrap()

import cv2
import numpy as np
from PySide6.QtCore import QCoreApplication, QEventLoop, QObject, QThread, QTimer
from phone_camera import PhoneCamera
from phone_camera_server import PhoneStreamServer

app = QCoreApplication.instance() or QCoreApplication([])
with tempfile.TemporaryDirectory() as directory:
    backend = QObject()
    backend.data_dir = directory
    phone = PhoneCamera(backend)
    physical = [row for row in phone.interfaces if row["rank"] < 10]
    if physical:
        assert phone.interfaces[0]["rank"] < 10, phone.interfaces
    phone.hosts = ["127.0.0.1"]  # Only this test permits loopback pairing.
    loop = QEventLoop()
    threads = []
    def state_changed():
        threads.append(QThread.currentThread() == app.thread())
        if phone.state["phase"] in ("waiting", "error"):
            loop.quit()
    phone.changed.connect(state_changed)
    deadline = QTimer(); deadline.setSingleShot(True); deadline.timeout.connect(loop.quit)
    with patch("phone_camera.PhoneStreamServer", side_effect=lambda host, path:
               PhoneStreamServer(host, path, allow_loopback=True)):
        phone.pair("127.0.0.1")
        phone.close()  # Cancelling pending preparation must not resurrect its link.
        phone.pair("127.0.0.1")
        deadline.start(5000); loop.exec(); deadline.stop()
    assert phone.state["phase"] == "waiting", phone.state
    assert all(threads), "Pairing state changed outside the GUI thread"
    png = base64.b64decode(phone.state["qr"].split(",", 1)[1])
    pixels = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_COLOR)
    decoded, _, _ = cv2.QRCodeDetector().detectAndDecode(pixels)
    assert decoded == phone.state["url"], "QR must encode the actual one-time pairing URL"
    server = phone.server
    context = ssl.create_default_context(cadata=server.ca.read_bytes())
    with urllib.request.urlopen(decoded, context=context, timeout=2) as response:
        assert response.status == 200 and b"getUserMedia" in response.read()
    with urllib.request.urlopen(phone.state["checkUrl"], timeout=2) as response:
        assert response.status == 200 and b"getUserMedia" not in response.read()
    phone._poll()
    assert phone.state["networkSeen"] and phone.state["httpsSeen"]
    phone.close()
    assert not phone.state["url"] and phone.server is None and server.closed and not server.token
    server.thread.join(timeout=2)
    server.check_thread.join(timeout=2)
    assert not server.thread.is_alive()
    assert not server.check_thread.is_alive()
    assert not list(Path(directory).rglob("*.jpg"))
    print(json.dumps({"ok": True, "qrDecodes": True, "trustedLocalTls": True,
                      "pairCancelPair": True, "guiThreadState": True,
                      "closeInvalidatesLink": True, "cameraOpened": False,
                      "networkCheck": True, "interfacePriority": True}))
