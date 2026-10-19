"""Small Qt DPI helpers kept in logical-pixel space."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QGuiApplication


class DpiService(QObject):
    screenChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._connected = set()
        self.refresh()
        app = QGuiApplication.instance()
        if app is not None:
            app.screenAdded.connect(self._on_screen)
            app.screenRemoved.connect(lambda _screen: self.refresh())

    @staticmethod
    def describe(screen) -> str:
        if screen is None:
            return "screen=none dpr=1.00"
        geometry = screen.availableGeometry()
        return (
            f"screen={screen.name() or 'unknown'} "
            f"dpr={screen.devicePixelRatio():.2f} "
            f"available={geometry.width()}x{geometry.height()}"
        )

    def refresh(self):
        app = QGuiApplication.instance()
        if app is None:
            return
        for screen in app.screens():
            if id(screen) in self._connected:
                continue
            self._connected.add(id(screen))
            screen.geometryChanged.connect(lambda _rect, self=self: self.screenChanged.emit())
            screen.availableGeometryChanged.connect(lambda _rect, self=self: self.screenChanged.emit())
            screen.logicalDotsPerInchChanged.connect(lambda _dpi, self=self: self.screenChanged.emit())

    def _on_screen(self, _screen):
        self.refresh()
        self.screenChanged.emit()

    def log_snapshot(self):
        app = QGuiApplication.instance()
        if app is None:
            return
        print("[DPI] Qt logical-pixel mode; " + " | ".join(self.describe(s) for s in app.screens()))
