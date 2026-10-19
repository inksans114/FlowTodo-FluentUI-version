"""Real QML + local model QA. No webcam, microphone or desktop capture is opened."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "vendor"))
DATA = tempfile.TemporaryDirectory(prefix="flowtodo-supervision-qa-")
os.environ["LOCALAPPDATA"] = DATA.name
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["QT_QUICK_BACKEND"] = "software"
os.environ["QT_QUICK_CONTROLS_STYLE"] = "Basic"
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu --disable-gpu-compositing"

from supervision_environment import bootstrap
bootstrap()

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QFontDatabase
from PySide6.QtQml import QQmlComponent, QQmlExpression
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from RinUI import RinUIWindow
from compat_backend import RinUIBackend
from i18n_runtime import translator


def find(item, name):
    if item.objectName() == name:
        return item
    for child in item.childItems():
        result = find(child, name)
        if result is not None:
            return result


QApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
app = QApplication([])
app.setQuitOnLastWindowClosed(False)
for font in ("msyh.ttc", "segoeui.ttf"):
    QFontDatabase.addApplicationFont(str(Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / font))
backend = RinUIBackend()
backend.settings_database.update(notificationSoundEnabled=False, focusWeatherMode="off")
backend._apply_focus_environment = lambda _options: None
backend._restore_focus_environment = lambda: None
backend._show_main_window = lambda: None
backend._minimize_main_window = lambda: None
# Current app is ours. The OCR worker initializes but never receives a screen-capture job.
backend._foreground_window_info = lambda: (1, os.getpid(), "FlowTodo", "python.exe", "")
window = RinUIWindow(shared_engine=False)
window.engine.rootContext().setContextProperty("Backend", backend)
window.engine.rootContext().setContextProperty("I18nBridge", translator())
warnings = []
window.engine.warnings.connect(lambda errors: warnings.extend(e.toString() for e in errors))
window.load(ROOT / "qml/Main.qml")
root = window.root_window
assert root is not None
backend.attach_native_window(root)
output = ROOT / ".superdesign/qa"
output.mkdir(parents=True, exist_ok=True)


def evaluate(code):
    e = QQmlExpression(window.engine.rootContext(), root, code)
    result = e.evaluate()
    assert not e.hasError(), e.error().toString()
    return result


def render(target, name):
    QTest.qWait(300)
    image = target.grabWindow()
    assert not image.isNull() and image.save(str(output / name))


failed = True
try:
    for name in ("SupervisionWindow.qml", "components/SupervisionPanel.qml"):
        component = QQmlComponent(window.engine, QUrl.fromLocalFile(str(ROOT / "qml" / name)))
        assert not component.errors(), [e.toString() for e in component.errors()]
    QTest.qWait(350)
    evaluate("navigationView.push('" + QUrl.fromLocalFile(str(ROOT / "qml/pages/SupervisionWorkspace.qml")).toString() + "')")
    QTest.qWait(350)
    page = find(root.contentItem(), "SupervisionWorkspace")
    if page is None:
        diagnostic = QQmlComponent(window.engine, QUrl.fromLocalFile(str(ROOT / "qml/pages/SupervisionWorkspace.qml")))
        print("PAGE ERRORS", [error.toString() for error in diagnostic.errors()], flush=True)
    assert page is not None, warnings
    assert not find(root.contentItem(), "startSupervision").property("enabled")
    assert not find(root.contentItem(), "supervisionScreenConsent").property("checked")
    # Missing dependencies must not leave a disabled switch claiming "开启".
    from unittest.mock import patch
    setup = backend.supervision._availability_json
    backend.supervision._availability_json = json.dumps({"camera": False, "screen": False,
                "cameraReason": "当前启动环境未安装 mediapipe", "screenReason": "当前启动环境未安装 rapidocr_onnxruntime",
                "pythonVersion": "3.9.6", "interpreter": "fixture/python.exe", "repairHint": "修复后重新启动",
                "repairCommand": "python tools/setup_supervision.py"})
    backend.supervision.setupChanged.emit()
    QTest.qWait(100)
    for name in ("supervisionCamera", "supervisionScreen"):
        control = find(root.contentItem(), name)
        assert not control.property("checked") and not control.property("enabled")
    assert not find(root.contentItem(), "startSupervision").property("enabled")
    page.setProperty("showRepair", True)
    render(root, "supervision-missing-environment.png")
    backend.supervision._availability_json = setup
    page.setProperty("showRepair", False)
    backend.supervision.setupChanged.emit()
    QTest.qWait(100)
    assert find(root.contentItem(), "supervisionScreen").property("enabled")
    render(root, "supervision-prepare.png")
    root.setWidth(900); root.setHeight(620)
    render(root, "supervision-prepare-compact.png")
    # Consent refusal must not create a timer or worker.
    assert not backend.startSupervision(json.dumps({"screen": True}), 25, "测试")
    assert not backend.active_focus_session
    requested = []
    backend.supervisionViewRequested.connect(requested.append)
    assert backend.startSupervision(json.dumps({"screen": True, "screenConsent": True, "view": "compact"}), 25, "完成物理卷子的选择题")
    assert backend.supervision.active, warnings
    supervisor = backend.supervision
    for _ in range(100):
        QTest.qWait(100)
        if "screen" in supervisor.ready:
            break
    assert "screen" in supervisor.ready, json.dumps(supervisor.state, ensure_ascii=False)
    assert supervisor.camera is None
    assert not supervisor.busy["screen"]
    assert requested[-1] == "compact"
    supervisor_window = next(w for w in app.allWindows() if w.objectName() == "supervisionWindow")
    assert supervisor_window.width() == 430 and supervisor_window.height() == 420
    render(supervisor_window, "supervision-small.png")
    island = next(iter(backend.island_windows.values()))
    remaining = island.focus_snapshot()["remaining"]
    backend.presentSupervision("full")
    QTest.qWait(200)
    assert requested[-1] == "full"
    assert abs(island.focus_snapshot()["remaining"] - remaining) <= 1
    # The full-screen window and overlay compile without browser dependencies.
    render(supervisor_window, "supervision-full.png")
    # Artificial screen evidence tests alert behavior without reading the desktop.
    supervisor.timer.stop()
    supervisor.policy.started = time.monotonic() - 100
    supervisor.policy.pending["screen"] = time.monotonic() - 30
    evidence = {"status": "suspect", "label": "疑似娱乐内容，等待确认", "suspect": True,
                "title": "测试窗口", "windowKey": "test", "sampleAt": time.monotonic()}
    supervisor._result(supervisor.token, "screen", evidence)
    alert = supervisor.state["alert"]
    assert alert and alert["kind"] == "screen"
    render(supervisor_window, "supervision-alert-full.png")
    backend.presentSupervision("compact")
    render(supervisor_window, "supervision-alert-small.png")
    supervisor.resolveAlert("stale-id", "wrong")
    assert supervisor.state["alert"] is not None
    supervisor.resolveAlert(alert["id"], "allow")
    assert supervisor.state["alert"] is None
    assert supervisor._screen_allowed["test"] > time.monotonic()
    backend.toggleSupervisionPause()
    assert supervisor.state["paused"]
    assert supervisor.camera is None and supervisor.preview == ""
    paused = island.focus_snapshot()["remaining"]
    QTest.qWait(1100)
    assert island.focus_snapshot()["remaining"] == paused
    supervisor._result(supervisor.token, "screen", evidence)
    assert supervisor.state["alert"] is None
    backend.toggleSupervisionPause()
    assert not supervisor.state["paused"]
    supervisor._result(supervisor.token, "screen", dict(evidence, epoch=supervisor._epoch - 1))
    assert supervisor.state["alert"] is None
    token = supervisor.token
    backend.stopSupervision()
    assert not supervisor.active and supervisor.camera is None and supervisor.preview == ""
    assert backend.active_focus_session  # Stopping supervision does not discard focus.
    supervisor._result(token, "screen", evidence)
    assert supervisor.state["alert"] is None
    # Actual TLS receiver + camera model, with generated images only. Keep the
    # event loop ticking while phone frames arrive and the view switches.
    import io
    import ssl
    import threading
    import urllib.request
    from PIL import Image
    from phone_camera_server import PhoneStreamServer
    from PySide6.QtCore import QEventLoop, QTimer, QThread
    phone = PhoneStreamServer("127.0.0.1", Path(DATA.name) / "test-tls", allow_loopback=True)
    supervisor.phone.server = phone
    supervisor.phone.state.update(phase="waiting", url=phone.url, qr="", fingerprint=phone.fingerprint)
    supervisor.phone.changed.emit()
    picture = io.BytesIO()
    Image.new("RGB", (640, 480), "#668a74").save(picture, format="JPEG")
    fixture_jpeg = picture.getvalue()
    halt = threading.Event()
    uploads, upload_errors = [], []
    def produce():
        context = ssl.create_default_context(cadata=phone.ca.read_bytes())
        while not halt.is_set():
            if phone.running:
                request = urllib.request.Request(phone.origin + "/frame", data=fixture_jpeg,
                    headers={"X-FlowTodo-Token": phone.token, "Content-Type": "image/jpeg"})
                try:
                    with urllib.request.urlopen(request, context=context, timeout=2) as response:
                        assert response.status == 202
                        uploads.append(time.monotonic())
                except (OSError, urllib.error.URLError) as error:
                    upload_errors.append(str(error))
            halt.wait(.9)
    producer = threading.Thread(target=produce, daemon=True)
    beat_times, deliveries = [], []
    heartbeat = QTimer(); heartbeat.setInterval(50); heartbeat.timeout.connect(lambda: beat_times.append(time.monotonic()))
    supervisor.previewChanged.connect(lambda: deliveries.append(QThread.currentThread() == app.thread()) if supervisor.preview else None)
    assert backend.startSupervision(json.dumps({"camera": True, "cameraSource": "phone", "cameraConsent": True, "screen": False, "view": "full"}), 25, "桌面串流测试")
    producer.start(); heartbeat.start()
    # Use the application's real event loop. Repeated QTest.qWait calls can
    # monopolize Python's GIL and starve the TLS receiver's Python threads.
    frame_loop = QEventLoop()
    deadline = QTimer(); deadline.setSingleShot(True); deadline.timeout.connect(frame_loop.quit)
    complete = QTimer(); complete.setInterval(100)
    complete.timeout.connect(lambda: frame_loop.quit() if len(deliveries) >= 10 else None)
    deadline.start(30000); complete.start(); frame_loop.exec()
    deadline.stop(); complete.stop()
    assert len(deliveries) >= 10, {"deliveries": len(deliveries), "uploads": len(uploads),
                                  "uploadErrors": upload_errors, "state": supervisor.state}
    assert all(deliveries), "A model result updated the GUI from another thread"
    assert max(b-a for a,b in zip(beat_times, beat_times[1:])) < 1.0
    assert supervisor.camera is None  # The phone source never opens a PC webcam.
    supervisor_panel = find(supervisor_window.contentItem(), "supervisionPanel")
    supervisor_panel.setProperty("showCalibration", True)
    supervisor.calibrate("learning")
    assert supervisor.state["calibration"]["phase"] == "learning"
    render(supervisor_window, "supervision-calibration-full.png")
    backend.presentSupervision("compact"); QTest.qWait(200)
    assert supervisor_window.height() > 420
    render(supervisor_window, "supervision-calibration-small.png")
    backend.toggleSupervisionPause(); QTest.qWait(200)
    assert not phone.running and phone.latest is None
    assert supervisor.state["calibration"]["phase"] != "learning"
    backend.toggleSupervisionPause(); QTest.qWait(300)
    halt.set(); producer.join(timeout=3)
    supervisor.timer.stop()
    supervisor._epoch += 1
    supervisor.worker.set_epoch(supervisor._epoch, False)
    # Drive the personal classifier through the controller with labelled
    # synthetic feature samples, not stored camera images.
    def posture(value):
        return {"handsVisible": 1, "faceVisible": 1, "phoneVisible": 0,
                "headY": value, "handsCenterY": value, "headX": .4, "eyesY": value}
    def evidence(value):
        return {"epoch": supervisor._epoch, "sampleAt": time.monotonic(), "preview": supervisor.preview,
                "points": [], "boxes": [], "present": True, "upperBody": True, "observable": True,
                "phoneVisible": False, "heldPhone": False, "handCount": 1, "eyeDirection": "front",
                "features": posture(value)}
    supervisor.calibrate("learning")
    for _ in range(10):
        supervisor._result(supervisor.token, "camera", evidence(.2))
    supervisor.calibrate("other")
    for _ in range(10):
        supervisor._result(supervisor.token, "camera", evidence(.7))
    assert supervisor.state["calibration"]["ready"]
    supervisor.policy.started = time.monotonic() - 100
    supervisor.policy.pending["posture"] = time.monotonic() - 45
    supervisor.policy.last_sample["posture"] = time.monotonic()
    supervisor._result(supervisor.token, "camera", evidence(.7))
    assert supervisor.state["alert"]["kind"] == "posture"
    supervisor.resolveAlert(supervisor.state["alert"]["id"], "wrong")
    with patch("supervision.QMediaDevices.videoInputs", side_effect=AssertionError("device enumeration during results")):
        supervisor._result(supervisor.token, "camera", evidence(.2))
        assert json.loads(supervisor.camerasJson) is not None
        supervisor.changed.emit()
    assert supervisor.state["alert"] is None
    # Force an inference timeout without waiting or blaming the user for it.
    supervisor.busy["camera"] = True
    supervisor._submitted_at["camera"] = time.monotonic() - 20
    supervisor._tick()
    assert "camera" not in supervisor.ready and supervisor.state["cameraStatus"] == "error"
    assert backend.active_focus_session and not phone.running
    heartbeat.stop()
    backend.stopSupervision()
    assert phone.closed and not supervisor.phone.state["url"]
    print(json.dumps({"phoneTlsFrames": len(deliveries), "guiHeartbeatMaxGap": round(max(b-a for a,b in zip(beat_times, beat_times[1:])), 3), "guiThreadResults": True, "timeoutKeepsFocus": True}), flush=True)
    assert not warnings, warnings
    print(json.dumps({"ok": True, "checks": ["consent required", "real local OCR initialization", "no capture of own window", "fullscreen/small view", "same authoritative timer", "sustained evidence reminder", "stale click ignored", "temporary exception", "pause closes capture", "paused clock", "late result rejected", "stop releases resources, focus retained", "continuous phone TLS frames", "GUI heartbeat", "native inference timeout"], "warnings": warnings}, ensure_ascii=False), flush=True)
    failed = False
except Exception:
    import traceback
    traceback.print_exc()
    sys.stderr.flush()
finally:
    backend.shutdown()
    QTest.qWait(100)
    DATA.cleanup()
    # Match the other offscreen previews: native QML objects outlive Python
    # wrappers at interpreter finalization, after resources have been shut down.
    os._exit(1 if failed else 0)
