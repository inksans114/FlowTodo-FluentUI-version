"""Quick entry regression with temporary files and simulated AI; no mic/API."""
from pathlib import Path
source = Path(__file__).with_name("focus_preview.py").read_text(encoding="utf-8")
exec(compile(source.split("QTest.qWait(500)")[0], str(Path(__file__).with_name("focus_preview.py")), "exec"))
import copy
from uuid import uuid4
from unittest.mock import patch
from ai_library import remember
from ai_planning import AIOutputLimit

failed = True
try:
    backend.settings_database["aiApiKey"] = ""
    backend.settings_database["speechInputMode"] = "cloud"
    backend.settings_database["notificationSoundEnabled"] = False
    original_tasks = copy.deepcopy(backend.local_database)
    old_plan = {"libraryId": uuid4().hex, "captureMode": True, "captureOriginal": "原来的物理方案",
                "tasks": [{"title": "原来的任务"}], "summary": "旧方案保留", "questions": []}
    remember(backend.ai_state_database, old_plan)
    calls = []
    def forbidden(*args, **kwargs):
        calls.append(1)
        raise AssertionError("Default quick entry must not use AI")
    backend._call_ai_chat = forbidden
    QTest.qWait(500)
    open_page("QuickCapture.qml"); QTest.qWait(200)
    original = find_visual(root.contentItem(), "quickCaptureOriginal")
    assert original is not None, warnings
    page = original
    while page.metaObject().indexOfProperty("batchId") < 0:
        page = page.parentItem()
    def action(code):
        expression = QQmlExpression(window.engine.rootContext(), page, code)
        result = expression.evaluate()
        assert not expression.hasError(), expression.error().toString()
        return result
    original.setProperty("text", "买猫粮；交报告。给同学回消息")
    assert len(page.property("drafts").toVariant()) == 3
    assert find_visual(root.contentItem(), "quickCaptureSubmit").property("enabled")
    first = {"batchId": page.property("batchId"), "tasks": page.property("drafts").toVariant()}
    render("quick-capture-multiple", 1180, 920)
    action("submit()")
    assert len(backend.local_database) == len(original_tasks) + 3
    assert original.property("text") == ""
    assert backend.local_database[-len(original_tasks):] == original_tasks
    assert len({task["id"] for task in backend.local_database}) == len(backend.local_database)
    assert json.loads(backend.addQuickCapture(json.dumps(first)))["added"] == 0
    assert not backend.saveQuickCaptureDraft(json.dumps(dict(first, original="旧页面不得覆盖下一批")))
    original.setProperty("text", "买猫粮")
    action("submit()")
    assert sum(task["title"] == "买猫粮" for task in backend.local_database) == 2
    assert not calls
    assert json.loads(backend.getSelectedAiCapture())["plan"]["libraryId"] == old_plan["libraryId"]
    # Validate a whole batch before writing and leave both RAM and disk intact.
    before = copy.deepcopy(backend.local_database)
    invalid = {"batchId": uuid4().hex, "tasks": [{"title": "合法"}, {"title": ""}]}
    assert not json.loads(backend.addQuickCapture(json.dumps(invalid)))["ok"]
    with patch("ai_library.write_state", side_effect=OSError("simulated disk error")):
        assert not json.loads(backend.addQuickCapture(json.dumps({"batchId": uuid4().hex, "tasks": [{"title": "不应添加"}]})))["ok"]
    assert before == backend.local_database
    # Drafts survive leaving and rebuilding the page; edited titles/categories
    # survive independently of the old AI library selection.
    original.setProperty("text", "读一篇文献；洗衣服")
    action("editTask(0, {title:'读完指定文献', category:'学习'}); persist()")
    saved = json.loads(backend.getQuickCaptureDraft())
    assert saved["tasks"][0]["title"] == "读完指定文献"
    # Wait for navigation transitions to remove the preceding page before finding
    # an editor with the same objectName on the rebuilt page.
    open_page("HomeDashboard.qml"); QTest.qWait(500)
    open_page("QuickCapture.qml"); QTest.qWait(500)
    original = find_visual(root.contentItem(), "quickCaptureOriginal")
    page = original
    while page.metaObject().indexOfProperty("batchId") < 0: page = page.parentItem()
    assert page.property("drafts").toVariant()[0]["category"] == "学习"
    backend.settings_database["aiApiKey"] = "offline-fixture"
    backend.settingsChanged.emit()
    def response(messages, **options):
        calls.append((messages, options))
        return '{"tasks":[{"title":"读文献","category":"学习"},{"title":"洗衣服","category":"生活"}]}'
    backend._call_ai_chat = response
    action("organize()")
    for _ in range(30):
        QTest.qWait(30)
        if not page.property("waiting"): break
    assert not page.property("waiting") and not backend.aiRequestRunning
    assert len(calls) == 1 and calls[-1][1]["output_limit"] == 1600
    assert len(calls[-1][0]) == 2 and "原来的物理方案" not in str(calls[-1])
    assert backend.local_database == before  # AI preview doesn't import automatically.
    def truncated(*args, **kwargs):
        calls.append(1)
        raise AIOutputLimit("length", '{"tasks":[')
    backend._call_ai_chat = truncated
    action("organize()")
    for _ in range(30):
        QTest.qWait(30)
        if not page.property("waiting"): break
    assert len(calls) == 2 and original.property("text") == "读一篇文献；洗衣服"
    assert find_visual(root.contentItem(), "quickCaptureSubmit").property("enabled")
    action("submit()")
    assert len(backend.local_database) == len(before) + 2
    # A slow optional result must never restore already-submitted text or
    # replace a different new batch entered while it was being processed.
    import threading
    release = threading.Event()
    def slow(messages, **options):
        release.wait(2)
        return '{"tasks":[{"title":"旧输入的AI结果","category":"其他"}]}'
    backend._call_ai_chat = slow
    original.setProperty("text", "旧输入")
    action("organize()")
    original.setProperty("text", "现在要记的另一件事")
    action("submit()")
    release.set()
    for _ in range(30):
        QTest.qWait(30)
        if not backend.aiRequestRunning: break
    assert original.property("text") == "" and not page.property("drafts").toVariant()
    assert backend.local_database[0]["title"] == "现在要记的另一件事"
    render("quick-capture-ready", 900, 740)
    # An explicit new AI thought does not replace the previously saved plan.
    backend.newAiCapture()
    assert json.loads(backend.getSelectedAiCapture()) == {"pendingInput": ""}
    assert backend.openSavedAiPlan(old_plan["libraryId"])
    assert json.loads(backend.getSelectedAiCapture())["plan"]["captureOriginal"] == "原来的物理方案"
    open_page("AiWorkspace.qml"); QTest.qWait(150)
    ai_original = find_visual(root.contentItem(), "captureOriginal")
    assert ai_original is not None
    ai_page = ai_original
    while ai_page.metaObject().indexOfProperty("generatedOriginal") < 0: ai_page = ai_page.parentItem()
    expression = QQmlExpression(window.engine.rootContext(), ai_page, "newCapture()")
    expression.evaluate(); assert not expression.hasError(), expression.error().toString()
    ai_original.setProperty("text", "新的想法里有物理、英语两件事")
    QTest.qWait(400)
    assert json.loads(backend.getSelectedAiCapture())["pendingInput"] == "新的想法里有物理、英语两件事"
    assert json.loads(backend.getSavedAiPlan(old_plan["libraryId"]))["plan"]["captureOriginal"] == "原来的物理方案"
    assert not warnings, warnings
    print(json.dumps({"ok": True, "checks": ["multiple tasks without AI key", "append and clear for next batch", "unique IDs", "repeat click idempotency", "new same-title task", "no old-task modification", "atomic batch rejection", "persistent edited drafts", "optional AI is one small request", "AI failure preserves input and allows direct entry", "old AI plans preserved"], "warnings": warnings}), flush=True)
    failed = False
except Exception:
    import traceback
    traceback.print_exc(); sys.stderr.flush()
finally:
    backend.shutdown(); root.hide(); DATA.cleanup()
    os._exit(1 if failed else 0)
