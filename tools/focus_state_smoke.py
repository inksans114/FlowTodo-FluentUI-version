"""Check focus drafts through actual navigation, with isolated application data."""
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")
sys.path[:0] = [str(ROOT), str(ROOT / "vendor")]
data = tempfile.TemporaryDirectory(prefix="flowtodo-focus-state-")
os.environ["LOCALAPPDATA"] = data.name
os.environ["FLOWTODO_RINUI_CONFIG_DIR"] = str(Path(data.name) / "rinui")
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["QT_QUICK_BACKEND"] = "software"
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
from PySide6.QtCore import Qt, QTimer
from PySide6.QtQml import QQmlExpression, QQmlEngine
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

QApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
app = QApplication([])
app.setQuitOnLastWindowClosed(False)
from RinUI import RinUIWindow
from compat_backend import RinUIBackend
from i18n_runtime import translator

backend = RinUIBackend()
backend.local_database = [{"id": 101, "title": "Future task", "scheduledDate": "2099-01-01", "done": False}]
window = RinUIWindow(shared_engine=False)
engine = window.engine
engine.rootContext().setContextProperty("Backend", backend)
engine.rootContext().setContextProperty("I18nBridge", translator())
warnings = []
engine.warnings.connect(lambda errors: warnings.extend(e.toString() for e in errors))
window.load(ROOT / "qml/Main.qml")
root = window.root_window


def evaluate(scope, code):
    expression = QQmlExpression(QQmlEngine.contextForObject(scope), scope, code)
    result = expression.evaluate()
    assert not expression.hasError(), expression.error().toString()
    return result


def find(item, name):
    if item.objectName() == name:
        return item
    for child in item.childItems():
        result = find(child, name)
        if result is not None:
            return result


def navigate(name):
    url = (ROOT / "qml/pages" / name).as_uri()
    evaluate(root, "navigationView.push(" + json.dumps(url) + ")")
    QTest.qWait(450)
    return find(root.contentItem(), name.removesuffix(".qml"))


QTest.qWait(400)
page = navigate("FocusWorkspace.qml")
assert page is not None
evaluate(page, "allTasks = true; selectedTaskId = 101; durationMinutes = 37; customDuration = true; showAdvanced = true; showTaskPicker = true; pomodoro = true; roundCount = 6; shieldEnabled = true; scrollPosition = 120")
find(page, "focusStepInput").setProperty("text", "Draft action")
navigate("HomeDashboard.qml")
page = navigate("FocusWorkspace.qml")
assert page.property("selectedTaskId") == 101
assert page.property("durationMinutes") == 37
for flag in ("customDuration", "showAdvanced", "showTaskPicker", "allTasks", "pomodoro", "shieldEnabled"):
    assert page.property(flag), flag
assert page.property("roundCount") == 6
assert find(page, "focusStepInput").property("text") == "Draft action"
assert page.property("scrollPosition") == 120
print("[OK] Navigation restores draft, task filter/selection, options, and scroll.")

backend.focus_journey.data["active"] = {"id": "session-1", "status": "paused", "progress": "Saved progress", "nextAction": "Saved next"}
backend.focusJourneyChanged.emit()
find(page, "focusProgressInput").setProperty("text", "Unsaved progress")
find(page, "focusNextInput").setProperty("text", "Unsaved next")
navigate("HomeDashboard.qml")
page = navigate("FocusWorkspace.qml")
assert find(page, "focusProgressInput").property("text") == "Unsaved progress"
assert find(page, "focusNextInput").property("text") == "Unsaved next"
navigate("HomeDashboard.qml")
backend.focus_journey.data["active"] = {"id": "session-2", "status": "review", "progress": "New session", "nextAction": "New next"}
backend.focusJourneyChanged.emit()
page = navigate("FocusWorkspace.qml")
assert page.property("stage") == "review"
assert find(page, "focusReviewProgress").property("text") == "New session"
assert find(page, "focusReviewNext").property("text") == "New next"
print("[OK] Unsaved session notes survive; new session/phase uses current backend state.")
assert not [w for w in warnings if "ReferenceError" in w or "TypeError" in w], warnings
navigate("HomeDashboard.qml")
backend.shutdown()
root.hide()
app.processEvents()
QTimer.singleShot(0, app.quit)
app.exec()
print("[OK] No QML runtime errors.")
