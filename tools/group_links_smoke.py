"""Click the step link buttons using temporary data, including new flows."""
import faulthandler
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'vendor')]
os.chdir(ROOT)
DATA = tempfile.TemporaryDirectory(prefix='flowtodo-group-links-')
os.environ['FLOWTODO_DATA_DIR'] = DATA.name
os.environ['FLOWTODO_RINUI_CONFIG_DIR'] = str(Path(DATA.name) / 'rinui')
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
os.environ['QT_QUICK_BACKEND'] = 'software'
os.environ['QT_QUICK_CONTROLS_STYLE'] = 'Basic'
faulthandler.dump_traceback_later(40, exit=True)

from PySide6.QtCore import QPointF, Qt, QUrl
from PySide6.QtQml import QQmlEngine, QQmlExpression
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase
from RinUI import RinUIWindow
from compat_backend import RinUIBackend
from i18n_runtime import translator

app = QApplication([])
for font in ('msyh.ttc', 'segoeui.ttf', 'seguisb.ttf'):
    QFontDatabase.addApplicationFont(str(Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts' / font))
backend = RinUIBackend()
backend.groups_database = [dict(id=201, name='晨间学习', steps=[dict(name='阅读资料', duration=25, relationId='read', extra='retain'), dict(name='写下观点', duration=15, relationId='write')])]
window = RinUIWindow(shared_engine=False)
window.engine.rootContext().setContextProperty('Backend', backend)
window.engine.rootContext().setContextProperty('I18nBridge', translator())
warnings, requests = [], []
window.engine.warnings.connect(lambda errors: warnings.extend(e.toString() for e in errors))
backend.taskRelationsRequested.connect(requests.append)
window.load(ROOT / 'qml/Main.qml')
root = window.root_window
assert root is not None, warnings
backend.attach_native_window(root)
root.setWidth(1500); root.setHeight(1000)
QTest.qWait(350)

def find(item, name):
    if item.objectName() == name: return item
    for child in item.childItems():
        found = find(child, name)
        if found is not None: return found

def qml(item, code):
    expr = QQmlExpression(QQmlEngine.contextForObject(item), item, code)
    value = expr.evaluate()
    assert not expr.hasError(), expr.error().toString()
    return value[0] if isinstance(value, tuple) else value

def open_editor(group_id):
    url = QUrl.fromLocalFile(str(ROOT / 'qml/pages/GroupEditorPage.qml')).toString()
    qml(root, "navigationView.safePush('" + url + "', true, false, {groupId: " + str(group_id) + "})")
    QTest.qWait(450)
    page = find(root.contentItem(), 'GroupEditorPage')
    assert page is not None, warnings
    return page

def click_link(page, index):
    root.grabWindow(); QTest.qWait(100)
    button = find(page, 'groupStepRelation_' + str(index))
    assert button is not None
    point = button.mapToScene(QPointF(button.width()/2, button.height()/2)).toPoint()
    QTest.mouseMove(root, point); QTest.qWait(80)
    QTest.mouseClick(root, Qt.LeftButton, Qt.NoModifier, point)
    QTest.qWait(300)

page = open_editor(201)
assert root.grabWindow().save(str(ROOT / 'work/group-link-before.png'))
click_link(page, 1)
assert requests[-1] == 'step:201:write', (requests, warnings)
assert find(root.contentItem(), 'TaskRelationsPage') is not None
assert backend.groups_database[0]['steps'][0]['extra'] == 'retain'
print('Existing flow: real step link opens graph.', flush=True)
page = open_editor(-1)
qml(page, 'stepsModel.setProperty(0, "title", "整理研究材料")')
before = len(requests)
click_link(page, 0)
assert len(requests) == before + 1
key = requests[-1]
graph = find(root.contentItem(), 'TaskRelationsPage')
assert graph is not None
assert json.loads(qml(graph, 'JSON.stringify(page.selectedNode)'))['title'] == '整理研究材料'
flow_id = int(key.split(':')[1])
saved = next(g for g in backend.groups_database if g['id'] == flow_id)
assert saved['name'] == '未命名任务流'
assert saved['steps'][0]['relationId'] == key.split(':')[2]
persisted = json.loads(Path(backend.groups_file).read_text('utf-8'))
assert next(g for g in persisted if g['id'] == flow_id) == saved
print('New flow: save then open graph focused on the clicked step.', flush=True)
page = open_editor(201)
qml(page, 'stepsModel.setProperty(0, "title", "")')
before = len(requests)
snapshot = json.dumps(backend.groups_database, sort_keys=True)
click_link(page, 0)
assert len(requests) == before
assert find(page, 'groupEditorError').isVisible()
assert json.dumps(backend.groups_database, sort_keys=True) == snapshot
print('Empty clicked step: feedback without changing saved data.', flush=True)
page = open_editor(-1)
qml(page, 'stepsModel.setProperty(0, "title", "阅读资料")')
assert not qml(page, 'page.save(false, "")')
assert qml(page, 'nameField.activeFocus')
assert find(page, 'groupEditorError').isVisible()
page = open_editor(201)
field = find(page, 'groupStepTitle_0')
field.forceActiveFocus()
QTest.keyClick(root, Qt.Key_A, Qt.ControlModifier)
for letter in 'draft': QTest.keyClick(root, ord(letter.upper()))
QTest.qWait(80)
click_link(page, 0)
assert requests[-1] == 'step:201:read'
graph = find(root.contentItem(), 'TaskRelationsPage')
actual_title = json.loads(qml(graph, 'JSON.stringify(page.selectedNode)'))['title']
assert actual_title == 'DRAFT', actual_title
assert backend.groups_database[0]['steps'][0]['extra'] == 'retain'
assert len(backend.groups_database) == 2
print('Native typing: edited title retained and the same step selected.', flush=True)
page = open_editor(201)
qml(page, 'stepsModel.move(1, 0, 1)')
click_link(page, 0)
assert requests[-1] == 'step:201:write'
assert backend.groups_database[0]['steps'][0]['relationId'] == 'write'
assert backend.groups_database[0]['steps'][1]['extra'] == 'retain'
print('Reordered steps: link follows the clicked step and metadata stays intact.', flush=True)
assert not warnings, warnings
backend.shutdown()
root.hide(); app.processEvents(); DATA.cleanup()
print('PASS: step link checks; no QML errors.', flush=True)
os._exit(0)
