"""End-to-end relation graph checks using temporary data and offscreen QML."""
import os
import sys
import json
import tempfile
import copy
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'vendor')]
os.chdir(ROOT)
(ROOT / 'work').mkdir(exist_ok=True)
DATA = tempfile.TemporaryDirectory(prefix='flowtodo-relations-')
os.environ['FLOWTODO_DATA_DIR'] = DATA.name
os.environ['FLOWTODO_RINUI_CONFIG_DIR'] = str(Path(DATA.name) / 'rinui')
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
os.environ['QT_QUICK_BACKEND'] = 'software'
os.environ['QT_QUICK_CONTROLS_STYLE'] = 'Basic'
os.environ['QTWEBENGINE_CHROMIUM_FLAGS'] = '--disable-gpu --disable-gpu-compositing'
from PySide6.QtCore import QUrl, Qt, QPoint, QPointF
from PySide6.QtQml import QQmlExpression, QQmlComponent, QQmlEngine
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase
from RinUI import RinUIWindow
from compat_backend import RinUIBackend
from task_relations import TaskRelations
from i18n_runtime import translator

app = QApplication([])
for font in ('msyh.ttc', 'segoeui.ttf', 'seguisb.ttf'):
    QFontDatabase.addApplicationFont(str(Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts' / font))
backend = RinUIBackend()
backend.settings_database['focusWeatherMode'] = 'off'
backend._apply_focus_environment = lambda *_: None
backend._restore_focus_environment = lambda: None
backend._minimize_main_window = lambda: None
backend._show_main_window = lambda: None
backend.local_database = [
    {'id': 1001, 'title': '整理研究材料', 'meta': '找到三个论点', 'done': False, 'scheduledDate': backend._today_key()},
    {'id': 1002, 'title': '写报告第一段', 'done': False, 'scheduledDate': backend._today_key()},
    {'id': 1003, 'title': '每晚复习英语', 'taskType': 'daily', 'done': False, 'scheduledDate': backend._today_key()},
    {'id': 1004, 'title': '周末修改报告', 'done': False, 'scheduledDate': '2099-10-12'}]
backend.groups_database = [{'id': 201, 'name': '晨间学习', 'launchApps': [], 'steps': [{'name': '阅读资料', 'duration': 5}, {'name': '摘录重点', 'duration': 15}]}]
backend.projects_database = [{'id': 301, 'name': '课程研究报告', 'milestones': [{'title': '文献梳理', 'done': False}, {'title': '初稿完成', 'done': False}]}]
graph = json.loads(backend.taskRelationsJson)
assert len(graph['nodes']) == 10 and len(graph['collections']) == 5
step = next(n for n in graph['nodes'] if n['kind'] == 'step')['key']
milestone = next(n for n in graph['nodes'] if n['kind'] == 'milestone')['key']
assert backend.connectTaskRelation('task:1001', step, 'next')
assert backend.connectTaskRelation(step, 'task:1002', 'next')
assert not backend.connectTaskRelation('task:1002', 'task:1001', 'next'), 'Must reject cycles'
assert not backend.connectTaskRelation('task:1001', step, 'next'), 'Must reject duplicates'
assert not backend.connectTaskRelation('task:1001', 'task:1001', 'together')
assert backend.connectTaskRelation('task:1001', milestone, 'together')
assert backend.connectTaskRelation(milestone, 'task:1003', 'together')
assert len(json.loads(backend.getRelationChoices('task:1001'))['together']) == 2
assert backend.moveRelationNode('task:1001', 46, 78)
persisted = TaskRelations(Path(DATA.name) / 'task_relations.json')
assert len(persisted.data['edges']) == 4 and persisted.data['positions']['task:1001']['x'] == 46
before = copy.deepcopy(persisted.data)
with patch('task_relations.write_state', side_effect=OSError('disk full')):
    try: persisted.connect('task:1002', 'task:1003', 'next', graph['nodes'])
    except OSError: pass
    else: raise AssertionError('write error not exposed')
assert persisted.data == before, 'Failed persistence must retain memory'
first_id = backend.groups_database[0]['steps'][0]['relationId']
backend.groups_database[0]['steps'].reverse()
backend.groups_database[0]['steps'][1]['name'] = '阅读新的资料'
assert next(n for n in json.loads(backend.taskRelationsJson)['nodes'] if n['key'] == step)['title'] == '阅读新的资料'
assert backend.groups_database[0]['steps'][1]['relationId'] == first_id

window = RinUIWindow(shared_engine=False)
window.engine.rootContext().setContextProperty('Backend', backend)
window.engine.rootContext().setContextProperty('I18nBridge', translator())
warnings = []
window.engine.warnings.connect(lambda errors: warnings.extend(e.toString() for e in errors))
window.load(ROOT / 'qml/Main.qml')
root = window.root_window
assert root is not None, warnings
backend.attach_native_window(root)
QTest.qWait(350)

def find(item, name):
    if item.objectName() == name: return item
    for child in item.childItems():
        found = find(child, name)
        if found is not None: return found
    return None

def qml(item, code):
    expr = QQmlExpression(QQmlEngine.contextForObject(item), item, code)
    value = expr.evaluate()
    assert not expr.hasError(), expr.error().toString()
    return value

def open_page(name, props='{}'):
    qml(root, "navigationView.push('" + QUrl.fromLocalFile(str(ROOT / 'qml/pages' / name)).toString() + "'," + props + ')')
    QTest.qWait(400)

def render(name, width=1180, height=820):
    root.setWidth(width); root.setHeight(height); QTest.qWait(220)
    assert root.grabWindow().save(str(ROOT / 'work' / (name + '.png')))

render('task-edit-entry')
edit_button = find(root.contentItem(), 'editTask_1001')
assert edit_button is not None, 'Home exposes a visible edit task button'
point = edit_button.mapToScene(QPointF(edit_button.width()/2, edit_button.height()/2)).toPoint()
QTest.mouseClick(root, Qt.LeftButton, Qt.NoModifier, point)
QTest.qWait(350)
assert find(root.contentItem(), 'TaskEditorPage') is not None, 'Edit button opens the editor'
qml(root, 'navigationView.pop()')
QTest.qWait(350)

open_page('FocusWorkspace.qml')
focus_page = find(root.contentItem(), 'FocusWorkspace')
assert focus_page is not None
assert not focus_page.property('showAdvanced')
assert not find(root.contentItem(), 'focusRelationsMore').isVisible()
render('quiet-focus')
body = find(root.contentItem(), 'focusPreparationBody')
assert not backend._immersive_active and not backend.active_focus_session, 'Opening Focus shows preparation without starting a scene or timer'
assert abs(body.mapToScene(QPointF(body.width()/2, 0)).x() - focus_page.mapToScene(QPointF(focus_page.width()/2, 0)).x()) < 2
assert abs(body.mapToScene(QPointF(0, body.height()/2)).y() - focus_page.mapToScene(QPointF(0, focus_page.height()/2)).y()) < 48, 'Preparation is visually centered'
render('centered-focus-compact', 900, 620)
assert body.width() <= focus_page.width() - 64
backend.setSetting('theme', 'dark')
render('centered-focus-dark')
backend.setSetting('theme', 'light')
render('quiet-focus')
assert find(root.contentItem(), 'focusRelationsShortcut').isVisible()
assert find(root.contentItem(), 'openSupervision').isVisible()
input_item = find(root.contentItem(), 'focusStepInput')
input_item.forceActiveFocus()
assert input_item.property('placeholderText') == '', 'Clicking clears the focus hint without typing'
shortcut = find(root.contentItem(), 'focusTaskShortcut')
point = shortcut.mapToScene(QPointF(shortcut.width()/2, shortcut.height()/2)).toPoint()
QTest.mouseMove(root, point)
QTest.qWait(100)
QTest.mousePress(root, Qt.LeftButton, Qt.NoModifier, point)
QTest.qWait(60)
QTest.mouseRelease(root, Qt.LeftButton, Qt.NoModifier, point)
QTest.qWait(120)
render('quiet-focus-picker')
assert find(root.contentItem(), 'focusTaskPicker').isVisible(), 'Task selection is beside the input'
picker_item = find(root.contentItem(), 'focusTaskPicker')
assert picker_item.mapToScene(QPointF(0,0)).y() < find(root.contentItem(), 'quickStartFocus').mapToScene(QPointF(0,0)).y()
more = find(root.contentItem(), 'focusMore')
point = more.mapToScene(QPointF(more.width()/2, more.height()/2)).toPoint()
QTest.mouseClick(root, Qt.LeftButton, Qt.NoModifier, point)
QTest.qWait(150)
assert focus_page.property('showAdvanced')
assert find(root.contentItem(), 'focusRelationsMore').isVisible(), 'More also has task relations'
render('quiet-focus-more')
input_item.setProperty('text', '阅读资料，整理三个论点')
focus_page.setProperty('immersive', False)
start_button = find(root.contentItem(), 'quickStartFocus')
point = start_button.mapToScene(QPointF(start_button.width()/2, start_button.height()/2)).toPoint()
QTest.mouseMove(root, point); QTest.qWait(80)
QTest.mouseClick(root, Qt.LeftButton, Qt.NoModifier, point)
QTest.qWait(250)
assert focus_page.property('stage') == 'work', 'The restored start button starts a real focus session'
assert backend.pauseStepFocus('整理了第一个论点', '整理第二个论点')
QTest.qWait(100)
assert focus_page.property('stage') == 'paused'
assert backend.resumeStepFocus('整理第二个论点')
assert backend.endStepFocus()
QTest.qWait(100)
assert focus_page.property('stage') == 'review'
assert backend.saveStepReview('整理了三个论点', '', False)
QTest.qWait(100)
assert focus_page.property('stage') == 'prepare'
assert not backend.local_database[0]['done'], 'Focus review does not automatically complete the task'
open_page('AiWorkspace.qml')
render('quiet-ai')

for name in ('TaskEditorPage.qml', 'GroupEditorPage.qml', 'ProjectEditorNative.qml', 'GroupPrepWorkspace.qml', 'ProjectPrepNative.qml', 'RelationPrepPage.qml', 'TaskRelationsPage.qml'):
    component = QQmlComponent(window.engine, QUrl.fromLocalFile(str(ROOT / 'qml/pages' / name)))
    assert not component.isError(), [e.toString() for e in component.errors()]
    obj = component.create()
    assert obj is not None, [e.toString() for e in component.errors()]
    obj.deleteLater()
QTest.qWait(100)
backend.openTaskRelations('task:1001')
QTest.qWait(500)
page = find(root.contentItem(), 'TaskRelationsPage')
assert page is not None, warnings
canvas = find(root.contentItem(), 'taskGraphCanvas')
render('task-relations-light')
render('task-relations-compact', 900, 620)
assert not find(root.contentItem(), 'relationListConnect').isVisible()
help_button = find(root.contentItem(), 'inlineHelp')
point = help_button.mapToScene(QPointF(help_button.width()/2, help_button.height()/2)).toPoint()
QTest.mouseClick(root, Qt.LeftButton, Qt.NoModifier, point)
QTest.qWait(180)
render('quiet-relations-help')
QTest.keyClick(root, Qt.Key_Escape)
graph_more = find(root.contentItem(), 'relationGraphMore')
point = graph_more.mapToScene(QPointF(graph_more.width()/2,graph_more.height()/2)).toPoint()
QTest.mouseMove(root, point); QTest.qWait(100)
QTest.mouseClick(root, Qt.LeftButton, Qt.NoModifier, point)
QTest.qWait(150)
assert qml(page, 'graphMenu.visible')[0]
render('quiet-relations-menu')
list_action = find(root.contentItem(), 'relationListAction')
assert list_action is not None
point = list_action.mapToScene(QPointF(list_action.width()/2,list_action.height()/2)).toPoint()
QTest.mouseMove(root, point); QTest.qWait(50)
QTest.mouseClick(root, Qt.LeftButton, Qt.NoModifier, point)
QTest.qWait(80)
assert find(root.contentItem(), 'relationListConnect').isVisible()
qml(page, 'showListConnect = false')
group_handle = find(root.contentItem(), 'relationCollectionHandle_today')
before_graph = json.loads(backend.taskRelationsJson)
before_node = next(n for n in before_graph['nodes'] if n['key'] == 'task:1001')
before_collection = next(c for c in before_graph['collections'] if c['key'] == 'today')
point = group_handle.mapToScene(QPointF(80,25)).toPoint()
QTest.mouseMove(root, point); QTest.qWait(80)
QTest.mousePress(root, Qt.LeftButton, Qt.NoModifier, point)
QTest.mouseMove(root, point + QPoint(24,18), 60)
QTest.mouseRelease(root, Qt.LeftButton, Qt.NoModifier, point + QPoint(24,18))
QTest.qWait(100)
after_graph = json.loads(backend.taskRelationsJson)
after_node = next(n for n in after_graph['nodes'] if n['key'] == 'task:1001')
after_collection = next(c for c in after_graph['collections'] if c['key'] == 'today')
assert after_collection['x'] > before_collection['x'] and after_collection['y'] > before_collection['y']
assert abs((after_node['x']-before_node['x'])-(after_collection['x']-before_collection['x'])) < .01
assert TaskRelations(Path(DATA.name)/'task_relations.json').data['collectionPositions']['today']['x'] == after_collection['x']
render('quiet-relations-dragged')
root.setWidth(1180); root.setHeight(820); QTest.qWait(150)
before_y = backend.task_relations.data['positions']['task:1001']['y']
drag_node = find(root.contentItem(), 'relationNode_task:1001')
point = drag_node.mapToScene(QPointF(80, 25)).toPoint()
QTest.mousePress(root, Qt.LeftButton, Qt.NoModifier, point)
QTest.mouseMove(root, point + QPoint(0, 18), 50)
QTest.mouseRelease(root, Qt.LeftButton, Qt.NoModifier, point + QPoint(0, 18))
QTest.qWait(80)
assert backend.task_relations.data['positions']['task:1001']['y'] > before_y
# Exercise actual output-port drag at the default zoom.
a, b = find(root.contentItem(), 'relationNode_task:1002'), find(root.contentItem(), 'relationNode_task:1001')
qa = a.mapToScene(QPointF(a.width(), a.height()/2)).toPoint()
qb = b.mapToScene(QPointF(0, b.height()/2)).toPoint()
QTest.mousePress(root, Qt.LeftButton, Qt.NoModifier, qa)
QTest.mouseMove(root, qb, 80)
QTest.mouseRelease(root, Qt.LeftButton, Qt.NoModifier, qb)
QTest.qWait(100)
assert len(json.loads(backend.taskRelationsJson)['edges']) == 4, 'Cycle rejected through the real wire gesture'
# Add an independent cross-collection link through a drag.
a, b = find(root.contentItem(), 'relationNode_task:1002'), find(root.contentItem(), 'relationNode_task:1004')
qa = a.mapToScene(QPointF(a.width(), a.height()/2)).toPoint()
qb = b.mapToScene(QPointF(0, b.height()/2)).toPoint()
QTest.mousePress(root, Qt.LeftButton, Qt.NoModifier, qa)
QTest.mouseMove(root, qb, 80)
QTest.mouseRelease(root, Qt.LeftButton, Qt.NoModifier, qb)
QTest.qWait(150)
assert len(json.loads(backend.taskRelationsJson)['edges']) == 5, 'Wire drag must create a link'
edge = json.loads(backend.taskRelationsJson)['edges'][-1]
assert backend.disconnectTaskRelation(edge['id'])
backend.setSetting('theme', 'dark')
QTest.qWait(400)
render('task-relations-dark')
backend.setSetting('theme', 'light')
open_page('GroupEditorPage.qml', '{groupId:201}')
editor = find(root.contentItem(), 'GroupEditorPage')
keys_before = {s['relationId'] for s in backend.groups_database[0]['steps']}
qml(editor, "stepsModel.move(0,1,1); page.save(true, '')")
QTest.qWait(450)
assert keys_before == {s['relationId'] for s in backend.groups_database[0]['steps']}
assert len(json.loads(backend.taskRelationsJson)['edges']) == 4
open_page('ProjectEditorNative.qml', '{projectId:301}')
editor = find(root.contentItem(), 'ProjectEditorNative')
milestone_before = backend.projects_database[0]['milestones'][0]['relationId']
qml(editor, "page.save(true, '')")
QTest.qWait(450)
assert milestone_before == backend.projects_database[0]['milestones'][0]['relationId']
open_page('TaskEditorPage.qml', '{taskId:1001}')
assert find(root.contentItem(), 'TaskEditorPage') is not None
task_editor = find(root.contentItem(), 'TaskEditorPage')
assert not find(root.contentItem(), 'taskEditorRelations').isVisible()
render('quiet-task-editor')
qml(task_editor, 'showMore = true')
assert find(root.contentItem(), 'taskEditorRelations').isVisible()
render('quiet-task-editor-more')
duration_item = find(root.contentItem(), 'taskDurationField')
point = duration_item.mapToScene(QPointF(duration_item.width()-16,duration_item.height()/2)).toPoint()
QTest.mouseMove(root, point); QTest.qWait(80)
QTest.mouseClick(root, Qt.LeftButton, Qt.NoModifier, point)
assert duration_item.property('value') == 26
qml(task_editor, 'duration.contentItem.forceActiveFocus()')
QTest.keyClick(root, Qt.Key_A, Qt.ControlModifier)
QTest.keyClick(root, Qt.Key_1)
QTest.keyClick(root, Qt.Key_5)
QTest.keyClick(root, Qt.Key_Return)
QTest.qWait(50)
assert duration_item.property('value') == 15, 'Duration supports direct numeric editing'
backend.setSetting('theme', 'dark'); QTest.qWait(180)
render('quiet-task-editor-dark')
backend.setSetting('theme', 'light'); QTest.qWait(180)
render('quiet-task-editor-compact',900,620)
root.setWidth(1180); root.setHeight(820)
assert backend.updateTaskDetails(json.dumps({'id':1001, 'title':'整理材料 · 已修改','meta':'保留备注','focusMinutes':15}))
assert len(json.loads(backend.taskRelationsJson)['edges']) == 4
requests = []
backend.relationCompletionRequested.connect(lambda key, complete: requests.append((key, complete)))
backend.toggleTask(1001, True)
assert requests[-1] == ('task:1001', True)
assert not backend.local_database[0]['done'], 'Source completion awaits confirmation'
render('task-relations-completion')
render('task-relations-completion-compact', 900, 620)
from PySide6.QtCore import QObject
completion = root.findChild(QObject, 'relationCompletionDialog')
assert completion is not None
qml(completion, "choices = ({node:{title:'长任务列表布局检查'}, next:[], together:Array.from({length:30},function(_,i){return {title:'关联任务 '+(i+1)+'：阅读资料并记录下一步',collectionTitle:'课程研究报告'}})})")
qml(completion, 'showTogether = true')
render('task-relations-completion-long', 900, 620)
assert completion.property('height') <= root.height()-40, 'Long lists stay inside the window'
qml(completion, "present('task:1001', true)")
root.setWidth(1180); root.setHeight(820)
assert backend.confirmRelationCompletion('task:1001', True, True, '')
assert backend.local_database[0]['done'] and backend.local_database[2]['done']
assert backend.projects_database[0]['milestones'][0]['done']
assert backend.projects_database[0]['progress'] == 0.5
assert not backend.local_database[1]['done'], 'Sequential links never propagate completion'
assert backend.startRelationNode(step, 5, '读一小段', False)
QTest.qWait(200)
assert backend.focus_journey.active['source']['relationNodeKey'] == step
island = next(iter(backend.island_windows.values()))
island._deadline -= 20; island._tick(); backend._refresh_focus_snapshot()
assert backend.endStepFocus()
target_step = next(s for s in backend.groups_database[0]['steps'] if s['relationId'] == first_id)
assert not target_step.get('relationDone'), 'Timer does not complete the step'
assert backend.saveStepReview('读了资料', '', True)
target_step = next(s for s in backend.groups_database[0]['steps'] if s['relationId'] == first_id)
assert target_step['relationDone']
assert requests[-1] == (step, True)
preparations = []
backend.focusPreparationRequested.connect(lambda kind, item: preparations.append((kind, item)))
assert backend.confirmRelationCompletion(step, True, False, 'task:1002')
assert preparations[-1] == ('task', 1002.0)
assert backend.reopenRelationNode(step)
assert not next(s for s in backend.groups_database[0]['steps'] if s['relationId'] == first_id)['relationDone']
backend.deleteTask(1001)
assert not any(e['source']=='task:1001' or e['target']=='task:1001' for e in backend.task_relations.data['edges'])
edges_before_reset = copy.deepcopy(backend.task_relations.data['edges'])
assert backend.resetRelationLayout()
assert not backend.task_relations.data['collectionPositions'] and not backend.task_relations.data['positions']
assert backend.task_relations.data['edges'] == edges_before_reset
errors = [w for w in warnings if any(t in w for t in ('TypeError', 'ReferenceError', 'Cannot assign', 'Binding loop', 'Error:'))]
assert not errors, errors
print(json.dumps({'ok':True, 'checks':['membership','stable IDs after rename/reorder','cycle/self/duplicate rejection','disk failure','persisted edges/layout','QML components','wire gestures','light/dark/compact renders','edit preservation','explicit together completion','timer does not mark done','step session identity','next task preparation','delete cleanup'], 'warnings':warnings}, ensure_ascii=False), flush=True)
backend.shutdown()
for win in app.topLevelWindows(): win.hide()
app.processEvents()
DATA.cleanup()
os._exit(0)
