"""Exercise canonical todo membership, QML dialogs and real island boundaries offline."""
from pathlib import Path
import time

bootstrap = Path(__file__).with_name('group_links_smoke.py').read_text(encoding='utf-8').split('def find(')[0]
exec(compile(bootstrap, str(Path(__file__).with_name('group_links_smoke.py')), 'exec'))
faulthandler.cancel_dump_traceback_later()
faulthandler.dump_traceback_later(90, exit=True)
backend._apply_focus_environment = lambda *_: None
backend._restore_focus_environment = lambda: None
backend._group_launch_apps = lambda *_: []
backend._show_main_window = lambda: None
backend._minimize_main_window = lambda: None
backend.settings_database['focusWeatherMode'] = 'off'
import island as island_module
island_module.play_notification_sound = lambda: None
island_module.send_windows_notification = lambda *_: None
backend.local_database = [dict(id=1, title='阅读英语', done=False, focusMinutes=1), dict(id=2, title='完成练习', done=False, focusMinutes=1), dict(id=3, title='检查答案', done=False, focusMinutes=1)]
backend.groups_database = []
backend.projects_database = []
backend.signalTasksUpdated.emit(backend._json(backend.local_database))
backend.signalGroupsUpdated.emit('[]')

def find(item, name):
    if item.objectName().lower() == name.lower(): return item
    for child in item.childItems():
        result = find(child, name)
        if result is not None: return result

def qml(item, code):
    expr = QQmlExpression(QQmlEngine.contextForObject(item), item, code)
    result = expr.evaluate()
    assert not expr.hasError(), expr.error().toString()
    return result[0] if isinstance(result, tuple) else result

def click(name):
    root.grabWindow(); QTest.qWait(100)
    item = find(root.contentItem(), name)
    assert item is not None and item.isVisible(), name
    point = item.mapToScene(QPointF(item.width()/2, item.height()/2)).toPoint()
    QTest.mouseMove(root, point); QTest.qWait(80)
    QTest.mouseClick(root, Qt.LeftButton, Qt.NoModifier, point)
    QTest.qWait(350)

def open_page(name, props='{}'):
    url = QUrl.fromLocalFile(str(ROOT / 'qml/pages' / name)).toString()
    qml(root, "navigationView.push('" + url + "', " + props + ')')
    QTest.qWait(450)

def expire(island):
    island._deadline = time.monotonic() - 1
    island._tick()
    QTest.qWait(120)

