"""Click-test account routes and render native QML with temporary data."""
from pathlib import Path
source = Path(__file__).with_name("focus_preview.py").read_text(encoding="utf-8").split("QTest.qWait(500)")[0]
source = source.replace('os.environ["LOCALAPPDATA"] = DATA.name', 'os.environ["LOCALAPPDATA"] = DATA.name\nos.environ["FLOWTODO_DATA_DIR"] = str(Path(DATA.name) / "data")\nos.environ["FLOWTODO_RINUI_CONFIG_DIR"] = str(Path(DATA.name) / "RinUI/config")')
exec(compile(source, str(Path(__file__).with_name("focus_preview.py")), "exec"))

def visible_control(name, item=None):
    item = item or root.contentItem()
    if item.objectName() == name and item.isVisible():
        return item
    for child in item.childItems():
        found = visible_control(name, child)
        if found is not None:
            return found
    return None

def click(name):
    item = visible_control(name)
    assert item is not None, name
    QTest.mouseClick(root, Qt.LeftButton, Qt.NoModifier, item.mapToScene(item.boundingRect().center()).toPoint())
    QTest.qWait(1000)

def route():
    nav = root.findChild(QObject, "MainNavigationView")
    return str(nav.property("currentPage"))

QTest.qWait(500)
backend.renameAccount("林同学")
backend._record_ai_usage({"total_tokens": 1000}, "default")
for width in (1180, 900):
    root.setWidth(width)
    root.setHeight(760)
    for collapsed in (True, False):
        open_page("HomeDashboard.qml")
        QTest.qWait(600)
        evaluate("navigationView.navigationBar.collapsed = " + ("true" if collapsed else "false"))
        QTest.qWait(200)
        if not collapsed:
            render("home-page-" + str(width), width, 760)
        click("accountMenuButton")
        flyout = root.findChild(QObject, "accountFlyout")
        assert flyout.property("opened")
        assert 200 <= flyout.property("height") <= 310
        assert flyout.property("y") + flyout.property("height") <= root.height() - 60
        if width == 1180 and not collapsed:
            render("account-menu-1180", width, 760)
        if width == 900 and collapsed:
            render("account-menu-collapsed", width, 760)
        click("accountProfileButton")
        assert route().endswith("UserAccount.qml"), route()
        assert not flyout.property("visible")
        if not collapsed:
            render("account-page-" + str(width), width, 760)
        open_page("HomeDashboard.qml")
        QTest.qWait(700)
        click("accountMenuButton")
        click("accountPageMenuItem")
        assert route().endswith("UserAccount.qml"), route()

root.setWidth(1180)
evaluate("navigationView.navigationBar.collapsed = false")
QTest.qWait(500)
click("accountManageServiceButton")
assert route().endswith("AiSettings.qml"), route()
click("accountMenuButton")
click("accountSettingsMenuItem")
assert route().endswith("SettingsHub.qml"), route()
click("accountMenuButton")
click("accountServiceMenuItem")
assert route().endswith("AiSettings.qml"), route()
click("accountMenuButton")
click("accountProfileButton")
click("accountEditButton")
dialog = root.findChild(QObject, "accountEditDialog")
assert dialog.property("visible")
render("account-edit-dialog", 1180, 760)
field = visible_control("accountNickname")
field.setProperty("text", "测试昵称")
click("accountSaveButton")
assert json.loads(backend.accountJson)["name"] == "测试昵称"
assert not dialog.property("visible")
click("accountEditButton")
visible_control("accountNickname").setProperty("text", "不保存")
click("accountCancelButton")
assert json.loads(backend.accountJson)["name"] == "测试昵称"
from PySide6.QtGui import QImage, QColor, QPainter
from unittest.mock import patch
import hashlib
from account_state import AccountState
original_path = Path(DATA.name) / "avatar-original.png"
image = QImage(512, 256, QImage.Format_RGB32)
image.fill(QColor("#e7b88f"))
painter = QPainter(image)
painter.fillRect(256, 0, 256, 256, QColor("#315d9b"))
painter.end()
assert image.save(str(original_path))
original_hash = hashlib.sha256(original_path.read_bytes()).hexdigest()
with patch("compat_backend.QFileDialog.getOpenFileName", return_value=(str(original_path), "PNG")):
    click("accountAvatarButton")
crop = root.findChild(QObject, "avatarCropDialog")
assert crop.property("visible")
crop.setProperty("panX", 1.0)
render("avatar-crop-dialog", 1180, 760)
click("avatarCropSave")
assert not crop.property("visible")
avatar_path = backend._account_state.path.parent / "avatar.png"
avatar = QImage(str(avatar_path))
assert avatar.size().width() == 256
assert avatar.pixelColor(128, 128).blue() > avatar.pixelColor(128, 128).red()
assert avatar.pixelColor(0, 0).alpha() == 0
assert hashlib.sha256(original_path.read_bytes()).hexdigest() == original_hash
revision = json.loads(backend.accountJson)["avatarRevision"]
assert AccountState(backend._account_state.path).snapshot()["avatarRevision"] == revision
assert not backend.loadAccountAvatar(str(Path(DATA.name) / "missing.png"))
with patch("compat_backend.QFileDialog.getOpenFileName", return_value=(str(original_path), "PNG")):
    click("accountAvatarButton")
click("avatarCropCancel")
assert json.loads(backend.accountJson)["avatarRevision"] == revision
click("accountEditButton")
visible_control("accountNickname").setProperty("text", "尚未保存的昵称")
with patch("compat_backend.QFileDialog.getOpenFileName", return_value=("", "")):
    click("accountImportAvatar")
assert dialog.property("visible")
assert visible_control("accountNickname").property("text") == "尚未保存的昵称"
with patch("compat_backend.QFileDialog.getOpenFileName", return_value=(str(original_path), "PNG")):
    click("accountImportAvatar")
assert crop.property("visible")
click("avatarCropCancel")
assert dialog.property("visible")
assert visible_control("accountNickname").property("text") == "尚未保存的昵称"
click("accountCancelButton")
render("account-with-avatar", 1180, 760)
backend.setSetting("theme", "dark")
render("account-dark", 1180, 760)
click("accountMenuButton")
render("account-menu-dark", 1180, 760)
QTest.keyClick(root, Qt.Key_Escape)
QTest.qWait(600)
open_page("HomeDashboard.qml")
QTest.qWait(500)
render("home-dark", 1180, 760)
backend.setSetting("theme", "light")
QTest.qWait(200)
entry = visible_control("homeNewTask")
entry.setProperty("text", "验证新版首页添加")
click("homeAddButton")
new_task = next(t for t in backend.local_database if t["title"] == "验证新版首页添加")
click("homeToggle_" + str(new_task["id"]))
assert next(t for t in backend.local_database if t["id"] == new_task["id"])["done"]
click("accountMenuButton")
click("accountProfileButton")
backend.setSetting("aiServiceMode", "custom")
QTest.qWait(200)
assert json.loads(backend.accountJson)["usage"]["status"] == "provider"
render("account-custom-api", 1180, 760)
errors = [w for w in warnings if any(word in w for word in ("ReferenceError", "TypeError", "Cannot assign", "Binding loop", "Error:"))]
assert not errors, "\n".join(errors)
backend.shutdown()
root.hide()
app.processEvents()
print(json.dumps({"ok": True, "routes": "header, account, AI service, settings; collapsed and expanded; 900 and 1180", "warnings": warnings}, ensure_ascii=False), flush=True)
DATA.cleanup()
os._exit(0)
