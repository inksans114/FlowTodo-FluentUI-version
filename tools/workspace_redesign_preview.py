"""Offline native UI and request allowance regression; all data is temporary."""
from pathlib import Path

source = Path(__file__).with_name("focus_preview.py").read_text(encoding="utf-8").split("QTest.qWait(500)")[0]
source = source.replace('os.environ["LOCALAPPDATA"] = DATA.name', 'os.environ["LOCALAPPDATA"] = DATA.name\nos.environ["FLOWTODO_DATA_DIR"] = str(Path(DATA.name) / "data")\nos.environ["FLOWTODO_RINUI_CONFIG_DIR"] = str(Path(DATA.name) / "RinUI/config")')
exec(compile(source, str(Path(__file__).with_name("focus_preview.py")), "exec"))
import io
import urllib.error
from unittest.mock import patch
from account_state import AccountState

_open_page = open_page
def open_page(name):
    _open_page(name)
    QTest.qWait(750)  # Wait for StackView transition before hit-testing controls.

def visible(name, item=None):
    item = item or root.contentItem()
    if item.objectName() == name and item.isVisible():
        return item
    for child in item.childItems():
        result = visible(name, child)
        if result is not None:
            return result
    return None

def click(name):
    QTest.qWait(80)
    item = visible(name)
    assert item is not None, name
    QTest.mouseClick(root, Qt.LeftButton, Qt.NoModifier, item.mapToScene(item.boundingRect().center()).toPoint())
    QTest.qWait(180)

def usage():
    return json.loads(backend.accountJson)["usage"]

def focus_page():
    item = visible("quickStartFocus") or visible("focusWorkCard")
    while item is not None and item.metaObject().indexOfProperty("stage") < 0:
        item = item.parentItem()
    assert item is not None
    return item

QTest.qWait(400)
backend.settings_database["aiApiKey"] = "MOCK_ONLY"
backend.settingsChanged.emit()
backend.settings_database["notificationSoundEnabled"] = False
backend.local_database += [
    {"id": 102, "title": "整理本周的项目进展", "done": False, "meta": "项目 · 本周"},
    {"id": 103, "title": "读书 20 分钟", "done": False, "taskType": "daily", "reminderTime": "18:00"},
]
backend.tasksChanged.emit()
for width, height in ((1180, 760), (900, 620)):
    root.setWidth(width); root.setHeight(height)
    evaluate("navigationView.navigationBar.collapsed = false")
    for page_name, shot in (("HomeDashboard.qml", "home-refined"), ("AiWorkspace.qml", "ai-refined"), ("FocusWorkspace.qml", "focus-refined")):
        open_page(page_name)
        QTest.qWait(250)
        render(shot + "-" + str(width), width, height)
    assert visible("focusTaskShortcut")
    assert visible("quickStartFocus")
    click("focusTaskShortcut")
    picker = visible("focusTaskPicker")
    assert picker is not None
    render("focus-task-picker-" + str(width), width, height)
    # Test an actual native ComboBox activation and selected task propagation.
    expression = QQmlExpression(window.engine.rootContext(), picker, "activated(1)")
    expression.evaluate()
    assert not expression.hasError()
    page = focus_page()
    assert page.property("selectedTaskId") == 101
    click("focusDuration_15")
    assert page.property("durationMinutes") == 15
    assert visible("focusDurationDisplay").property("text") == "15:00"

root.setWidth(1180); root.setHeight(760)
open_page("HomeDashboard.qml"); QTest.qWait(250)
visible("homeNewTask").setProperty("text", "新增一件重要的事")
click("homeAddButton")
task = next(t for t in backend.local_database if t["title"] == "新增一件重要的事")
click("homeToggle_" + str(task["id"]))
assert task["done"]
task_list = visible("homeTaskList")
assert task_list.mapToScene(task_list.boundingRect().topLeft()).y() < 430

open_page("FocusWorkspace.qml"); QTest.qWait(250)
click("focusMore")
assert focus_page().property("showAdvanced")
render("focus-refined-options", 1180, 1000)
click("focusMore")
root.setHeight(760)
visible("focusStepInput").setProperty("text", "写完文献综述的第一段")
click("quickStartFocus")
page = focus_page()
assert page.property("stage") == "work"
render("focus-refined-work", 1180, 760)
click("focusPause")
assert page.property("stage") == "paused"
render("focus-refined-paused", 1180, 760)
assert backend.resumeStepFocus("继续写第一段")
assert backend.endStepFocus()
QTest.qWait(200)
assert page.property("stage") == "review"
render("focus-refined-review", 1180, 760)
assert backend.saveStepReview("完成第一段", "检查引用", False)

for page_name, shot in (("HomeDashboard.qml", "home-refined-dark"), ("AiWorkspace.qml", "ai-refined-dark"), ("FocusWorkspace.qml", "focus-refined-dark")):
    backend.setSetting("theme", "dark")
    open_page(page_name); QTest.qWait(200)
    render(shot, 1180, 760)
backend.setSetting("theme", "light")
open_page("AiWorkspace.qml"); QTest.qWait(250)
visible("captureOriginal").setProperty("text", "明天写论文，先整理文献")
assert visible("capturePrepare").property("enabled")
click("inlineHelp")
assert root.findChild(QObject, "inlineHelpPopup").property("visible")
QTest.keyClick(root, Qt.Key_Escape)