requests, invalid, preparations, old_preparations = [], [], [], []
messages = []
backend.messageRequested.connect(lambda *args: messages.append(args))
backend.relationCompletionRequested.connect(lambda key, done: requests.append((key, done)))
backend.flowInvalidRequested.connect(invalid.append)
backend.flowPreparationRequested.connect(preparations.append)
backend.focusPreparationRequested.connect(lambda *args: old_preparations.append(args))
open_page('GroupEditorPage.qml', '{groupId: -1}')
editor = find(root.contentItem(), 'groupEditorPage')
assert editor is not None
find(editor, 'groupNameField').setProperty('text', '英语作业')
click('addExistingTasks')
click('flowPickTask_1'); click('flowPickTask_2'); click('flowPickTasksConfirm')
assert qml(editor, 'stepsModel.count') == 2
assert qml(editor, 'page.save(false, "")')
group = backend.groups_database[0]
assert [s['taskId'] for s in group['steps']] == [1, 2]
gid = group['id']
graph = json.loads(backend.taskRelationsJson)
assert [n['key'] for n in graph['nodes']].count('task:1') == 1
assert next(n for n in graph['nodes'] if n['key'] == 'task:1')['collectionTitle'] == '英语作业'
assert len(graph['edges']) == 1 and graph['edges'][0]['readonly']
assert backend.connectTaskRelation('task:2', 'task:3', 'next')
assert not backend.connectTaskRelation('task:2', 'task:1', 'next')
assert invalid and qml(root, 'flowInvalid.visible')
qml(root, 'flowInvalid.close()')
bad_group = dict(group, steps=group['steps'] + [group['steps'][0]])
assert not backend.saveGroupJson(json.dumps(bad_group))
assert len(backend.groups_database[0]['steps']) == 2
qml(root, 'flowInvalid.close()')
backend.openTaskRelations('group:' + str(gid))
QTest.qWait(450)
page = find(root.contentItem(), 'taskRelationsPage')
assert page is not None
QTest.qWait(200)
assert root.grabWindow().save(str(ROOT / 'work/flow-logic-graph.png'))
backend.prepareFlowNode('group:' + str(gid)); QTest.qWait(150)
assert qml(root, 'flowPreparation.visible')
click('flowStartConfirm')
assert backend.active_focus_session and not backend._immersive_active
assert backend.active_focus_session['mode'] == 'group'
island = next(iter(backend.island_windows.values()))
assert [t['relationNodeKey'] for t in island.tasks] == ['task:1', 'task:2']
expire(island)
assert requests[-1] == ('task:1', True)
assert island.flow_waiting and island.current_index == 0 and not island.focus_running()
assert not backend.local_database[0]['done'], 'Clock alone never completes the todo'
assert qml(root, 'relationCompletion.visible')
assert qml(root, 'relationCompletion.nextKey') == 'task:2'
assert root.grabWindow().save(str(ROOT / 'work/flow-logic-next.png'))
qml(root, 'relationCompletion.close()')
island.signalFollowupRequested.emit('flow'); QTest.qWait(80)
assert qml(root, 'relationCompletion.visible'), 'Floating window can reopen a dismissed prompt'
click('flowNextConfirm')
assert backend.local_database[0]['done'] and not backend.local_database[1]['done']
assert island.current_index == 1 and island.focus_running()
expire(island)
assert requests[-1] == ('task:2', True)
assert qml(root, 'relationCompletion.nextKey') == 'task:3'
click('flowNextConfirm')
assert backend.active_focus_session is None and backend.local_database[1]['done']
assert preparations[-1] == 'task:3' and not old_preparations, 'Next uses a dialog and keeps the flow page'
assert find(root.contentItem(), 'taskRelationsPage').isVisible()
assert qml(root, 'flowPreparation.visible')
assert backend.stats_database.get('totalFocusSeconds') == 120
assert next(n for n in json.loads(backend.taskRelationsJson)['nodes'] if n['kind'] == 'group')['done']
click('flowStartConfirm')
single = next(i for i in backend.island_windows.values() if not i._finished)
expire(single)
assert requests[-1] == ('task:3', True), 'Single graph node also prompts without immersion'
assert find(root.contentItem(), 'taskRelationsPage').isVisible()
click('flowNextConfirm')
assert backend.local_database[2]['done']
backend.reopenRelationNode('group:' + str(gid))
assert not backend.local_database[0]['done'] and not backend.local_database[1]['done']
# Explicit breaks remain in the timer queue, without an extra injected break.
group['steps'].insert(1, dict(name='休息', type='break', duration=1, relationId='rest'))
assert backend.saveGroupJson(json.dumps(group))
assert backend.startGroupById(gid, json.dumps({'includeBreaks': True, 'breakMinutes': 1}))
island = next(i for i in backend.island_windows.values() if not i._finished and not i._cancelled)
assert [t.get('type', 'focus') for t in island.tasks] == ['focus', 'break', 'focus']
expire(island); click('flowNextConfirm')
assert island.current_index == 1
expire(island); QTest.qWait(400)
assert island.current_index == 2 and island.focus_running()
expire(island)
qml(root, 'relationCompletion.nextKey = ""')
click('flowNextConfirm')
assert backend.active_focus_session is None
# A saved boundary can be resumed without running a zero-second timer or losing the prompt.
backend.reopenRelationNode('group:' + str(gid))
assert backend.startGroupById(gid)
island = next(i for i in backend.island_windows.values() if not i._finished and not i._cancelled)
expire(island)
qml(root, 'relationCompletion.close()')
assert backend.parkStepFocus('', '')
assert backend.resumeStepFocus('')
QTest.qWait(100)
assert backend._pending_flow_key == 'task:1' and qml(root, 'relationCompletion.visible')
click('flowNextConfirm')
island = next(i for i in backend.island_windows.values() if not i._finished and not i._cancelled)
assert island.focus_running()
if island._current_task().get('type') == 'break':
    expire(island); QTest.qWait(400)
