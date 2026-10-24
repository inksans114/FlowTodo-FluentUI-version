"""Verify native About/Updates navigation and controls without network or installation."""
from pathlib import Path
from unittest.mock import Mock, patch

# Reuse the isolated application setup, before the language smoke starts its actions.
source = Path(__file__).with_name("i18n_smoke.py").read_text(encoding="utf-8")
exec(compile(source.split('    open_page("AppAppearanceSettings.qml")')[0], str(Path(__file__).with_name("i18n_smoke.py")), "exec"))


def find(name):
    matches = [item for item in descendants(root.contentItem()) if item.objectName() == name]
    assert matches, (name, texts(root.contentItem()), warnings)
    return matches[-1]


output = Path(DATA.name)
open_page("SettingsHub.qml")
assert "关于 FlowTodo" in texts(root.contentItem())
open_page("AboutPage.qml")
assert backend.appVersion in find("currentVersionLabel").property("text")
switch = find("automaticUpdateSwitch")
assert switch.property("checked") is True
evaluate(switch, "checked = false; clicked()")
assert not json.loads(backend.updateJson)["autoDownload"]
assert json.loads(Path(backend.settings_file).read_text(encoding="utf-8"))["updateAutoDownload"] is False

with patch.object(backend._update_manager, "check_for_updates") as check:
    evaluate(find("checkUpdatesButton"), "clicked()")
    check.assert_called_once_with(manual=True)
QTest.qWait(180)
root.grabWindow().save(str(output / "about.png"))

open_page("UpdatePage.qml")
assert find("automaticUpdateSwitch").property("checked") is False
evaluate(find("automaticUpdateSwitch"), "checked = true; clicked()")
assert json.loads(backend.updateJson)["autoDownload"]
backend._update_manager._receive({"status": "downloading", "progress": 47, "progressKnown": True, "receivedBytes": 50*1048576, "totalBytes": 100*1048576, "bytesPerSecond": 1048576, "remainingSeconds": 50, "availableVersion": "2.3.3", "busy": True})
backend._update_manager._busy = True; backend._update_manager.stateChanged.emit()
QTest.qWait(250)
assert find("updateDownloadProgress").property("value") == 47
assert not find("checkUpdatesButton").property("enabled")
assert "50.0 MB / 100.0 MB" in find("updateTransferDetails").property("text")
root.grabWindow().save(str(output / "update-downloading.png"))
backend._update_manager._receive({"progressKnown":False,"totalBytes":0})
QTest.qWait(50)
assert find("updateDownloadProgress").property("indeterminate")
assert "%" not in find("updateProgressPercent").property("text")
for state in ("verifying", "staging"):
    backend._update_manager._receive({"status":state,"progress":90})
    QTest.qWait(250)
    assert not find("updateDownloadProgress").property("indeterminate")
    assert find("updateDownloadProgress").isVisible()

with patch("updater.is_packaged_build", return_value=True), patch("updater.windows_package_family", return_value=""), patch("updater.sys.platform", "win32"):
    backend._update_manager._busy = False
    backend._update_manager._receive({"status": "ready", "ready": True, "progress": 100, "notes": "改进稳定性与界面翻译。", "message": "更新已下载，点击安装并重启后应用更新。"})
    QTest.qWait(80)
    assert find("installUpdateButton").isVisible()
    with patch.object(backend._update_manager, "install_update") as install:
        evaluate(find("installUpdateButton"), "clicked()")
        QTest.qWait(120)
        install.assert_not_called()
        dialog = root.findChild(QObject, "installUpdateDialog")
        assert dialog is not None and dialog.property("visible")
        evaluate(dialog, "close()")
        QTest.qWait(120)
    root.grabWindow().save(str(output / "update-ready.png"))

backend.setLanguage("zh_TW"); QTest.qWait(100)
assert "安裝並重新啟動" in texts(root.contentItem())
backend.setLanguage("en_US"); QTest.qWait(100)
assert "Install and restart" in texts(root.contentItem())

# Check the store layout at both navigation breakpoints and in dark mode.
for width in (1000, 900, 1180):
    root.setWidth(width); QTest.qWait(200)
    for name in ("storeProductHeader", "releaseMetadata", "automaticUpdateCard", "releaseNotesCard"):
        item = find(name)
        bounds = item.mapRectToScene(item.boundingRect())
        assert bounds.right() <= root.width() - 12, (width, name, bounds)
        assert item.width() > 100, (width, name, item.width())
        if name == "automaticUpdateCard":
            for text in descendants(item):
                if text.metaObject().indexOfProperty("lineCount") >= 0 and text.property("lineCount") > 1:
                    assert text.height() >= text.property("lineCount") * text.property("font").pixelSize(), (width, text.property("text"), text.height())
    root.grabWindow().save(str(output / ("store-update-" + str(width) + ".png")))
evaluate(root, "Theme.setTheme(Theme.mode.Dark)")
QTest.qWait(300)
root.grabWindow().save(str(output / "store-update-dark.png"))
evaluate(root, "Theme.setTheme(Theme.mode.Light)")
backend.setLanguage("zh_TW"); QTest.qWait(250)
root.grabWindow().save(str(output / "store-update-zh-TW.png"))
backend.setLanguage("zh_CN")
backend._update_manager._receive({"status":"idle", "ready":False, "availableVersion":"", "notes":"", "message":"启动和登录后检查更新。"})
open_page("AboutPage.qml"); QTest.qWait(180)
root.grabWindow().save(str(output / "store-about.png"))
errors = [warning for warning in warnings if any(word in warning for word in ("ReferenceError", "TypeError", "not a type", "Cannot assign", "Binding loop", "anchor"))]
assert not errors, "\n".join(errors)
print(json.dumps({"ok": True, "screenshots": str(output), "warnings": warnings}, ensure_ascii=False), flush=True)
DATA._finalizer.detach()
backend.shutdown(); root.hide(); app.processEvents()
os._exit(0)
