"""A dedicated native WebEngine window, outside the QML scene graph."""
import os
from pathlib import Path

from PySide6.QtCore import QObject, Property, Qt, QUrl, Signal, Slot, QTimer
from PySide6.QtGui import QColor, QDesktopServices, QKeySequence, QShortcut
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtMultimedia import QSoundEffect


class StudioChannel(QObject):
    stateChanged = Signal(str)

    def __init__(self, backend, parent):
        super().__init__(parent)
        self.backend = backend
        backend.focusSessionChanged.connect(self.publish)

    @Property(str, notify=stateChanged)
    def state(self):
        return self.backend.focusStudioStateJson

    def publish(self):
        self.stateChanged.emit(self.state)

    @Slot(str, str)
    def action(self, name, value):
        self.backend.focusStudioAction(name, value)


class StudioPage(QWebEnginePage):
    def __init__(self, profile, parent, entry_path=None):
        super().__init__(profile, parent)
        self.entry_path = Path(entry_path or Path(__file__).resolve().parent / "focus-studio/index.html").resolve()
        self.console_errors = []
        self.console_messages = []

    def acceptNavigationRequest(self, url, navigation_type, is_main_frame):
        if navigation_type == QWebEnginePage.NavigationTypeLinkClicked and url.toString() in ("https://open-meteo.com/", "https://ipapi.co/"):
            QDesktopServices.openUrl(url)
            return False
        # Pretty-decoded QUrl text differs from Path.as_uri() for spaces/Chinese.
        return url.isLocalFile() and os.path.normcase(str(Path(url.toLocalFile()).resolve())) == os.path.normcase(str(self.entry_path))

    def javaScriptConsoleMessage(self, level, message, line_number, source):
        self.console_messages = (self.console_messages + [message])[-40:]
        if level == QWebEnginePage.JavaScriptConsoleMessageLevel.ErrorMessageLevel:
            self.console_errors = (self.console_errors + [message])[-40:]