expire(island)
qml(root, 'relationCompletion.nextKey = ""'); click('flowNextConfirm')
assert backend.active_focus_session is None
# Legacy invalid files are blocked at execution, rather than silently repaired.
backend.reopenRelationNode('group:' + str(gid))
backend.task_relations.data['edges'].append(dict(id='legacy-bad', source='task:2', target='task:1', type='next'))
assert not backend.startGroupById(gid)
assert backend.active_focus_session is None and qml(root, 'flowInvalid.visible')
qml(root, 'flowInvalid.close()')
backend.task_relations.disconnect('legacy-bad')
for edge in list(backend.task_relations.data['edges']): backend.task_relations.disconnect(edge['id'])
assert not backend.saveGroupJson(json.dumps(dict(id=777, name='重复引用', steps=[dict(taskId=1, name='阅读英语')])) )
qml(root, 'flowInvalid.close()')
QTest.qWait(350)
assert backend.saveGroupJson(json.dumps(dict(id=777, name='交作业', steps=[dict(name='提交', duration=1, relationId='submit')])))
assert backend.connectTaskRelation('group:' + str(gid), 'group:777', 'next')
assert backend.startGroupById(gid)
island = next(i for i in backend.island_windows.values() if not i._finished and not i._cancelled)
expire(island); click('flowNextConfirm')
if island._current_task().get('type') == 'break': expire(island); QTest.qWait(400)
expire(island)
assert qml(root, 'relationCompletion.nextKey') == 'group:777'
click('flowNextConfirm')
assert preparations[-1] == 'group:777' and qml(root, 'flowPreparation.visible')
click('flowStartConfirm')
island = next(i for i in backend.island_windows.values() if not i._finished and not i._cancelled)
closed = []
backend.immersiveFocusClosed.connect(lambda: closed.append(True))
backend._immersive_active = True
expire(island)
assert closed and not backend._immersive_active and qml(root, 'relationCompletion.visible'), 'The same boundary exits immersive mode and presents the prompt'
click('flowNextConfirm')
assert backend.active_focus_session is None
assert backend.groups_database[1]['steps'][0]['relationDone']
backend.deleteGroup(gid)
assert len(backend.local_database) == 3 and backend.local_database[0]['done'], 'Deleting a flow keeps its canonical todos'
assert backend.saveGroupJson(json.dumps(dict(id=888, name='调整顺序', steps=[dict(name='第一步', duration=1, relationId='a'), dict(name='第二步', duration=2, relationId='b')])))
stages = json.loads(backend.getGroupSteps(888))[::-1]
assert backend.startPreparedGroup(888, json.dumps(stages))
assert [s['relationId'] for s in backend.groups_database[-1]['steps']] == ['b', 'a'], 'Preparation order persists to the diagram'
backend.cancel_focus_session()
backend.reopenRelationNode('group:888')
assert backend.startGroupById(888)
island = next(i for i in backend.island_windows.values() if not i._finished and not i._cancelled)
key = island._current_task()['relationNodeKey']
backend.requestRelationCompletion(key)
QTest.qWait(120)
assert island.flow_waiting and qml(root, 'relationCompletion.nodeKey') == key
assert island.tasks[0]['time'] < 5, 'Early completion records elapsed time instead of planned minutes'
next_key = qml(root, 'relationCompletion.nextKey')
backend._complete_relation_nodes([next_key])
assert qml(root, 'relationCompletion.nextKey') == '', 'The visible prompt refreshes after a queued task is completed elsewhere'
click('flowNextConfirm')
assert backend.active_focus_session is None, 'Externally completed queued tasks are skipped'
backend.reopenRelationNode('group:888')
assert backend.startGroupById(888, json.dumps({'includeBreaks': True, 'breakMinutes': 1}))
island = next(i for i in backend.island_windows.values() if not i._finished and not i._cancelled)
backend.requestRelationCompletion(island._current_task()['relationNodeKey']); QTest.qWait(120)
following = qml(root, 'relationCompletion.nextKey')
click('flowNextConfirm')
assert island._current_task().get('type') == 'break'
backend._complete_relation_nodes([following])
expire(island); QTest.qWait(400)
assert backend.active_focus_session is None, 'A todo completed during the break never starts another timer'
assert not warnings, warnings
print(json.dumps({'status': 'passed', 'checks': ['native multi-select', 'canonical todo identity', 'group completion synced to home', 'implicit ordering', 'invalid graph modal', 'no page switch', 'floating timer boundaries', 'external next', 'whole flow chaining', 'explicit breaks', 'boundary recovery', 'early completion', 'queued completion sync', 'legacy validation'], 'warnings': warnings}, ensure_ascii=False), flush=True)
backend.shutdown()
for island in list(backend.island_windows.values()): island.close()
root.hide(); app.processEvents(); DATA.cleanup()
faulthandler.cancel_dump_traceback_later()
os._exit(0)
