"""Exercise archiving and actual island continuation with isolated user data."""
import os
import sys
import json
import tempfile
import time
from pathlib import Path
from datetime import datetime, timedelta

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "vendor")]
temp = tempfile.TemporaryDirectory(prefix="flowtodo-retention-qa-")
os.environ["LOCALAPPDATA"] = temp.name
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["QT_QUICK_BACKEND"] = "software"
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
sys.stdout.reconfigure(encoding="utf-8")
from PySide6.QtCore import Qt, QEventLoop, QTimer, QUrl
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlEngine, QQmlComponent
QApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
app = QApplication([])
app.setQuitOnLastWindowClosed(False)
from compat_backend import RinUIBackend
from i18n_runtime import translator
backend = RinUIBackend()
backend._apply_focus_environment = lambda options: None
backend._restore_focus_environment = lambda: None
backend._show_main_window = lambda: None
backend.settings_database["notificationSoundEnabled"] = False


def wait(ms=100):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


old = (datetime.now() - timedelta(days=15)).isoformat()
backend.local_database = [{"id": 5001, "title": "过期普通任务", "createdAt": old, "done": False},
                          {"id": 5002, "title": "长期任务", "createdAt": old, "taskType": "long", "done": False},
                          {"id": 5003, "title": "未来任务", "createdAt": old, "scheduledDate": "2099-01-01", "done": False}]
backend.setSetting("taskAutoArchiveDays", 3)
assert [task["id"] for task in json.loads(backend.tasksJson)] == [5002, 5003]
assert len(json.loads(backend.getArchivedTasks())) == 1
assert backend._task_stats()["done"] == 0
backend.reload()
assert len(json.loads(backend.getArchivedTasks())) == 1
assert backend.restoreArchivedTask(5001)
backend._process_daily_tasks()
assert len(json.loads(backend.tasksJson)) == 3
assert not json.loads(backend.getArchivedTasks())
print("[OK] Archive persists, protects special/future tasks, restores with a new grace period.")
saved_tasks = backend.local_database
backend.local_database = [{"id": 1, "done": True}, {"id": 2, "done": False, "archivedAt": old}]
assert not next(item for item in backend._build_achievements() if item["id"] == "perfect_day")["unlocked"]
backend.local_database = saved_tasks
print("[OK] Archiving unfinished tasks does not unlock the all-tasks-completed achievement.")

assert backend.startStepFocus(5001, 1, "写第一句", False)
wait()
island = next(iter(backend.island_windows.values()))
assert not island.errors(), island.errors()
island._deadline = time.monotonic() - 1
island._tick()
wait()
assert not backend.active_focus_session
assert island.isVisible() and island._root.property("awaitingChoice")
seconds = backend.stats_database["todayFocusSeconds"]
trees = len(backend.focus_journey.data["forest"])
island._root.followupRequested.emit("break")
wait()
island = next(iter(backend.island_windows.values()))
assert island.tasks[0]["type"] == "break"
assert backend.active_focus_session["focusSeconds"] == 0
island._deadline = time.monotonic() - 1
island._tick()
wait()
assert backend.stats_database["todayFocusSeconds"] == seconds
assert len(backend.focus_journey.data["forest"]) == trees
island._root.followupRequested.emit("focus")
wait()
island = next(iter(backend.island_windows.values()))
assert island.tasks[0]["time"] == 60
assert backend.active_focus_session["taskId"] == 5001
island._deadline = time.monotonic() - 1
island._tick()
wait()
assert backend.stats_database["todayFocusSeconds"] == seconds + 60
island._root.followupRequested.emit("dismiss")
wait()
assert not backend.island_windows
print("[OK] Completed island stays; break does not count focus or trees; repeat retains task/duration; dismiss works.")

assert backend.startPomodoroFocus(-1, 1, 2, 10, 3, "", False, 3)
wait()
island = next(iter(backend.island_windows.values()))
island.current_index = len(island.tasks) - 1
island._remaining = 0
island._on_all_tasks_completed()
island._root.followupRequested.emit("break")
wait()
island = next(iter(backend.island_windows.values()))
assert island.tasks[0]["time"] == 600
backend.cancelFocus()
wait(600)
print("[OK] Final custom-cycle break honors the configured long-break cadence.")

from RinUI import RinUIWindow
window = RinUIWindow(shared_engine=False)
engine = window.engine
engine.addImportPath(str(ROOT / "vendor"))
engine.rootContext().setContextProperty("Backend", backend)
engine.rootContext().setContextProperty("I18nBridge", translator())
window.load(ROOT / "qml/Main.qml")
warnings = []
engine.warnings.connect(lambda errors: warnings.extend(error.toString() for error in errors))
objects = []
for name in ("FocusJourney.qml", "AppSettings.qml", "ArchivedTasks.qml"):
    component = QQmlComponent(engine, QUrl.fromLocalFile(str(ROOT / "qml/pages" / name)))
    wait()
    obj = component.create()
    assert obj is not None, [error.toString() for error in component.errors()]
    objects.append(obj)
    if name == "FocusJourney.qml":
        assert obj.property("durationMinutes") == 5
        assert obj.property("immersive") is False
assert not [w for w in warnings if "ReferenceError" in w or "TypeError" in w], warnings
print("[OK] Focus, archive settings, and restore page load without QML runtime errors.")
backend.shutdown()
window.root_window.hide()
app.processEvents()
QTimer.singleShot(0, app.quit)
app.exec()
print("[OK] Application shutdown completed.")
temp.cleanup()
