"""Native Qt Quick implementation of FlowTodo's focus floating island."""

import json
import os
import sys
import time
import ctypes
import ctypes.wintypes
from urllib.parse import unquote, urlparse

from playsound import playsound
from PySide6.QtCore import QMetaObject, QPoint, QTimer, Qt, QUrl, Signal
from PySide6.QtGui import QColor, QCursor
from PySide6.QtQuick import QQuickView
from PySide6.QtWidgets import QApplication

try:
    from plyer import notification
    USE_SYSTEM_NOTIFICATION = True
except ImportError:
    notification = None
    USE_SYSTEM_NOTIFICATION = False

try:
    import pygame
except ImportError:
    pygame = None


def send_windows_notification(title: str, message: str, duration: int = 5):
    """Send the system notification used by completed focus sessions."""
    try:
        sound_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audio.mp3")
        if os.path.isfile(sound_path):
            playsound(sound_path, block=False)
        if USE_SYSTEM_NOTIFICATION and notification is not None:
            notification.notify(title=title, message=message, timeout=duration, app_name="FlowTodo")
        else:
            print(f"[Notification] {title}: {message}")
    except Exception as exc:
        print(f"[Island] Windows notification failed: {exc}")


class DynamicIslandBridge(QQuickView):
    """A lightweight, native QML focus window.

    The former WebEngine island owned its timer in JavaScript. This version keeps
    all session state in Python and uses QML only for visual state and interaction.
    That removes Chromium from the focus-window lifecycle entirely.
    """

    signalStateChanged = Signal(str)

    def __init__(self, tasks=None, mode="group", options=None, preferences=None):
        super().__init__()
        self.setTitle("FlowTodo Focus Island")
        self.setColor(QColor(Qt.transparent))
        self.setResizeMode(QQuickView.SizeViewToRootObject)
        self.setFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)

        self.tasks = list(tasks or [])
        self.mode = mode
        self.options = dict(options or {})
        self._preferences = self._normalized_preferences(preferences)
        self.current_index = 0
        self._remaining = 0
        self._total = 0
        self._started_at = None
        self._finished = False
        self._cancelled = False
        self._expanded = False
        self._root = None
        self._page_ready = False
        self._pending_guard_alerts = []
        self._noise_active = False
        self._drag_origin = QPoint()
        self._drag_pointer_offset = QPoint()
        self._style_hints = QApplication.styleHints()
        if hasattr(self._style_hints, "colorSchemeChanged"):
            self._style_hints.colorSchemeChanged.connect(self._on_system_color_scheme_changed)

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)

        self.statusChanged.connect(self._on_qml_status)
        qml_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "qml", "FocusIsland.qml")
        self.setSource(QUrl.fromLocalFile(qml_path))
        self.resize(640, 220)
        self._apply_window_preferences()

    @staticmethod
    def _normalized_preferences(preferences):
        defaults = {
            "islandTheme": "material",
            "nativeAccent": "#0f6cbd",
            "islandScale": 1.0,
            "islandOpacity": 1.0,
            "islandAnchor": "top_center",
            "islandOffsetX": 0,
            "islandOffsetY": 96,
            "islandLayer": "top",
            "islandLightingEffect": True,
        }
        result = dict(defaults)
        if isinstance(preferences, dict):
            result.update({key: preferences[key] for key in defaults if key in preferences})
        try:
            result["islandScale"] = max(0.75, min(1.35, float(result["islandScale"])))
        except (TypeError, ValueError):
            result["islandScale"] = defaults["islandScale"]
        try:
            result["islandOpacity"] = max(0.35, min(1.0, float(result["islandOpacity"])))
        except (TypeError, ValueError):
            result["islandOpacity"] = defaults["islandOpacity"]
        for key in ("islandOffsetX", "islandOffsetY"):
            try:
                result[key] = int(float(result[key]))
            except (TypeError, ValueError):
                result[key] = defaults[key]
        result["islandTheme"] = str(result["islandTheme"] or "material")
        result["nativeAccent"] = str(result["nativeAccent"] or "")
        result["islandAnchor"] = str(result["islandAnchor"] or "top_center")
        result["islandLayer"] = "bottom" if result["islandLayer"] == "bottom" else "top"
        result["islandLightingEffect"] = bool(result["islandLightingEffect"])
        return result

    def _on_qml_status(self, status):
        if status != QQuickView.Ready or self._page_ready:
            return
        self._root = self.rootObject()
        if self._root is None:
            return
        self._page_ready = True
        self._root.pauseRequested.connect(self.pause_focus)
        self._root.resumeRequested.connect(self.resume_focus)
        self._root.cancelRequested.connect(self.cancel_focus)
        self._root.dragStarted.connect(self._start_drag)
        self._root.dragMoved.connect(self._move_drag)
        self._root.dragFinished.connect(self._finish_drag)
        self._root.displayModeChanged.connect(self._on_display_mode_changed)
        self._root.exitFinished.connect(self.close)
        self._apply_qml_preferences()
        self._load_and_start_task(0)
        QTimer.singleShot(80, self._enter)
        QTimer.singleShot(120, self._flush_pending_guard_alerts)

    def _move_to_screen_top(self):
        screen = self.screen() or QApplication.primaryScreen()
        if screen is None:
            return
        geometry = screen.availableGeometry()
        anchor = self._preferences["islandAnchor"]
        offset_x = self._preferences["islandOffsetX"]
        offset_y = self._preferences["islandOffsetY"]
        if anchor.endswith("left"):
            x = geometry.x() + offset_x
        elif anchor.endswith("right"):
            x = geometry.x() + geometry.width() - self.width() - offset_x
        else:
            x = geometry.x() + (geometry.width() - self.width()) // 2 + offset_x
        y = geometry.y() + geometry.height() - self.height() - offset_y if anchor.startswith("bottom") else geometry.y() + offset_y
        self.setPosition(QPoint(x, y))

    def _apply_qml_preferences(self):
        self._set_root_property("themeName", self._preferences["islandTheme"])
        self._set_root_property("customAccent", self._preferences["nativeAccent"])
        self._set_root_property("islandScale", self._preferences["islandScale"])
        self._set_root_property("lightingEffect", self._preferences["islandLightingEffect"])
        self._set_root_property("systemDark", self._system_is_dark())

    def _system_is_dark(self):
        """Use Qt's Windows color-scheme integration, with a safe Qt 6 fallback."""
        try:
            scheme = self._style_hints.colorScheme()
            dark_scheme = getattr(getattr(Qt, "ColorScheme", None), "Dark", None)
            return scheme == dark_scheme or str(scheme).lower().endswith("dark")
        except Exception:
            return False

    def _on_system_color_scheme_changed(self, _scheme):
        self._set_root_property("systemDark", self._system_is_dark())

    def _apply_window_preferences(self, recreate_flags=True):
        self.setOpacity(self._preferences["islandOpacity"])
        if recreate_flags:
            flags = Qt.FramelessWindowHint | Qt.Tool
            flags |= Qt.WindowStaysOnBottomHint if self._preferences["islandLayer"] == "bottom" else Qt.WindowStaysOnTopHint
            self.setFlags(flags)
        self._move_to_screen_top()

    def update_preferences(self, preferences):
        """Apply appearance and location changes without interrupting the timer."""
        self._preferences = self._normalized_preferences(preferences)
        self._apply_window_preferences()
        self._apply_qml_preferences()
        if self.isVisible():
            self.show()

    def _invoke(self, method):
        if self._root is not None:
            QMetaObject.invokeMethod(self._root, method)

    def _enter(self):
        self._invoke("enterIsland")

    def _set_root_property(self, name, value):
        if self._root is not None:
            self._root.setProperty(name, value)

    def _environment_text(self):
        labels = []
        if self.options.get("wallpaperEnabled") or self.options.get("wallpaper"):
            labels.append("壁纸")
        if self.options.get("disableOtherApps") or self.options.get("disableApps"):
            labels.append("专注护盾")
        if self.options.get("whiteNoiseEnabled") or self.options.get("whiteNoise"):
            labels.append(self.options.get("whiteNoiseName") or "白噪音")
        return "  ·  ".join(str(item) for item in labels)

    def _load_and_start_task(self, index):
        if index >= len(self.tasks):
            self._on_all_tasks_completed()
            return
        self.current_index = index
        task = self.tasks[index]
        self._total = max(0, int(task.get("time", 0) or 0))
        self._remaining = self._total
        self._started_at = time.monotonic()

        if self.mode == "project":
            phase = f"里程碑 {index + 1}/{len(self.tasks)}"
            status = "攻坚中"
        else:
            phase = f"阶段 {index + 1}/{len(self.tasks)}"
            status = "专注中" if task.get("type", "focus") == "focus" else "休息中"

        self._set_root_property("taskTitle", str(task.get("title") or "任务"))
        self._set_root_property("taskSubtitle", str(task.get("subtitle") or ""))
        self._set_root_property("phaseLabel", phase)
        self._set_root_property("statusLabel", status)
        self._set_root_property("taskType", str(task.get("type") or "focus"))
        self._set_root_property("totalSeconds", self._total)
        self._set_root_property("remainingSeconds", self._remaining)
        self._set_root_property("running", True)
        self._set_root_property("taskRevision", index)
        self._start_noise()
        self._timer.start()
        self._emit_state("task")

    def _tick(self):
        if self._remaining <= 0:
            return
        self._remaining = max(0, self._remaining - 1)
        self._set_root_property("remainingSeconds", self._remaining)
        if self._remaining == 0:
            self._timer.stop()
            self._stop_noise()
            self._set_root_property("running", False)
            self._emit_state("task_done", 0)
            next_index = self.current_index + 1
            if next_index < len(self.tasks):
                QTimer.singleShot(320, lambda: self._load_and_start_task(next_index))
            else:
                self._on_all_tasks_completed()

    def pause_focus(self):
        if self._finished or self._cancelled or not self._timer.isActive():
            return
        self._timer.stop()
        self._stop_noise()
        self._set_root_property("running", False)
        self._set_root_property("statusLabel", "已暂停")
        self._emit_state("paused", self._remaining)

    def resume_focus(self):
        if self._finished or self._cancelled or self._remaining <= 0 or self._timer.isActive():
            return
        self._started_at = time.monotonic()
        self._timer.start()
        self._start_noise()
        task = self._current_task()
        status = "攻坚中" if self.mode == "project" else ("专注中" if task.get("type", "focus") == "focus" else "休息中")
        self._set_root_property("running", True)
        self._set_root_property("statusLabel", status)
        self._emit_state("resumed", self._remaining)

    def _on_display_mode_changed(self, mini_mode):
        self._expanded = not bool(mini_mode)
        self._emit_state("mini" if mini_mode else "expanded", self._remaining)

    def _start_drag(self):
        self._drag_origin = self.position()
        # Use global coordinates on both sides of the drag. QML local coordinates
        # can be device-independent while the native window position is physical.
        self._drag_pointer_offset = QCursor.pos() - self.frameGeometry().topLeft()

    def _move_drag(self, delta_x, delta_y):
        del delta_x, delta_y
        self.setPosition(QCursor.pos() - self._drag_pointer_offset)

    def _finish_drag(self):
        self._drag_origin = self.position()

    def _current_task(self):
        if 0 <= self.current_index < len(self.tasks):
            return self.tasks[self.current_index]
        return {}

    def _elapsed_seconds(self, remaining=None):
        total = int(self._current_task().get("time", 0) or 0)
        if remaining is not None and total > 0:
            return max(0, min(total, total - remaining))
        return max(0, total - self._remaining)

    def _state_payload(self, event, remaining=None):
        current = self._current_task()
        total_seconds = sum(int(task.get("time", 0) or 0) for task in self.tasks)
        completed_seconds = sum(int(task.get("time", 0) or 0) for task in self.tasks[:self.current_index])
        completed_seconds += self._elapsed_seconds(remaining)
        return {
            "event": event,
            "mode": self.mode,
            "index": self.current_index,
            "totalTasks": len(self.tasks),
            "title": current.get("title", "任务"),
            "subtitle": current.get("subtitle", ""),
            "type": current.get("type", "focus"),
            "taskSeconds": int(current.get("time", 0) or 0),
            "remaining": remaining,
            "completedSeconds": max(0, min(total_seconds, completed_seconds)),
            "totalSeconds": total_seconds,
            "cancelled": self._cancelled,
            "finished": self._finished,
        }

    def _emit_state(self, event, remaining=None):
        self.signalStateChanged.emit(json.dumps(self._state_payload(event, remaining), ensure_ascii=False))

    def cancel_focus(self):
        if self._finished or self._cancelled:
            return
        self._cancelled = True
        self._timer.stop()
        self._stop_noise()
        self._set_root_property("running", False)
        self._set_root_property("exitCancelled", True)
        self._emit_state("cancelled", self._remaining)
        self._invoke("exitIsland")

    def show_guard_alert(self, title="其他应用"):
        message = f"检测到切换到 {str(title or '其他应用')[:60]}，请回到当前专注"
        if not self._page_ready:
            self._pending_guard_alerts.append(message)
            return
        self._set_root_property("guardMessage", message)
        self._invoke("showGuard")

    def _flush_pending_guard_alerts(self):
        if self._pending_guard_alerts:
            self._set_root_property("guardMessage", self._pending_guard_alerts[-1])
            self._invoke("showGuard")
            self._pending_guard_alerts.clear()

    def _on_all_tasks_completed(self):
        if self._finished:
            return
        self._finished = True
        self._timer.stop()
        self._stop_noise()
        self._set_root_property("running", False)
        self._set_root_property("exitCancelled", False)
        self._emit_state("completed", 0)
        if self.mode == "project":
            send_windows_notification("FlowTodo: 项目攻坚完成", "所有项目里程碑已顺利完成")
        else:
            send_windows_notification("FlowTodo: 任务完成", "所有专注任务已完成")
        self._invoke("exitIsland")

    def _noise_path(self):
        source = self.options.get("whiteNoiseData")
        if not source:
            return ""
        if str(source).startswith("file:"):
            return unquote(urlparse(str(source)).path.lstrip("/"))
        return str(source)

    def _start_noise(self):
        path = self._noise_path()
        if not path or pygame is None or self._noise_active:
            return
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            pygame.mixer.music.load(path)
            pygame.mixer.music.play(-1)
            self._noise_active = True
        except Exception as exc:
            print(f"[Island] White noise unavailable: {exc}")

    def _stop_noise(self):
        if pygame is not None and self._noise_active:
            try:
                pygame.mixer.music.stop()
            except Exception:
                pass
        self._noise_active = False

    def closeEvent(self, event):
        self._timer.stop()
        self._stop_noise()
        super().closeEvent(event)

    def _island_hit_rect(self):
        mini_mode = bool(self._root.property("miniMode")) if self._root is not None else False
        guard_visible = bool(self._root.property("guardVisible")) if self._root is not None else False
        scale = self._preferences["islandScale"]
        width = int((482 if guard_visible else (224 if mini_mode else 482)) * scale)
        height = int((72 if guard_visible or mini_mode else 132) * scale)
        return (self.width() - width) // 2, (self.height() - height) // 2, width, height

    def nativeEvent(self, event_type, message):
        # Do not override WM_NCHITTEST here. Windows sends physical-pixel cursor
        # coordinates while QQuickView exposes device-independent geometry; mixing
        # the two made the whole island click-through on scaled displays.
        return super().nativeEvent(event_type, message)
