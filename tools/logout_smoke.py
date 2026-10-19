"""Exercise both logout dialogs with temporary data and an offline account server."""
from pathlib import Path

source = Path(__file__).with_name('focus_preview.py').read_text(encoding='utf-8').split('QTest.qWait(500)')[0]
source = source.replace('os.environ["LOCALAPPDATA"] = DATA.name', 'os.environ["LOCALAPPDATA"] = DATA.name\nos.environ["FLOWTODO_DATA_DIR"] = str(Path(DATA.name) / "data")\nos.environ["FLOWTODO_RINUI_CONFIG_DIR"] = str(Path(DATA.name) / "RinUI/config")')
exec(compile(source, str(Path(__file__).with_name('focus_preview.py')), 'exec'))

import threading
import urllib.error
from unittest.mock import Mock
from PySide6.QtQml import QQmlEngine

cloud = backend._cloud
cloud.refresh_timer.stop()
cloud.client.opener = Mock()
cloud.client.opener.open.side_effect = urllib.error.URLError('offline test')
local_before = list(backend.local_database)

def seed():
    cloud.client.vault.save({'accessToken': 'fake-offline-session'})
    cloud.cache = {'user': {'id': '00000000-0000-0000-0000-000000000001',
                           'name': '测试账户', 'email': 'test@example.com', 'plan': 'lite', 'balance': 0}}
    cloud.changed()
    QTest.qWait(100)

def qml(item, code):
    expr = QQmlExpression(QQmlEngine.contextForObject(item), item, code)
    result = expr.evaluate()[0]
    assert not expr.hasError(), expr.error().toString()
    return result

def click(item):
    if isinstance(item, str):
        item = find_visual(root.contentItem(), item)
    assert item is not None
    root.grabWindow()
    point = item.mapToScene(item.boundingRect().center()).toPoint()
    QTest.mouseMove(root, point)
    QTest.qWait(50)
    QTest.mouseClick(root, Qt.LeftButton, Qt.NoModifier, point)
    QTest.qWait(800)

root.setWidth(1180)
root.setHeight(760)
root.show()
evaluate('navigationView.navigationBar.collapsed = false')
open_page('HomeDashboard.qml')
QTest.qWait(400)
try:
    for entry in ('menu', 'page'):
        seed()
        if entry == 'page':
            open_page('UserAccount.qml')
            QTest.qWait(400)
        dialog = root.findChild(QObject, 'accountMenuLogoutDialog' if entry == 'menu' else 'accountPageLogoutDialog')
        assert dialog is not None
        def show():
            if entry == 'menu':
                click('accountMenuButton')
                click('accountLogoutMenuItem')
            else:
                click('accountLogoutButton')
            assert dialog.property('opened')
        show()
        assert qml(dialog, 'footer.standardButton(1024).highlighted')
        if entry == 'menu':
            render('logout-rinui')
        click(qml(dialog, 'footer.standardButton(4194304)'))  # Cancel
        assert cloud.logged_in(), 'Cancel logged out the account'
        held = threading.Event()
        cloud.job(lambda: held.wait(10), lambda _: None)
        show()
        assert cloud.busy
        click(qml(dialog, 'footer.standardButton(1024)'))  # Ok
        assert not dialog.property('visible')
        assert not cloud.logged_in()
        assert json.loads(backend.accountJson)['name'] == '本地访客'
        assert not cloud.client.vault.path.exists()
        assert backend.local_database == local_before
        held.set()
        QTest.qWait(100)
    assert not [w for w in warnings if 'LogoutConfirmDialog.qml' in w], warnings
    print('PASS: RinUI dialogs, cancel, both logout entries during refresh, offline logout, local tasks preserved.', flush=True)
finally:
    if 'held' in globals():
        held.set()
    cloud.close()
backend.shutdown()
root.hide()
app.processEvents()
DATA.cleanup()
os._exit(0)