# Exercise the real transport method without ever connecting to an API.
assert usage()["remaining"] == 5
with patch("urllib.request.urlopen", side_effect=TimeoutError):
    try:
        backend._call_ai_chat([])
        raise AssertionError("Timeout did not propagate")
    except RuntimeError as error:
        assert "超时" in str(error)
assert usage()["remaining"] == 5
for bad in ({"choices": []}, {"choices": [{"message": {"content": ""}}]},
            {"choices": [{"finish_reason": "content_filter", "message": {"content": "blocked"}}]}):
    with patch("urllib.request.urlopen", return_value=io.BytesIO(json.dumps(bad).encode())):
        try:
            backend._call_ai_chat([])
            raise AssertionError("Invalid reply was accepted")
        except RuntimeError:
            pass
assert usage()["remaining"] == 5
reply = {"choices": [{"finish_reason": "stop", "message": {"content": "收到"}}]}
for remaining in range(4, -1, -1):
    with patch("urllib.request.urlopen", return_value=io.BytesIO(json.dumps(reply).encode())):
        assert backend._call_ai_chat([]) == "收到"
    assert usage()["remaining"] == remaining
    if remaining == 4:
        open_page("UserAccount.qml"); QTest.qWait(200)
        render("account-free-counts", 1180, 760)
        click("accountMenuButton")
        render("account-menu-counts", 1180, 760)
        QTest.keyClick(root, Qt.Key_Escape)
with patch("urllib.request.urlopen") as network:
    try:
        backend._call_ai_chat([])
        raise AssertionError("Sixth Free request was accepted")
    except RuntimeError as error:
        assert "5 次" in str(error)
    network.assert_not_called()
assert AccountState(backend._account_state.path).snapshot()["usage"]["remaining"] == 0
open_page("AiWorkspace.qml"); QTest.qWait(200)
visible("captureOriginal").setProperty("text", "再试一次")
assert not visible("capturePrepare").property("enabled")
render("ai-free-exhausted", 1180, 760)
backend.setSetting("aiServiceMode", "custom")
backend.setSetting("aiApiKey", "MOCK_ONLY")
with patch("urllib.request.urlopen", return_value=io.BytesIO(json.dumps(reply).encode())):
    assert backend._call_ai_chat([]) == "收到"
assert usage()["status"] == "provider"
assert backend._account_state.snapshot()["usage"]["remaining"] == 0
assert visible("capturePrepare").property("enabled")
# Actual prepare/answer clicks, backed by simulated transport, preserve the flow.
click("aiMore")
click("aiNewIdea")
visible("captureOriginal").setProperty("text", "明天写论文，先整理文献")
plans = [
    {"tasks": [], "summary": "先确定眼前这一步。", "questions": [{"question": "想先做哪一步？", "choices": ["整理资料", "写第一段"]}]},
    {"tasks": [{"title": "整理论文资料"}], "guidance": {"goal": "写完文献综述", "intro": "先整理一个可引用的观点。", "style": "chunks", "steps": [{"title": "打开文献，标记一个观点", "detail": "从已读的材料里选一个观点。", "minutes": 5, "type": "focus"}]}},
]
def plan_reply(*args, **kwargs):
    plan = plans.pop(0)
    return io.BytesIO(json.dumps({"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(plan, ensure_ascii=False)}}]}).encode())

def wait_for_ai():
    for _ in range(100):
        QTest.qWait(100)
        if not backend.aiRequestRunning:
            return
    raise AssertionError("Simulated request did not finish")

before_tasks = len(backend.local_database)
with patch("urllib.request.urlopen", side_effect=plan_reply):
    click("capturePrepare")
    wait_for_ai()
    answer_field = visible("captureAnswer_0")
    assert answer_field is not None
    page = answer_field
    while page.metaObject().indexOfProperty("questions") < 0:
        page = page.parentItem()
    render("ai-refined-question", 1180, 760)
    expression = QQmlExpression(window.engine.rootContext(), page, "setAnswer(0, '整理资料')")
    expression.evaluate()
    assert not expression.hasError()
    click("captureAnswer")
    wait_for_ai()
assert not plans
assert visible("captureGuidedStart").property("enabled")
assert visible("captureOriginal") is None
assert len(backend.local_database) == before_tasks
render("ai-refined-ready", 1180, 760)
with patch.object(backend, "startGuidedCapture", return_value=True) as launch:
    click("captureGuidedStart")
    launch.assert_called_once_with(page.property("savedId"))
click("aiSavedPlans")
assert str(root.findChild(QObject, "MainNavigationView").property("currentPage")).endswith("AiSavedPlans.qml")
errors = [w for w in warnings if any(word in w for word in ("ReferenceError", "TypeError", "Cannot assign", "Binding loop", "Error:"))]
assert not errors, "\n".join(errors)
backend.shutdown()
root.hide(); app.processEvents()
result = {"ok": True, "checks": ["native layouts at two widths, light/dark", "home add/complete and task list above fold", "task linking and duration", "focus start/pause/resume/review", "AI help, new idea, prepare, answer, ready and saved", "five successful calls and sixth blocked", "failed replies free", "restart persistence", "custom API separate"], "warnings": warnings}
(output / "workspace-redesign-results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(result, ensure_ascii=False), flush=True)
DATA.cleanup()
os._exit(0)
