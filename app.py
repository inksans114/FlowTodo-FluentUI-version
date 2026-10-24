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
if sys.platform == "win32":
    # Supervision needs CPU pixels, not a camera/scene-graph GPU texture exchange.
    # Avoid driver readback stalls without disabling acceleration of the QML UI.
    os.environ.setdefault("QT_DISABLE_HW_TEXTURES_CONVERSION", "1")
# Prefer the stable Chromium software compositor on Windows. The QML interface
# keeps its own acceleration; only the small focus scene uses a software z-buffer.
# Opting into accelerated WebEngine is available for machines without the shared
# D3D texture flicker, but is never required for orbit or growth animations.
if os.environ.get("FLOWTODO_WEBENGINE_ACCELERATED") != "1":
    studio_flags = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "").split()
    for studio_flag in ("--disable-gpu", "--disable-gpu-compositing"):
        if studio_flag not in studio_flags:
            studio_flags.append(studio_flag)
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = " ".join(studio_flags)
os.chdir(BASE_DIR)
from app_paths import windows_package_family
if sys.platform == "darwin" or windows_package_family():
    from app_paths import user_data_dir
    # A signed/read-only .app must never be used as a settings directory.
    os.environ.setdefault("FLOWTODO_RINUI_CONFIG_DIR", str(user_data_dir().parent / "RinUI/config"))

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

from runtime_diagnostics import install, install_qt_logging, checkpoint  # noqa: E402
install()
checkpoint("Loading optional native packages")

# MediaPipe's optional drawing imports use six virtual modules. Importing the
# vision packages before PySide's __feature__ import hook avoids a Windows
# shiboken/six incompatibility. This loads code only; no models or devices open.
from supervision_environment import bootstrap  # noqa: E402
bootstrap()
checkpoint("Optional native packages loaded; importing Qt and backend")
install_qt_logging()

from RinUI import RinUIWindow  # noqa: E402
from PySide6.QtCore import QCoreApplication, QObject, QEvent, QTimer, Qt, Slot  # noqa: E402
from PySide6.QtGui import QAction, QIcon  # noqa: E402
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon  # noqa: E402

from compat_backend import RinUIBackend  # noqa: E402
from dpi_utils import DpiService  # noqa: E402
from notification_audio import play_notification_sound, set_backend as set_audio_backend  # noqa: E402
from i18n_runtime import tr, translator  # noqa: E402
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
        self._menu_actions = [
            (QAction(self.menu), "打开 FlowTodo", self.show_window),
            None,
            (QAction(self.menu), "新建便签", self.backend.createNote),
            (QAction(self.menu), "显示所有便签", self.backend.showNotes),
            (QAction(self.menu), "隐藏所有便签", self.backend.hideNotes),
            (QAction(self.menu), "展开小组件", self.backend.showDesktopWidget),
            None,
            (QAction(self.menu), "退出", self.quit_application),
        ]
        for entry in self._menu_actions:
            if entry is None:
                self.menu.addSeparator()
                continue
            action, _source, handler = entry
            action.triggered.connect(handler)
            self.menu.addAction(action)
        self._retranslate_menu()
        translator().languageChanged.connect(self._retranslate_menu)
        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(self._on_activated)
        self.window.installEventFilter(self)
        self._sync_visibility()

    def _retranslate_menu(self) -> None:
        """Tray menus are native widgets, so their labels need a manual refresh."""
        for entry in self._menu_actions:
            if entry is None:
                continue
            action, source, _handler = entry
            action.setText(tr(source))

    def _behavior(self) -> str:
        return str(self.backend.getSetting("closeBehavior", "tray") or "tray").lower()

    def _sync_visibility(self) -> None:
        self.tray.setVisible(self._behavior() == "tray")

    def eventFilter(self, watched, event):
        if watched is self.window and event.type() == QEvent.Type.Close and not self._allow_close:
            if self._behavior() == "tray":
                event.ignore()
                self.window.hide()
                self.tray.showMessage(
                    "FlowTodo",
                    tr("已最小化到系统托盘"),
                    QSystemTrayIcon.MessageIcon.Information,
                    1800,
                )
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
        play_notification_sound()
        was_visible = self.tray.isVisible()
        if not was_visible:
            self.tray.show()
        heading = tr("日程提醒") if kind == "scheduled" else tr("每日重复任务提醒")
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
    checkpoint("Creating QApplication; version=" + APP_VERSION)
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    app = QApplication(sys.argv)
    QCoreApplication.setOrganizationName("FlowTodo")
    QCoreApplication.setApplicationName("FlowTodo Native QML")
    QCoreApplication.setApplicationVersion(APP_VERSION)

    from app_paths import user_data_dir
    from desktop_handoff import Handoff,wake_code,register_protocol
    handoff=Handoff(user_data_dir(),app)
    callback=next((wake_code(value) for value in sys.argv[1:] if wake_code(value)),None)
    if callback and handoff.forward(callback):return 0
    handoff.listen()
    if '--smoke-test' not in sys.argv:
        try:register_protocol(compiled=globals().get('__compiled__'))
        except OSError:pass  # Browser polling remains available if OS registration is restricted.

    checkpoint("Creating backend")
    backend = RinUIBackend()
    set_audio_backend(backend)
    dpi_service = DpiService(app)
    dpi_service.log_snapshot()
    window = RinUIWindow(shared_engine=False)
    window.engine.rootContext().setContextProperty("Backend", backend)
    # Every QML engine needs the translator before loading, because the I18n
    # singleton resolves it as a root context property.
    window.engine.rootContext().setContextProperty("I18nBridge", translator())
    checkpoint("Loading main QML window")
    window.load(BASE_DIR / "qml" / "Main.qml")
    checkpoint("Main QML window loaded")
    window.setIcon(BASE_DIR / "logopromax.ico")
    backend.attach_native_window(window.root_window)
    backend.attach_qml_engine(window.engine)
    def resume_account(code):
        if backend._cloud.wake_login(code):
            window.root_window.showNormal();window.root_window.raise_();window.root_window.requestActivate()
    handoff.wake.connect(resume_account)
    app._flowtodo_handoff=handoff
    if callback:QTimer.singleShot(0,lambda:resume_account(callback))
    # The tray mode must keep the process alive while every UI window is hidden.
    # In direct-exit mode TrayController calls app.quit() explicitly.
    app.setQuitOnLastWindowClosed(False)
    tray_controller = TrayController(app, backend, window.root_window)
    backend.settingsChanged.connect(tray_controller._sync_visibility)
    backend.signalTaskReminder.connect(tray_controller.show_task_reminder)
    update_manager = backend._update_manager
    update_manager.quitRequested.connect(tray_controller.quit_application)
    # Keep the controller alive for the lifetime of the application.
    app._flowtodo_tray_controller = tray_controller
    app._flowtodo_update_manager = update_manager
    app._flowtodo_dpi_service = dpi_service
    app.aboutToQuit.connect(backend.shutdown)
    app.aboutToQuit.connect(lambda: checkpoint("Qt aboutToQuit received"))
    # Delay network work until the first window has finished rendering.
    if "--smoke-test" in sys.argv:
        # Build verification: no updater requests, camera or microphone capture.
        QTimer.singleShot(1000, app.quit)
    else:
        QTimer.singleShot(1800, update_manager.automatic_check)
    checkpoint("Starting Qt event loop")
    result = app.exec()
    checkpoint("Qt event loop exited: " + str(result))
    return result


if __name__ == "__main__":
    raise SystemExit(main())
