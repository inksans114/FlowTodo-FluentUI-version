"""Opt-in camera / foreground-screen patrol, independent of the focus scene."""
from __future__ import annotations

import base64
import json
import os
import queue
import threading
import time
from uuid import uuid4

from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QObject, Property, Qt, QTimer, Signal, Slot
from PySide6.QtGui import QImage
from PySide6.QtMultimedia import QCamera, QMediaCaptureSession, QMediaDevices, QVideoFrame, QVideoSink

from supervision_policy import DEFAULT_BLOCKED, SupervisionPolicy, options, screen_evidence
from supervision_environment import availability
from supervision_calibration import PostureCalibration


class PatrolWorker(QObject):
    ready = Signal(str, dict)
    result = Signal(str, str, dict)
    finished = Signal()

    def __init__(self, token, config, parent=None):
        super().__init__(parent)
        self.token, self.config = token, config
        self.jobs = queue.Queue(maxsize=2)
        self.halt = threading.Event()
        self.epoch = 0
        self.processing = False
        self._thread = threading.Thread(target=self.run, daemon=True)

    def start(self):
        self._thread.start()

    def wait(self, milliseconds=None):
        self._thread.join(None if milliseconds is None else milliseconds / 1000)
        return not self._thread.is_alive()

    def submit(self, kind, image=None, metadata=None):
        try:
            self.jobs.put_nowait((kind, image, metadata or {}))
            return True
        except queue.Full:
            return False

    def stop(self):
        self.halt.set()
        self._clear_jobs()

    def _clear_jobs(self):
        while True:
            try:
                self.jobs.get_nowait()
            except queue.Empty:
                break

    def set_epoch(self, epoch, enabled):
        self.processing = False
        self.epoch = epoch
        self._clear_jobs()
        self.processing = enabled

    def run(self):
        models, readiness = {}, {}
        try:
            from supervision_vision import CameraDetector, ScreenDetector
            for kind, enabled, cls in (("camera", self.config["camera"], CameraDetector),
                                       ("screen", self.config["screen"], ScreenDetector)):
                if not enabled or self.halt.is_set():
                    continue
                try:
                    models[kind] = cls()
                    readiness[kind] = "ready"
                except Exception as error:
                    readiness[kind] = "error"
                    readiness[kind + "Error"] = f"本地识别初始化失败：{type(error).__name__}。请检查依赖与模型文件。"
            if not self.halt.is_set():
                self.ready.emit(self.token, readiness)
            while not self.halt.is_set():
                try:
                    kind, image, metadata = self.jobs.get(timeout=.2)
                except queue.Empty:
                    continue
                if self.halt.is_set():
                    break
                if not self.processing or metadata.get("epoch") != self.epoch:
                    continue
                try:
                    import numpy as np
                    if kind not in models:
                        raise RuntimeError("检测器尚未就绪")
                    if kind == "camera":
                        # The GUI only retains a frame reference. GPU readback,
                        # conversion and scaling can wait for the camera driver
                        # and must never run inside the GUI's video-frame slot.
                        if isinstance(image, QVideoFrame):
                            image = image.toImage()
                        elif isinstance(image, bytes):
                            # Validate dimensions before decoding an untrusted LAN JPEG.
                            import io
                            from PIL import Image
                            with Image.open(io.BytesIO(image)) as header:
                                if header.width > 1280 or header.height > 1280:
                                    raise ValueError("手机画面尺寸过大")
                            image = QImage.fromData(image, "JPG")
                        if image.isNull():
                            raise RuntimeError("摄像头没有提供可转换的画面")
                        image = image.scaled(640, 480, Qt.KeepAspectRatio, Qt.FastTransformation).convertToFormat(QImage.Format_RGB888)
                        rgb = np.frombuffer(image.bits(), dtype=np.uint8, count=image.sizeInBytes()).reshape(image.height(), image.bytesPerLine())
                        rgb = rgb[:, :image.width() * 3].reshape(image.height(), image.width(), 3).copy()
                        evidence = models[kind].detect(rgb, metadata["capturedAt"] * 1000)
                        if self.halt.is_set() or metadata.get("epoch") != self.epoch:
                            continue
                        buffer = QByteArray()
                        stream = QBuffer(buffer)
                        stream.open(QIODevice.WriteOnly)
                        image.save(stream, "JPG", 72)
                        stream.close()
                        evidence["preview"] = "data:image/jpeg;base64," + base64.b64encode(bytes(buffer)).decode("ascii")
                    else:
                        from PIL import ImageGrab
                        # Capture only the selected foreground window, never all monitors.
                        with ImageGrab.grab(window=int(metadata["hwnd"])) as capture:
                            capture = capture.convert("RGB")
                            capture.thumbnail((1280, 900))
                            text = models[kind].detect(np.asarray(capture))
                        evidence = screen_evidence(metadata["process"], metadata["title"], text,
                                                   self.config, metadata.get("allowed", False))
                        evidence["title"] = metadata["title"][:90]
                        evidence["windowKey"] = metadata["windowKey"]
                        evidence["hwnd"] = metadata["hwnd"]
                        # Raw image and text are discarded here, not returned or persisted.
                    evidence["sampleAt"] = metadata["capturedAt"]
                    evidence["epoch"] = metadata.get("epoch", 0)
                    if not self.halt.is_set() and metadata.get("epoch") == self.epoch:
                        self.result.emit(self.token, kind, evidence)
                except Exception as error:
                    if not self.halt.is_set():
                        self.result.emit(self.token, kind, {"error": f"本次读取失败（{type(error).__name__}），不会记为分心。", "epoch": metadata.get("epoch", 0)})
        finally:
            if "camera" in models:
                models["camera"].close()
            models.clear()
            try:
                self.finished.emit()
            except RuntimeError:
                pass  # The app can exit even if a native detector was stalled.


