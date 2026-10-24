"""Exercise live language switching in real QML with disposable local data."""
import json
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "vendor"), str(ROOT)]
os.chdir(ROOT)
DATA = tempfile.TemporaryDirectory(prefix="flowtodo-i18n-")
os.environ["FLOWTODO_DATA_DIR"] = str(Path(DATA.name) / "data")
os.environ["FLOWTODO_RINUI_CONFIG_DIR"] = str(Path(DATA.name) / "rinui")
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["QT_QUICK_BACKEND"] = "software"
os.environ["QT_QUICK_CONTROLS_STYLE"] = "Basic"

from PySide6.QtCore import QObject, QUrl
from PySide6.QtGui import QFontDatabase
from PySide6.QtQml import QQmlComponent, QQmlEngine, QQmlExpression
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from RinUI import RinUIWindow
from compat_backend import RinUIBackend
from i18n_runtime import translator


def evaluate(item, code):
    expression = QQmlExpression(QQmlEngine.contextForObject(item), item, code)
    result = expression.evaluate()
    assert not expression.hasError(), expression.error().toString()
    return result[0] if isinstance(result, tuple) else result


def descendants(item):
    yield item
    for child in item.childItems():
        yield from descendants(child)


def texts(item):
    return [child.property("text") for child in descendants(item) if child.metaObject().indexOfProperty("text") >= 0]


app = QApplication([])
for font in ("msyh.ttc", "segoeui.ttf", "seguisb.ttf"):
    QFontDatabase.addApplicationFont(str(Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / font))
