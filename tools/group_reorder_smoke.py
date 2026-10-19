"""Exercise the step drag handles and persisted order with isolated app data."""
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, 'reconfigure'):
        stream.reconfigure(encoding='utf-8', errors='replace')
sys.path[:0] = [str(ROOT), str(ROOT / 'vendor')]
os.chdir(ROOT)
DATA = tempfile.TemporaryDirectory(prefix='flowtodo-reorder-')
os.environ['FLOWTODO_DATA_DIR'] = DATA.name
os.environ['FLOWTODO_RINUI_CONFIG_DIR'] = str(Path(DATA.name) / 'rinui')
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
os.environ['QT_QUICK_BACKEND'] = 'software'
os.environ['QT_QUICK_CONTROLS_STYLE'] = 'Basic'

from PySide6.QtCore import QPointF, Qt, QUrl
from PySide6.QtQml import QQmlEngine, QQmlExpression
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from RinUI import RinUIWindow
from compat_backend import RinUIBackend
from i18n_runtime import translator

app = QApplication([])
backend = RinUIBackend()
original = [dict(name=name, duration=duration, type=kind, relationId=name,
                 extra={'keep': name}) for name, duration, kind in
            [('A', 1, 'focus'), ('B', 25, 'focus'), ('C', 40, 'break'), ('D', 25, 'focus')]]
backend.groups_database = [dict(id=201, name='Reorder', steps=original)]
window = RinUIWindow(shared_engine=False)
window.engine.rootContext().setContextProperty('Backend', backend)
window.engine.rootContext().setContextProperty('I18nBridge', translator())
warnings = []
window.engine.warnings.connect(lambda errors: warnings.extend(e.toString() for e in errors))
window.load(ROOT / 'qml/Main.qml')
root = window.root_window
assert root is not None, warnings
backend.attach_native_window(root)
root.showNormal()
root.setWidth(1500)
root.setHeight(1100)
assert QTest.qWaitForWindowExposed(root, 3000)
QTest.qWait(350)

def find(item, name):
    if item.objectName() == name:
        return item
    for child in item.childItems():
        result = find(child, name)
        if result is not None:
            return result

def qml(item, code):
    expr = QQmlExpression(QQmlEngine.contextForObject(item), item, code)
    value = expr.evaluate()
    assert not expr.hasError(), expr.error().toString()
    return value[0] if isinstance(value, tuple) else value

url = QUrl.fromLocalFile(str(ROOT / 'qml/pages/GroupEditorPage.qml')).toString()
qml(root, "navigationView.push('" + url + "', {groupId: 201})")
QTest.qWait(500)
root.grabWindow()
QTest.qWait(100)
page = find(root.contentItem(), 'GroupEditorPage')
assert page is not None, warnings

def order():
    return json.loads(qml(page, 'JSON.stringify(Array.from({length: stepsModel.count}, function(_, i) { return stepsModel.get(i).title }))'))

def drag(start, end):
    root.grabWindow()
    QTest.qWait(100)
    handle = find(page, 'stepDragHandle_' + str(start))
    target = find(page, 'stepDragHandle_' + str(end))
    a = handle.mapToScene(QPointF(handle.width()/2, handle.height()/2)).toPoint()
    b = target.mapToScene(QPointF(target.width()/2, target.height()/2)).toPoint()
    b.setY(b.y() + (8 if end > start else -8))
    QTest.mousePress(root, Qt.LeftButton, Qt.NoModifier, a)
    QTest.qWait(50)
    assert qml(handle, 'stepDragArea.pressed'), 'Handle must receive the mouse press'
    for i in range(1, 13):
        QTest.mouseMove(root, a + (b-a)*i/12, 15)
    QTest.mouseRelease(root, Qt.LeftButton, Qt.NoModifier, b)
    QTest.qWait(100)
    assert page.property('draggedStepId') == ''

assert order() == ['A', 'B', 'C', 'D']
drag(0, 3)
assert order() == ['B', 'C', 'D', 'A'], order()
drag(3, 0)
assert order() == ['A', 'B', 'C', 'D'], order()
drag(1, 2)
assert order() == ['A', 'C', 'B', 'D'], order()
qml(page, 'page.save(false, "")')
QTest.qWait(250)
saved = json.loads(Path(backend.groups_file).read_text(encoding='utf-8'))
steps = next(group for group in saved if group['id'] == 201)['steps']
assert steps == [original[i] for i in (0, 2, 1, 3)], steps
qml(root, "navigationView.push('" + url + "', {groupId: 201})")
QTest.qWait(400)
page = find(root.contentItem(), 'GroupEditorPage')
assert order() == ['A', 'C', 'B', 'D']
errors = [w for w in warnings if any(s in w for s in ('ReferenceError', 'TypeError', 'Binding loop', 'Cannot assign'))]
assert not errors, errors
backend.shutdown()
root.hide()
app.processEvents()
DATA.cleanup()
print('PASS: drag down/up/adjacent; metadata retained; save and reopen order', flush=True)
os._exit(0)
