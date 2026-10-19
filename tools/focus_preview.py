"""Offscreen QML smoke test and renders, using only temporary application data."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "vendor"))
DATA = tempfile.TemporaryDirectory(prefix="flowtodo-focus-qa-")
os.environ["LOCALAPPDATA"] = DATA.name
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["QT_QUICK_BACKEND"] = "software"
if "--gpu" in sys.argv:
    os.environ.pop("QT_QUICK_BACKEND", None)
    os.environ["QSG_RHI_BACKEND"] = "opengl"
os.environ["QT_QUICK_CONTROLS_STYLE"] = "Basic"
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu --disable-gpu-compositing"

from PySide6.QtCore import QObject, QTimer, QUrl, Qt
from PySide6.QtGui import QFontDatabase
from PySide6.QtQml import QQmlExpression, QQmlComponent
from PySide6.QtQuick import QQuickItem
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from RinUI import RinUIWindow
from compat_backend import RinUIBackend
from focus_journey import FocusJourney
from i18n_runtime import translator

QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
app = QApplication([])
for font in ("msyh.ttc", "segoeui.ttf", "seguisb.ttf"):
    QFontDatabase.addApplicationFont(str(Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / font))
app.setQuitOnLastWindowClosed(False)
backend = RinUIBackend()
backend.settings_database["focusWeatherMode"] = "off"
backend._apply_focus_environment = lambda _options: None
backend._restore_focus_environment = lambda: None
backend._show_main_window = lambda: None
backend._minimize_main_window = lambda: None
backend.local_database = [{"id": 101, "title": "毕业论文 · 文献综述", "scheduledDate": backend._today_key(), "done": False}]
backend.groups_database = [{"id": 201, "name": "晨间写作", "description": "准备材料，再进入两轮写作。",
    "steps": [{"name": "整理资料", "duration": 5}, {"name": "写第一段", "duration": 25}, {"name": "休息", "duration": 5, "type": "break"}]}]
window = RinUIWindow(shared_engine=False)
window.engine.rootContext().setContextProperty("Backend", backend)
window.engine.rootContext().setContextProperty("I18nBridge", translator())
warnings = []
window.engine.warnings.connect(lambda errors: warnings.extend(error.toString() for error in errors))
window.load(ROOT / "qml/Main.qml")
root = window.root_window
assert root is not None, "Main QML failed to load"
backend.attach_native_window(root)
output = ROOT / ".superdesign/qa"
output.mkdir(parents=True, exist_ok=True)


def evaluate(code):
    expression = QQmlExpression(window.engine.rootContext(), root, code)
    result = expression.evaluate()
    if expression.hasError():
        raise AssertionError(expression.error().toString())
    return result


def open_page(name):
    url = QUrl.fromLocalFile(str(ROOT / "qml/pages" / name)).toString()
    evaluate("navigationView.push('" + url + "')")


def find_visual(item, name):
    if item.objectName() == name:
        return item
    for child in item.childItems():
        found = find_visual(child, name)
        if found is not None:
            return found
    return None


def render(name, width=1180, height=760):
    root.setWidth(width)
    root.setHeight(height)
    QTest.qWait(350)
    frame = root.grabWindow()
    assert not frame.isNull(), "No rendered frame"
    assert frame.save(str(output / f"{name}.png"))


QTest.qWait(500)
assert len(root.property("navigationItems").toVariant()) == 6
render("tasks")
open_page("FocusWorkspace.qml")
QTest.qWait(450)
page = find_visual(root.contentItem(), "FocusWorkspace")
if page is None:
    diagnostic = QQmlComponent(window.engine, QUrl.fromLocalFile(str(ROOT / "qml/pages/FocusWorkspace.qml")))
    print("PAGE DIAGNOSTICS", [error.toString() for error in diagnostic.errors()], flush=True)
assert page is not None, "FocusJourney failed to instantiate: " + "\n".join(warnings)
assert page.property("stage") == "prepare"
render("prepare")
render("prepare-compact", 900, 620)
assert backend.startStepFocus(101, 5, "阅读一篇参考文献，记下三个观点", False)
QTest.qWait(350)
island = next(iter(backend.island_windows.values()))
island._deadline -= 70
island._tick()
backend._refresh_focus_snapshot()
assert page.property("stage") == "work"
assert backend.captureFocusThought("晚上记得买东西")
render("work")
render("work-compact", 900, 620)
assert backend.pauseStepFocus("读到第三节，整理了一个观点", "整理第二个观点")
paused = island.focus_snapshot()["remaining"]
QTest.qWait(1100)
assert island.focus_snapshot()["remaining"] == paused
assert page.property("stage") == "paused"
render("return")
assert backend.parkStepFocus("读到第三节，整理了一个观点", "整理第二个观点")
saved = FocusJourney(Path(backend.data_dir) / "focus_journey.json")
assert saved.active["remainingSeconds"] == paused
assert saved.active["status"] == "paused"
step_id = saved.active["id"]
backend.focus_journey = saved
assert backend.pauseStepFocus("读到第三节，补了标记", "整理第二个观点")
assert backend.resumeStepFocus("整理第二个观点")
QTest.qWait(350)
island = next(iter(backend.island_windows.values()))
assert island.tasks[0]["time"] == paused, "Restart rounded away seconds"
assert backend.focus_journey.active["id"] == step_id
island._deadline -= 20
island._tick()
backend._refresh_focus_snapshot()
assert backend.endStepFocus()
assert page.property("stage") == "review"
assert backend.focus_journey.active["elapsedSeconds"] >= 90
assert backend.stats_database["todayFocusSeconds"] < 110, "Early finish recorded planned time"
assert backend.local_database[0]["done"] is False
render("review")
render("review-compact", 900, 620)
assert backend.saveStepReview("整理了三个观点", "写第一段", False)
assert backend.focus_journey.data["checkpoint"]["step"] == "写第一段"
assert backend.local_database[0]["done"] is False
render("prepare-checkpoint")
assert backend.resumeStepFocus("")
QTest.qWait(350)
assert backend.endStepFocus()
assert backend.saveStepReview("文献综述已完成", "", True)
assert backend.local_database[0]["done"] is True
assert len(backend.focus_journey.data["thoughts"]) == 1
session_component = QQmlComponent(window.engine, QUrl.fromLocalFile(str(ROOT / "qml/pages/FocusSessionNative.qml")))
assert not session_component.errors(), [error.toString() for error in session_component.errors()]
# Both paths invoke the same original island queue; immersion is optional.
evaluate("openFocusPreparation('group', 201)")
QTest.qWait(350)
group_page = find_visual(root.contentItem(), "GroupPrepWorkspace")
assert group_page is not None and group_page.property("immersiveEnabled") is False
group_page.setProperty("includeBreaks", False)
start_group = QQmlExpression(window.engine.rootContext(), group_page, "start()")
start_group.evaluate()
assert not start_group.hasError(), start_group.error().toString()
QTest.qWait(350)
group_island = next(iter(backend.island_windows.values()))
assert group_island.isVisible() and group_island.focus_running()
assert [task["title"] for task in group_island.tasks] == ["整理资料", "写第一段", "休息"]
assert [task["type"] for task in group_island.tasks] == ["focus", "focus", "break"]
assert not backend._immersive_active and backend._studio_window is None and root.isVisible()
evaluate("navigationView.push('" + QUrl.fromLocalFile(str(ROOT / "qml/pages/FocusSessionNative.qml")).toString() + "', {mode:'group'})")
QTest.qWait(350)
assert not backend._immersive_active, "Opening a task flow automatically started immersion"
tree_count = len(backend.focus_journey.data["forest"])
backend.cancelFocus()
assert len(backend.focus_journey.data["forest"]) == tree_count
assert backend.saveStepReview("", "", False)
evaluate("openFocusPreparation('group', 201)")
QTest.qWait(350)
group_page = find_visual(root.contentItem(), "GroupPrepWorkspace")
group_page.setProperty("immersiveEnabled", True)
start_group = QQmlExpression(window.engine.rootContext(), group_page, "start()")
start_group.evaluate()
assert not start_group.hasError(), start_group.error().toString()
QTest.qWait(1300)
assert backend._immersive_active and backend._studio_window.isVisible() and not root.isVisible()
assert next(iter(backend.island_windows.values())).focus_running()
backend.cancelFocus()
QTest.qWait(150)
assert not backend._immersive_active and root.isVisible()
assert len(backend.focus_journey.data["forest"]) == tree_count
assert backend.saveStepReview("", "", False)
open_page("ToolsHub.qml")
render("tools")
errors = [warning for warning in warnings if any(word in warning for word in ("ReferenceError", "TypeError", "is not a type", "Cannot assign", "Binding loop", "Error:"))]
if errors:
    raise AssertionError("QML errors:\n" + "\n".join(errors))
backend.shutdown()
root.hide()
app.processEvents()
QTimer.singleShot(0, app.quit)
app.exec()
print(json.dumps({"ok": True, "checks": ["six navigation entries", "QML preparation/work/pause/review/tools", "compact layout",
    "real island pause", "exact-second restart", "cumulative elapsed", "actual-duration statistics", "explicit task completion", "persistent thoughts", "task flow defaults to island only", "unchanged task order and break types", "task flow immersion opt-in", "cancelled flow plants no tree"],
    "renders": str(output), "warnings": warnings}, ensure_ascii=False, indent=2))
DATA.cleanup()
