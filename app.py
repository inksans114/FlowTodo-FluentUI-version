"""Native RinUI/QML entry point for the FlowTodo migration."""

from __future__ import annotations

import os
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
VENDOR_DIR = BASE_DIR / "vendor"

sys.path.insert(0, str(VENDOR_DIR))
sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")
os.chdir(BASE_DIR)

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

from RinUI import RinUIWindow  # noqa: E402
from PySide6.QtCore import QCoreApplication, QObject, QEvent, QTimer, Qt, Slot  # noqa: E402
from PySide6.QtGui import QAction, QIcon  # noqa: E402
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon  # noqa: E402

from compat_backend import RinUIBackend  # noqa: E402
from updater import UpdateManager  # noqa: E402
from version import APP_VERSION  # noqa: E402


class TrayController(QObject):
    """Own the optional Windows tray icon and translate window close into hide."""

    def __init__(self, app: QApplication, backend: RinUIBackend, window):
        super().__init__(app)
        self.app = app
        self.backend = backend
        self.window = window
        self._allow_close = False
        self.tray = QSystemTrayIcon(self)
        icon_path = BASE_DIR / "logopromax.ico"
        if icon_path.exists():
            self.tray.setIcon(QIcon(str(icon_path)))
        self.tray.setToolTip("FlowTodo")

        self.menu = QMenu()
        open_action = QAction("打开 FlowTodo", self.menu)
        open_action.triggered.connect(self.show_window)
        new_note_action = QAction("新建便签", self.menu)
        new_note_action.triggered.connect(self.backend.createNote)
        show_notes_action = QAction("显示所有便签", self.menu)
        show_notes_action.triggered.connect(self.backend.showNotes)
        hide_notes_action = QAction("隐藏所有便签", self.menu)
        hide_notes_action.triggered.connect(self.backend.hideNotes)
        show_widget_action = QAction("展开小组件", self.menu)
        show_widget_action.triggered.connect(self.backend.showDesktopWidget)
        quit_action = QAction("退出", self.menu)
        quit_action.triggered.connect(self.quit_application)
        self.menu.addAction(open_action)
        self.menu.addSeparator()
        self.menu.addAction(new_note_action)
        self.menu.addAction(show_notes_action)
        self.menu.addAction(hide_notes_action)
        self.menu.addAction(show_widget_action)
        self.menu.addSeparator()
        self.menu.addAction(quit_action)
        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(self._on_activated)
        self.window.installEventFilter(self)
        self._sync_visibility()

    def _behavior(self) -> str:
        return str(self.backend.getSetting("closeBehavior", "tray") or "tray").lower()

    def _sync_visibility(self) -> None:
        self.tray.setVisible(self._behavior() == "tray")

    def eventFilter(self, watched, event):
        if watched is self.window and event.type() == QEvent.Type.Close and not self._allow_close:
            if self._behavior() == "tray":
                event.ignore()
                self.window.hide()
                self.tray.showMessage("FlowTodo", "已最小化到系统托盘", QSystemTrayIcon.MessageIcon.Information, 1800)
                return True
            self.quit_application()
        return super().eventFilter(watched, event)

    def _on_activated(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            self.show_window()

    @Slot(str, str)
    def show_daily_reminder(self, title: str, message: str):
        self.show_task_reminder("daily", title, message)

    @Slot(str, str, str)
    def show_task_reminder(self, kind: str, title: str, message: str):
        """Use Qt's Windows tray integration for a real system notification banner."""
        was_visible = self.tray.isVisible()
        if not was_visible:
            self.tray.show()
        heading = "日程提醒" if kind == "scheduled" else "每日重复任务提醒"
        self.tray.showMessage(
            heading,
            f"{title}\n{message}",
            QSystemTrayIcon.MessageIcon.Warning,
            6000,
        )
        if not was_visible and self._behavior() != "tray":
            QTimer.singleShot(6500, self.tray.hide)

    @Slot()
    def show_window(self):
        self.window.showNormal()
        self.window.raise_()
        self.window.requestActivate()

    @Slot()
    def quit_application(self):
        self._allow_close = True
        self.tray.hide()
        self.app.quit()


def main() -> int:
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    app = QApplication(sys.argv)
    QCoreApplication.setOrganizationName("FlowTodo")
    QCoreApplication.setApplicationName("FlowTodo Native QML")
    QCoreApplication.setApplicationVersion(APP_VERSION)

    backend = RinUIBackend()
    window = RinUIWindow(shared_engine=False)
    window.engine.rootContext().setContextProperty("Backend", backend)
    window.load(BASE_DIR / "qml" / "Main.qml")
    backend.attach_native_window(window.root_window)
    backend.attach_qml_engine(window.engine)
    # The tray mode must keep the process alive while every UI window is hidden.
    # In direct-exit mode TrayController calls app.quit() explicitly.
    app.setQuitOnLastWindowClosed(False)
    tray_controller = TrayController(app, backend, window.root_window)
    backend.settingsChanged.connect(tray_controller._sync_visibility)
    backend.signalTaskReminder.connect(tray_controller.show_task_reminder)
    update_manager = UpdateManager(app)
    update_manager.statusChanged.connect(
        lambda level, title, message: backend.messageRequested.emit(level, title, message)
    )
    update_manager.quitRequested.connect(tray_controller.quit_application)
    # Keep the controller alive for the lifetime of the application.
    app._flowtodo_tray_controller = tray_controller
    app._flowtodo_update_manager = update_manager
    app.aboutToQuit.connect(backend.shutdown)
    # Delay network work until the first window has finished rendering.
    QTimer.singleShot(1800, update_manager.check_for_updates)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