# Keep network jobs outside this UI-only verification.
with patch("cloud_controller.CloudController.refresh", lambda self: None):
    backend = RinUIBackend()
    backend.setLanguage("zh_CN")
    window = RinUIWindow(shared_engine=False)
    window.engine.rootContext().setContextProperty("Backend", backend)
    window.engine.rootContext().setContextProperty("I18nBridge", translator())
    warnings = []
    window.engine.warnings.connect(lambda errors: warnings.extend(error.toString() for error in errors))
    window.load(ROOT / "qml/Main.qml")
    root = window.root_window
    assert root is not None, warnings
    backend.attach_native_window(root)
    root.setWidth(1180); root.setHeight(850)
    QTest.qWait(150)

    # Navigate through the actual settings screen, then activate its selector.
    nav = root.findChild(QObject, "MainNavigationView")
    def open_page(name):
        evaluate(root, "navigationView.push(" + json.dumps(QUrl.fromLocalFile(str(ROOT / "qml/pages" / name)).toString()) + ")")
        QTest.qWait(500)

    open_page("AppAppearanceSettings.qml")
    selectors = [child for child in descendants(root.contentItem()) if child.objectName() == "languageBox"]
    assert selectors, (str(nav.property("currentPage")), warnings, texts(root.contentItem()))
    selector = selectors[-1]
    evaluate(selector, "currentIndex = 1; activated(1)")
    QTest.qWait(120)
    assert backend.language == "zh_TW"
    assert "介面語言" in texts(root.contentItem()), texts(root.contentItem())
    assert "本地訪客" in texts(root.contentItem())
    assert json.loads(Path(backend.settings_file).read_text(encoding="utf-8"))["language"] == "zh_TW"
    root.grabWindow().save(str(Path(DATA.name) / "appearance-zh-TW.png"))

    open_page("AiWorkspace.qml")
    values = texts(root.contentItem())
    for expected in ("想從哪件事開始？", "已儲存", "更多"):
        assert expected in values, (expected, values)
    original = next(child for child in descendants(root.contentItem()) if child.objectName() == "captureOriginal" and child.isVisible())
    assert original.property("placeholderText") == "寫下你的安排…"
    # Switching while the page is open updates bindings without touching input.
    original.setProperty("text", "用户原文：买猫粮、学习 Python")
    backend.setLanguage("zh_CN"); QTest.qWait(100)
    assert "想从哪件事开始？" in texts(root.contentItem())
    backend.setLanguage("zh_TW"); QTest.qWait(100)
    assert original.property("text") == "用户原文：买猫粮、学习 Python"
    assert "想從哪件事開始？" in texts(root.contentItem())
    root.grabWindow().save(str(Path(DATA.name) / "assistant-zh-TW.png"))

    # Instantiate every changed page/component to catch missing imports and syntax.
    for name in ("UserAccount", "CloudStorage", "CustomAppearance", "SupervisionWorkspace", "QuickCapture", "AppSettings", "SettingsPage", "AiSettings", "AiSavedPlans"):
        component = QQmlComponent(window.engine, QUrl.fromLocalFile(str(ROOT / "qml/pages" / (name + ".qml"))))
        instance = component.create(window.engine.rootContext())
        assert instance is not None, (name, [error.toString() for error in component.errors()])
        instance.setParent(root)
        if name == "AppSettings":
            assert not any(item.objectName() == "languageBox" for item in descendants(instance))
        if name == "QuickCapture":
            evaluate(instance, 'page.drafts = [{title:"用户任务", category:"学习"}]; page.restoring = false')
            QTest.qWait(50)
            category = next(item for item in descendants(instance) if item.objectName() == "quickCaptureCategory_0")
            assert category.property("currentText") == "學習"
            evaluate(category, "currentIndex = 2; activated(2)")
            assert evaluate(instance, "page.drafts[0].category") == "工作"
        instance.deleteLater()
        app.processEvents()

    # Verify exactly the English settings labels that previously mixed languages.
    backend.setLanguage("en_US")
    open_page("SettingsHub.qml")
    values = texts(root.contentItem())
    for expected in ("AI assistant", "Tools", "Settings", "AI service & preferences", "Language, appearance, window effects and accent color"):
        assert expected in values, (expected, values)
    root.grabWindow().save(str(Path(DATA.name) / "settings-en-US.png"))

    # Exercise the real capture pipeline with a simulated provider, not a paid call.
    backend.settings_database["aiServiceMode"] = "official"
    backend.settings_database["updateAutoDownload"] = False
    backend._cloud.cache = {"user":{"id":"i18n-test-user", "name":"Test user", "email":"test@example.invalid", "plan":"free", "balance":0}}
    results = []
    backend.signalAiPlanReady.connect(lambda payload: results.append(json.loads(payload)))
    for language, plan in (
        ("en_US", {"title":"Submit the report", "summary":"Let's start with the outline.",
            "tasks":[{"title":"Submit the report", "meta":"Keep the original deadline."}],
            "guidance":{"goal":"Submit the report", "intro":"Start with one point for the outline.", "style":"whole", "steps":[{"title":"Outline the first point", "detail":"Write one sentence for the opening point.", "minutes":8, "type":"focus"}]}}),
        ("zh_TW", {"title":"提交報告", "summary":"先從大綱開始。",
            "tasks":[{"title":"提交報告", "meta":"保留原定期限。"}],
            "guidance":{"goal":"提交報告", "intro":"先整理大綱的第一個重點。", "style":"whole", "steps":[{"title":"整理第一個重點", "detail":"寫下一句話。", "minutes":8, "type":"focus"}]}})
    ):
        backend.setLanguage(language)
        response = {"choices":[{"message":{"content":json.dumps(plan, ensure_ascii=False)}}]}
        original = "下周二交报告，先列大纲。"
        request = {"captureMode":True, "captureOriginal":original, "messages":[{"role":"user", "content":original}]}
        with patch.object(backend._cloud, "logged_in", return_value=True), patch.object(backend._cloud.client, "ai_chat", return_value=response) as provider:
            backend._run_ai_plan_request(json.dumps(request, ensure_ascii=False))
        provider.assert_called_once()
        from ai_output_language import output_language
        assert output_language(provider.call_args.args[0]) == language
        assert results[-1]["ok"], results[-1]
        generated = results[-1]["plan"]
        assert generated["captureOriginal"] == original
        assert generated["guidance"]["steps"][0]["type"] == "focus"
        assert generated["guidance"]["intro"] == plan["guidance"]["intro"]
        assert generated["guidance"]["steps"][0]["encouragement"] == ("You made progress in this step." if language == "en_US" else "這一小段確實推進了。")
        backend.ai_state_database.update(captureFresh=False, captureDraftInput="", selectedAiPlanId=generated["libraryId"])
        open_page("AiWorkspace.qml")
        assert plan["guidance"]["intro"] in texts(root.contentItem())
        root.grabWindow().save(str(Path(DATA.name) / ("ai-generated-" + language + ".png")))

    errors = [warning for warning in warnings if any(word in warning for word in ("ReferenceError", "TypeError", "not a type", "Binding loop", "Cannot assign", "Error:"))]
    assert not errors, "\n".join(errors)
    print(json.dumps({"ok": True, "screenshots": DATA.name, "warnings": warnings}, ensure_ascii=False), flush=True)
    # Keep preview PNGs until they have been inspected; all app data remains temporary.
    DATA._finalizer.detach()
    backend.shutdown()
    root.hide()
    app.processEvents()
os._exit(0)