class SupervisionController(QObject):
    changed = Signal()
    setupChanged = Signal()
    previewChanged = Signal()
    alertRaised = Signal(str)
    stopped = Signal()

    def __init__(self, backend):
        super().__init__(backend)
        self.backend = backend
        self.active = False
        self.token = ""
        self.config = {}
        self.policy = None
        self.calibration = PostureCalibration()
        self.worker = None
        self.workers = set()
        self.capture = self.camera = self.sink = None
        self.preview = ""
        self.state = {"active": False, "cameraStatus": "off", "screenStatus": "off", "alert": None, "count": 0}
        self.busy = {"camera": False, "screen": False}
        self._submitted_at = {"camera": 0, "screen": 0}
        self.ready = set()
        self._last_frame = 0
        self._last_video_seen = 0
        self._screen_allowed = {}
        self._failures = {"camera": 0, "screen": 0}
        self._patrolling = False
        self._epoch = 0
        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self._tick)
        self.devices = QMediaDevices(self)
        self.devices.videoInputsChanged.connect(self._devices_changed)
        self._video_devices = list(QMediaDevices.videoInputs())
        self._devices_json = self._device_json()
        self._availability_json = json.dumps(availability(), ensure_ascii=False)
        self._devices_dirty = False
        from phone_camera import PhoneCamera
        self.phone = PhoneCamera(backend)

    @Property(QObject, constant=True)
    def phoneCamera(self):
        return self.phone

    def _device_json(self):
        return json.dumps([{"id": bytes(device.id()).hex(), "name": device.description()}
                           for device in self._video_devices], ensure_ascii=False)

    @Slot()
    def _devices_changed(self):
        # Some Windows camera drivers block enumeration while capture is active.
        # A device change is refreshed after capture closes, never per result.
        self._devices_dirty = True
        if self.camera is None:
            self._refresh_devices()

    def _refresh_devices(self):
        if self._devices_dirty:
            self._video_devices = list(QMediaDevices.videoInputs())
            self._devices_json = self._device_json()
            self._devices_dirty = False
            self.setupChanged.emit()

    @Property(str, notify=changed)
    def stateJson(self):
        return json.dumps(self.state, ensure_ascii=False)

    @Property(str, notify=previewChanged)
    def cameraPreview(self):
        return self.preview

    @Property(str, notify=setupChanged)
    def camerasJson(self):
        return self._devices_json

    @Property(str, notify=setupChanged)
    def availabilityJson(self):
        return self._availability_json

    def validate_start(self, config):
        config = options(config)
        available = json.loads(self.availabilityJson)
        if config["camera"] and not available["camera"]:
            raise ValueError(available["cameraReason"] + "。请查看监督页面的环境修复说明。")
        if config["screen"] and not available["screen"]:
            raise ValueError(available["screenReason"] + "。请查看监督页面的环境修复说明。")
        if config["camera"] and config["cameraSource"] == "phone":
            if self.phone.server is None:
                raise ValueError("请先生成二维码，连接手机摄像头。")
        elif config["camera"]:
            devices = json.loads(self.camerasJson)
            if not devices:
                raise ValueError("没有可用摄像头。可以仅开启屏幕巡查，或连接摄像头后重试。")
            if config["cameraId"] and not any(d["id"] == config["cameraId"] for d in devices):
                raise ValueError("选中的摄像头已断开，请重新选择。")
        return config

    def start(self, config):
        if self.active:
            raise ValueError("监督模式已在运行。")
        if len(self.workers) >= 2:
            raise ValueError("上一轮识别组件仍在释放。请稍候；如果一直没有响应，请重新启动软件。")
        self.config = self.validate_start(config)
        self.active = True
        self.token = uuid4().hex
        self.policy = SupervisionPolicy(self.config, time.monotonic())
        self.calibration = PostureCalibration()
        self.preview = ""
        self.busy = {"camera": False, "screen": False}
        self._submitted_at = {"camera": 0, "screen": 0}
        self.ready = set()
        self._screen_allowed.clear()
        self._failures = {"camera": 0, "screen": 0}
        self._patrolling = False
        self._epoch += 1
        self.state = {"active": True, "cameraStatus": "loading" if self.config["camera"] else "off",
                      "screenStatus": "loading" if self.config["screen"] else "off", "alert": None,
                      "mode": self.config["mode"], "cameraSource": self.config["cameraSource"], "count": 0, "paused": False, "points": [], "boxes": []}
        self.state["calibration"] = self.calibration.state()
        worker = PatrolWorker(self.token, self.config, self)
        self.worker = worker
        self.workers.add(worker)
        worker.ready.connect(self._models_ready)
        worker.result.connect(self._result)
        worker.finished.connect(self._worker_finished)
        worker.start()
        self.timer.start()
        self.changed.emit()

    @Slot()
    def _worker_finished(self):
        worker = self.sender()
        self.workers.discard(worker)
        worker.deleteLater()

    @Slot(str, dict)
    def _models_ready(self, token, result):
        if not self.active or token != self.token:
            return
        for kind in ("camera", "screen"):
            if result.get(kind) == "ready":
                self.ready.add(kind)
                self.state[kind + "Status"] = "ready"
            elif result.get(kind) == "error":
                self.state[kind + "Status"] = "error"
                self.state[kind + "Error"] = result.get(kind + "Error")
        self._tick()
        self.changed.emit()

    def _working(self):
        session = self.backend.active_focus_session
        island = next(iter(self.backend.island_windows.values()), None)
        if not session or island is None:
            return False
        snapshot = island.focus_snapshot()
        return bool(island.focus_running() and snapshot.get("type", "focus") != "break"
                    and not snapshot.get("awaitingChoice") and not getattr(island, "guided_waiting", False))

    def _open_camera(self):
        self._refresh_devices()
        devices = self._video_devices
        device = next((d for d in devices if bytes(d.id()).hex() == self.config["cameraId"]), None)
        if device is None:
            device = QMediaDevices.defaultVideoInput()
        if device.isNull():
            self._camera_error(None, "摄像头已断开")
            return
        self.camera = QCamera(device, self)
        formats = [f for f in device.videoFormats() if 320 <= f.resolution().width() <= 640 and f.resolution().height() <= 480]
        if formats:
            self.camera.setCameraFormat(min(formats, key=lambda f: (abs(f.resolution().width() - 640), abs(f.maxFrameRate() - 15))))
        self.camera.errorOccurred.connect(self._camera_error)
        self.capture = QMediaCaptureSession(self)
        self.sink = QVideoSink(self)
        self.capture.setCamera(self.camera)
        self.capture.setVideoSink(self.sink)
        self.sink.videoFrameChanged.connect(self._frame)
        self._last_frame = time.monotonic()
        self._last_video_seen = self._last_frame
        self.camera.start()

    def _close_camera(self):
        if self.camera is not None:
            self.camera.stop()
            self.capture.setCamera(None)
            self.capture.setVideoSink(None)
            self.camera.deleteLater()
            self.capture.deleteLater()
            self.sink.deleteLater()
        self.capture = self.camera = self.sink = None
        self.preview = ""
        self.state["points"] = []
        self.state["boxes"] = []
        self.state["heldPhone"] = False
        self.state["phoneVisible"] = False
        self.state["handCount"] = 0
        self.state["eyeDirection"] = "unknown"
        self.previewChanged.emit()

    def _camera_error(self, _code, message):
        if not self.active or self.policy is None:
            return
        self.ready.discard("camera")
        self._close_camera()
        self.policy.observe("away", False, time.monotonic(), False)
        self.policy.observe("phone", False, time.monotonic(), False)
        self.state.update(cameraStatus="error", cameraError="无法使用摄像头：" + str(message)[:160] + "。检查 Windows 摄像头权限和其他程序占用后重试。")
        self.changed.emit()

    @Slot(QVideoFrame)
    def _frame(self, frame):
        now = time.monotonic()
        if not self.active or not self._patrolling or "camera" not in self.ready or self.camera is None:
            return
        if frame.isValid():
            self._last_video_seen = now
        if not self.active or not self._patrolling or self.busy["camera"] or now - self._last_frame < .8:
            return
        if not frame.isValid():
            return
        if self.worker.submit("camera", QVideoFrame(frame), {"epoch": self._epoch, "capturedAt": now}):
            self.busy["camera"] = True
            self._submitted_at["camera"] = now
            self._last_frame = now

    @Slot()
    def _tick(self):
        if not self.active:
            return
        if not self.backend.active_focus_session:
            self.stop()
            return
        working = self._working()
        if working != self._patrolling:
            self._epoch += 1
            if self.worker:
                self.worker.set_epoch(self._epoch, working)
            self.busy = {"camera": False, "screen": False}
            self._submitted_at = {"camera": 0, "screen": 0}
            self._patrolling = working
            self.policy.reset_evidence()
            self.state["alert"] = None
            self.state["paused"] = not working
            if not working:
                if self.calibration.phase in ("learning", "other"):
                    self.calibration.cancel()
                    self.state["calibration"] = self.calibration.state()
                if self.phone.server:
                    self.phone.server.set_running(False)
                self._close_camera()
                self.state["cameraStatus"] = "paused" if self.config["camera"] else "off"
                self.state["screenStatus"] = "paused" if self.config["screen"] else "off"
                self.state["screenTitle"] = ""
            else:
                for kind in self.ready:
                    self.state[kind + "Status"] = "ready"
            self.changed.emit()
        if not working:
            return
        now = time.monotonic()
        if self.calibration.phase in ("learning", "other") and now - self.calibration.started > 25:
            self.calibration.observe({}, now)
            self.state["calibration"] = self.calibration.state()
            self.changed.emit()
        for kind in tuple(self.ready):
            if self.busy[kind] and now - self._submitted_at[kind] > 12:
                # Keep focus and controls working even if a native detector stalls.
                self.ready.discard(kind)
                self.busy[kind] = False
                self.policy.reset_evidence()
                self.state[kind + "Status"] = "error"
                self.state[kind + "Error"] = "本地识别响应超时，已暂停此项检测；专注计时会继续，可返回后重试。"
                if kind == "camera" and self.phone.server:
                    self.phone.server.set_running(False)
                self.changed.emit()
        self._screen_allowed = {key: until for key, until in self._screen_allowed.items() if until > now}
        if "camera" in self.ready and self.config["cameraSource"] == "phone":
            self._phone_frame(now)
        elif "camera" in self.ready and self.camera is None:
            self._open_camera()
        if self.camera is not None and now - self._last_video_seen > 8:
            self._camera_error(None, "长时间未收到摄像头画面")
        if "screen" not in self.ready or self.busy["screen"]:
            return
        if now - self.state.get("screenSampleAt", 0) < 7:
            return
        info = self.backend._foreground_window_info()
        if not info:
            self.policy.observe("screen", False, now, False)
            self.state.update(screenStatus="unknown", screenLabel="无法读取当前窗口，不会记为分心")
            self.changed.emit()
            return
        hwnd, pid, title, process, path = info
        if pid == os.getpid():
            self.policy.observe("screen", False, now)
            self.state.update(screenStatus="self", screenLabel="当前为 FlowTodo；使用电脑学习可切到小窗", screenTitle="")
            self.changed.emit()
            return
        key = f"{hwnd}:{pid}:{title[:200]}"
        allowed_apps = self.backend.settings_database.get("focusGuardWhitelist", [])
        allowed = any(str(item.get("process", "")).lower() == process or (path and str(item.get("path", "")).lower() == path.lower())
                      for item in allowed_apps if isinstance(item, dict))
        allowed = allowed or self._screen_allowed.get(key, 0) > now
        if self.worker.submit("screen", metadata={"hwnd": hwnd, "process": process, "title": title,
                                                   "windowKey": key, "allowed": allowed, "epoch": self._epoch, "capturedAt": now}):
            self.busy["screen"] = True
            self._submitted_at["screen"] = now
            self.state["screenSampleAt"] = now

    def _phone_frame(self, now):
        server = self.phone.server
        if server is None:
            self.state.update(cameraStatus="unknown", cameraError="手机已断开，请返回重新配对。")
            self.changed.emit()
            return
        server.set_running(True)
        if self.busy["camera"]:
            return
        frame = server.take_frame()
        if frame is None or now - frame[1] > 4:
            if now - self._last_video_seen > 5:
                self.policy.reset_evidence()
                self.preview = ""
                self.previewChanged.emit()
                self.state.update(cameraStatus="waitingPhone", points=[], boxes=[], heldPhone=False, handCount=0, eyeDirection="unknown")
                self.changed.emit()
            return
        image, captured_at = frame
        if self.worker.submit("camera", image, {"epoch": self._epoch, "capturedAt": captured_at}):
            self.busy["camera"] = True
            self._submitted_at["camera"] = now
            self._last_video_seen = captured_at

    @Slot(str, str, dict)
    def _result(self, token, kind, evidence):
        if not self.active or token != self.token or kind not in self.ready:
            return
        if evidence.get("epoch", self._epoch) != self._epoch:
            return
        self.busy[kind] = False
        if not self._patrolling or not self._working():
            return
        now = time.monotonic()
        # Results from slow inference cannot provide current evidence.
        if now - evidence.get("sampleAt", now) > 5:
            return
        if "error" in evidence:
            self._failures[kind] += 1
            self.state[kind + "Status"] = "error"
            self.state[kind + "Error"] = evidence["error"]
            self.policy.reset_evidence()
            if self._failures[kind] >= 3:
                self.ready.discard(kind)
                if kind == "camera":
                    self._close_camera()
                self.state[kind + "Error"] += " 连续读取失败，已停止此项；可停止监督后重试。"
            self.changed.emit()
            return
        self._failures[kind] = 0
        self.state.pop(kind + "Error", None)
        if kind == "camera":
            self.preview = evidence.pop("preview", "")
            self.previewChanged.emit()
            self.state.update(points=evidence["points"], boxes=evidence["boxes"], person=evidence["present"],
                              upperBody=evidence["upperBody"], phoneVisible=evidence["phoneVisible"], heldPhone=evidence["heldPhone"],
                              handCount=evidence.get("handCount", 0), eyeDirection=evidence.get("eyeDirection", "unknown"))
            self.state["cameraStatus"] = "hands" if evidence.get("handCount") else "tracking" if evidence["upperBody"] else "partial" if evidence["present"] else "absent" if evidence["observable"] else "unknown"
            if self.config["cameraSource"] == "phone" and not evidence.get("present"):
                # A desk view can lose hands while the person is still seated.
                evidence["observable"] = False
                self.state["cameraStatus"] = "deskUnknown"
            calibrating = self.calibration.phase in ("learning", "other")
            verdict = self.calibration.observe(evidence.get("features", {}), now)
            self.state["calibration"] = self.calibration.state()
            policy_evidence = dict(evidence)
            if self.calibration.phase == "ready" and verdict == "learning":
                policy_evidence["heldPhone"] = False  # The user's learning example can include a nearby phone.
            alert = self.policy.camera(policy_evidence, now) if not calibrating and self.state.get("alert") is None else None
            if not calibrating and self.state.get("alert") is None:
                posture = self.policy.observe("posture", verdict == "other", now, verdict != "unknown")
                alert = alert or posture
            pending_posture = self.policy.pending.get("posture", now)
            self.state["calibration"]["alarmRemaining"] = 0 if alert and alert["kind"] == "posture" else max(0, 5 - int(now - pending_posture))
            self.state["calibration"]["alarmExempt"] = now < self.policy.exempt_until.get("posture", 0)
        else:
            info = self.backend._foreground_window_info()
            if evidence.get("hwnd") and (not info or info[0] != evidence["hwnd"] or info[2][:90] != evidence["title"]):
                self.policy.observe("screen", False, now, False)
                return  # User switched windows while OCR was working.
            self.state.update(screenStatus=evidence["status"], screenLabel=evidence["label"],
                              screenTitle=evidence["title"], windowKey=evidence["windowKey"])
            if self.calibration.phase in ("learning", "other"):
                self.policy.observe("screen", False, now)
                alert = None  # Don't scold the user for demonstrating the requested example.
            else:
                alert = self.policy.observe("screen", evidence["suspect"], now) if self.state.get("alert") is None else None
        if alert and self.state.get("alert") is None:
            titles = {"away": "暂时没看到你，回来继续这一段？", "phone": "你可能正在用手机，要不要先放一边？", "screen": "当前内容可能偏离任务，要回到学习吗？", "posture": "非学习姿态已持续 5 秒，请回到任务"}
            if alert["kind"] == "posture" and self.calibration.reason == "unstable":
                titles["posture"] = "姿态不稳定已持续 5 秒，请回到任务"
            alert.update(id=uuid4().hex, title=titles[alert["kind"]],
                         detail="检测是近似判断；查资料、思考和短暂调整都很正常。", windowKey=self.state.get("windowKey", ""))
            self.state["alert"] = alert
            self.state["count"] = self.policy.alert_count
            self.alertRaised.emit(json.dumps(alert, ensure_ascii=False))
        self.changed.emit()

    @Slot(str)
    def calibrate(self, kind):
        if not self.active or not self._patrolling or "camera" not in self.ready:
            return
        try:
            if kind == "cancel":
                self.calibration.cancel()
            else:
                self.calibration.start(kind, time.monotonic())
        except ValueError as error:
            self.calibration.message = str(error)
        self.policy.reset_evidence()
        self.state["alert"] = None
        self.state["calibration"] = self.calibration.state()
        self.changed.emit()

    @Slot(str, str)
    def resolveAlert(self, alert_id, action):
        alert = self.state.get("alert")
        if not alert or alert["id"] != alert_id or action not in ("back", "allow", "wrong", "rest"):
            return
        now = time.monotonic()
        if action in ("allow", "wrong"):
            if alert["kind"] == "screen":
                self._screen_allowed[alert["windowKey"]] = now + 300
            else:
                self.policy.exempt(alert["kind"], now, 300)
        self.state["alert"] = None
        self.policy.reset_evidence()
        if action == "rest":
            active = self.backend.focus_journey.active or {}
            self.backend.pauseStepFocus(str(active.get("progress", "")), str(active.get("step", "")))
            self._tick()
        self.changed.emit()

    def stop(self):
        was_active = self.active
        self.active = False
        self.token = ""
        self.timer.stop()
        self._close_camera()
        self.phone.close()
        if self.worker is not None:
            self.worker.stop()
        self.worker = None
        self.ready.clear()
        self._screen_allowed.clear()
        self.state.update(active=False, cameraStatus="off", screenStatus="off", alert=None,
                          screenTitle="", windowKey="", points=[], boxes=[], heldPhone=False, phoneVisible=False,
                          person=False, upperBody=False, cameraError="", screenError="", screenLabel="")
        self.policy = None
        self._refresh_devices()
        self.changed.emit()
        if was_active:
            self.stopped.emit()

    def shutdown(self):
        self.stop()
        for worker in list(self.workers):
            worker.stop()
            worker.wait(1000)