class FocusStudioWindow(QWebEngineView):
    def __init__(self, backend):
        super().__init__()
        self.backend = backend
        self.rain_sound = QSoundEffect(self)
        self.reward_sound = QSoundEffect(self)
        self.reward_sound.setSource(QUrl.fromLocalFile(str(Path(__file__).resolve().parent / "focus-studio/assets/reward.wav")))
        backend.guidedReward.connect(self._play_reward)
        self.rain_sound.setLoopCount(QSoundEffect.Infinite.value)
        self.rain_sound.setVolume(.25)
        self.rain_sound.setSource(QUrl.fromLocalFile(str(Path(__file__).resolve().parent / "focus-studio/assets/rain.wav")))
        self.rain_sound.statusChanged.connect(self._sync_rain_sound)
        backend.focusSessionChanged.connect(self._sync_rain_sound)
        self.setObjectName("focusStudioWindow")
        self.setWindowTitle("FlowTodo · 专注")
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setContextMenuPolicy(Qt.NoContextMenu)
        self.resize(1280, 800)
        # An opaque top-level surface avoids compositing a transparent Chromium
        # texture through the application's QML window on every animation frame.
        self.setAttribute(Qt.WA_OpaquePaintEvent)
        self.setStyleSheet("background: #102822;")
        self.profile = QWebEngineProfile(self)
        self.studio_page = StudioPage(self.profile, self)
        self.studio_page.setBackgroundColor(QColor("#102822"))
        self.setPage(self.studio_page)
        settings = self.studio_page.settings()
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, False)
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        settings.setAttribute(QWebEngineSettings.JavascriptCanOpenWindows, False)
        self.channel = QWebChannel(self.studio_page)
        self.bridge = StudioChannel(backend, self.channel)
        self.channel.registerObject("studio", self.bridge)
        self.studio_page.setWebChannel(self.channel)
        self.loaded = False
        self._loading = True
        self._presentation_id = 0
        self._recovery_attempts = 0
        self._ready_watchdog = QTimer(self)
        self._ready_watchdog.setSingleShot(True)
        self._ready_watchdog.setInterval(5000)
        self._ready_watchdog.timeout.connect(self._recover_scene)
        self.loadStarted.connect(self._on_load_started)
        self.loadFinished.connect(self._on_loaded)
        self.studio_page.renderProcessTerminated.connect(self._on_renderer_terminated)
        page_url = QUrl.fromLocalFile(str(Path(__file__).resolve().parent / "focus-studio/index.html"))
        browser_flags = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "").split()
        if "--disable-gpu" in browser_flags and "--enable-unsafe-swiftshader" not in browser_flags:
            page_url.setFragment("software")
        self._entry_url = page_url
        self.setUrl(self._entry_url)
        self._escape_shortcut = QShortcut(QKeySequence("Escape"), self)
        self._escape_shortcut.activated.connect(self._escape)
        self._fullscreen_shortcut = QShortcut(QKeySequence("F11"), self)
        self._fullscreen_shortcut.activated.connect(self._toggle_fullscreen)

    def _on_loaded(self, ok):
        self._loading = False
        self.loaded = bool(ok)
        if not ok:
            self._recover_scene()
        else:
            token = self._presentation_id
            QTimer.singleShot(200, lambda: self._check_scene_ready(token))

    def _on_load_started(self):
        self._loading = True
        self.loaded = False
        self.studio_page.console_errors.clear()
        self.studio_page.console_messages.clear()

    def _on_renderer_terminated(self, _status, _exit_code):
        self.loaded = False
        self._loading = False
        self._recover_scene()

    def _check_scene_ready(self, token):
        if token != self._presentation_id or not self.isVisible() or not self.backend._immersive_active:
            return
        self.studio_page.runJavaScript(
            "Boolean(document.getElementById('timer') && window.flowFocus && window.flowFocus.connected)",
            lambda ready: self._scene_ready(ready, token),
        )

    def _scene_ready(self, ready, token):
        if token != self._presentation_id or not self.isVisible() or not self.backend._immersive_active:
            return
        if not ready:
            return  # The watchdog also covers a renderer that never calls back.
        self._ready_watchdog.stop()
        self.bridge.publish()
        self.update()
        if (self.backend.focus_journey.active or {}).get("source", {}).get("pendingClarification"):
            self.studio_page.runJavaScript("window.flowFocus.showProgressQuestions()")

    def _recover_scene(self):
        if not self.isVisible() or not self.backend._immersive_active:
            return
        if self._recovery_attempts < 1:
            self._recovery_attempts += 1
            self._ready_watchdog.start()
            # Reload the same local page/bridge; the authoritative timer lives outside it.
            token = self._presentation_id
            QTimer.singleShot(0, lambda: self._reload_entry() if token == self._presentation_id and self.isVisible() else None)
        else:
            self._ready_watchdog.stop()
            self.backend.messageRequested.emit("warning", "场景未能加载", "已返回应用，计时和进度仍保留；可以重新进入场景。")
            self.backend.exitFocusStudio()

    def _reload_entry(self):
        self.loaded = False
        self._loading = True
        current_url, entry_url = QUrl(self.url()), QUrl(self._entry_url)
        current_url.setFragment("")
        entry_url.setFragment("")
        if current_url == entry_url:
            # load/setUrl on the same #software URL can be a same-document
            # navigation, leaving an empty cached DOM untouched. Force a reload.
            self.reload()
        else:
            self.load(self._entry_url)

    def present(self):
        self._presentation_id += 1
        self._recovery_attempts = 0
        self._ready_watchdog.start()
        self.studio_page.setLifecycleState(QWebEnginePage.LifecycleState.Active)
        if not self.loaded and not self._loading:
            self._reload_entry()
        self.showFullScreen()
        self.raise_()
        self.activateWindow()
        self.setFocus()
        self.bridge.publish()
        self._sync_rain_sound()
        token = self._presentation_id
        QTimer.singleShot(250, lambda: self._check_scene_ready(token))

    def _sync_rain_sound(self):
        enabled = self.isVisible() and self.backend._immersive_active and bool(self.backend.settings_database.get("focusRainSound", False))
        self.rain_sound.setVolume(max(0., min(1., float(self.backend.settings_database.get("focusRainVolume", .25)))))
        if enabled and self.rain_sound.status() == QSoundEffect.Ready:
            if not self.rain_sound.isPlaying():
                self.rain_sound.play()
        else:
            self.rain_sound.stop()

    def hideEvent(self, event):
        self._presentation_id += 1
        self._ready_watchdog.stop()
        self.rain_sound.stop()
        self.reward_sound.stop()
        super().hideEvent(event)

    def _play_reward(self):
        if not self.isVisible() or not self.backend.settings_database.get("guidedRewardSound", True) or not self.backend.settings_database.get("notificationSoundEnabled", True):
            return
        volume = self.backend._safe_float(self.backend.settings_database.get("notificationSoundVolume"), .8)
        self.reward_sound.setVolume(max(0., min(.4, volume * .4)))
        self.reward_sound.play()

    def _escape(self):
        # Escape closes an HTML thought dialog first, then exits immersion.
        self.studio_page.runJavaScript(
            "(()=>{const d=document.querySelector('dialog[open]');if(d){d.close();return true;}return false;})()",
            lambda handled: None if handled else self.backend.exitFocusStudio(),
        )

    def _toggle_fullscreen(self):
        self.showNormal() if self.isFullScreen() else self.showFullScreen()

    def closeEvent(self, event):
        event.ignore()
        self.backend.exitFocusStudio()
