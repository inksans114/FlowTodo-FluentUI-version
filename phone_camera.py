"""Qt pairing facade; TLS setup and network shutdown never block the GUI."""
from __future__ import annotations

import base64
import io
import json
import os
import subprocess
import threading
import time
from pathlib import Path

from PySide6.QtCore import QObject, Property, QTimer, Signal, Slot
from PySide6.QtNetwork import QNetworkInterface

from phone_camera_server import PhoneStreamServer, private_host
from phone_network import ranked_interfaces


class PhoneCamera(QObject):
    changed = Signal()
    prepared = Signal(int, object, str, str, str)

    def __init__(self, backend):
        super().__init__(backend)
        self.directory = Path(backend.data_dir) / "phone-camera"
        self.server = None
        self.request = 0
        self._prepare_lock = threading.Lock()
        self.state = {"phase": "off", "url": "", "qr": "", "error": ""}
        rows = []
        for interface in QNetworkInterface.allInterfaces():
            flags = interface.flags()
            for entry in interface.addressEntries():
                rows.append({"ip": entry.ip().toString(), "name": interface.humanReadableName(),
                             "type": interface.type().name,
                             "up": bool(flags & QNetworkInterface.IsUp),
                             "running": bool(flags & QNetworkInterface.IsRunning)})
        self.interfaces = ranked_interfaces(rows)
        self.hosts = [row["ip"] for row in self.interfaces]
        self.prepared.connect(self._prepared)
        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self._poll)

    @Property(str, notify=changed)
    def stateJson(self):
        return json.dumps(self.state, ensure_ascii=False)

    @Property(str, constant=True)
    def addressesJson(self):
        return json.dumps(self.hosts)

    @Property(str, constant=True)
    def interfacesJson(self):
        return json.dumps(self.interfaces, ensure_ascii=False)

    @Slot(str)
    def pair(self, host):
        if host not in self.hosts:
            self.state.update(phase="error", error="没有可用局域网地址，请连接 Wi-Fi 后重新打开软件。")
            self.changed.emit()
            return
        self.close()
        self.request += 1
        request = self.request
        self.state.update(phase="starting", error="")
        self.changed.emit()

        def create():
            server = None
            try:
                import qrcode
                # A cancelled preparation can still be finishing on another
                # thread. Serialize certificate writes before a new pairing.
                with self._prepare_lock:
                    if request != self.request:
                        return
                    server = PhoneStreamServer(host, self.directory)
                image = qrcode.make(server.url, box_size=6, border=3)
                output = io.BytesIO()
                image.save(output, format="PNG")
                qr = "data:image/png;base64," + base64.b64encode(output.getvalue()).decode("ascii")
                output = io.BytesIO()
                qrcode.make(server.check_url, box_size=6, border=3).save(output, format="PNG")
                check_qr = "data:image/png;base64," + base64.b64encode(output.getvalue()).decode("ascii")
                self.prepared.emit(request, server, qr, check_qr, "")
            except Exception as error:
                if server:
                    server.close()
                try:
                    self.prepared.emit(request, None, "", "", "手机连接准备失败：" + str(error)[:220])
                except RuntimeError:
                    pass
        threading.Thread(target=create, daemon=True).start()

    @Slot(int, object, str, str, str)
    def _prepared(self, request, server, qr, check_qr, error):
        if request != self.request:
            if server:
                threading.Thread(target=server.close, daemon=True).start()
            return
        if error:
            self.state.update(phase="error", error=error)
        else:
            self.server = server
            self.state.update(phase="waiting", url=server.url, qr=qr, fingerprint=server.fingerprint, error="")
            self.state.update(checkUrl=server.check_url, checkQr=check_qr,
                              networkSeen=False, httpsSeen=False)
            self.timer.start()
        self.changed.emit()

    @Slot()
    def _poll(self):
        if not self.server:
            return
        now = time.monotonic()
        with self.server.lock:
            phase = "streaming" if self.server.running and now - self.server.last_frame < 4 else "connected" if now - self.server.last_seen < 5 else "waiting"
            seen, https = bool(self.server.last_probe), bool(self.server.last_page)
        if (self.state["phase"], self.state.get("networkSeen"), self.state.get("httpsSeen")) != (phase, seen, https):
            self.state.update(phase=phase, networkSeen=seen, httpsSeen=https)
            self.changed.emit()

    @Slot()
    def allowNetwork(self):
        """User-triggered UAC helper, scoped to this application's listening ports."""
        if os.name != "nt" or not self.server:
            return
        import ctypes
        script = Path(__file__).resolve().parent / "tools" / "allow_phone_camera.ps1"
        args = ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script),
                "-HostAddress", self.server.host, "-Ports", f"{self.server.http.server_port},{self.server.check_http.server_port}",
                "-AppPid", str(os.getpid())]
        code = ctypes.windll.shell32.ShellExecuteW(None, "runas", "powershell.exe", subprocess.list2cmdline(args), None, 0)
        self.state["error"] = "请完成 Windows 管理员确认，然后重新扫码。只放行本程序当前两个局域网端口，不关闭防火墙。" if code > 32 else "未获得管理员授权，连接规则未修改。可以在 Windows 安全中心手动允许此程序连接。"
        self.changed.emit()

    @Slot()
    def close(self):
        self.request += 1
        self.timer.stop()
        server, self.server = self.server, None
        if server:
            server.set_running(False)
            # Invalidate the link immediately, even before the socket closes.
            with server.lock:
                server.closed = True
                server.token = ""
            threading.Thread(target=server.close, daemon=True).start()
        self.state = {"phase": "off", "url": "", "qr": "", "error": ""}
        self.changed.emit()
