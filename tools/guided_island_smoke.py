"""Real floating-island follow-up clicks, with isolated data and no API calls."""
from pathlib import Path
import time

bootstrap = Path(__file__).with_name('group_links_smoke.py').read_text(encoding='utf-8').split('def find(')[0]
exec(compile(bootstrap, str(Path(__file__).with_name('group_links_smoke.py')), 'exec'))
from guided_focus import island_tasks, validate_guidance
from unittest.mock import patch
backend._apply_focus_environment = lambda *_: None
backend._restore_focus_environment = lambda: None
backend._show_main_window = lambda: None
backend._minimize_main_window = lambda: None
backend.settings_database['notificationSoundEnabled'] = False
backend.settings_database['focusWeatherMode'] = 'off'
backend.settings_database['focusMusicAutoPlay'] = False
guide = validate_guidance({'goal': '完成英语作业', 'style': 'chunks', 'intro': '先做眼前这一段。',
    'breakMinutes': 3, 'restAfterMinutes': 40, 'steps': [
    {'title': '阅读材料', 'detail': '先读眼前这一页', 'minutes': 2, 'type': 'focus'},
    {'title': '完成练习', 'detail': '写下答案', 'minutes': 7, 'type': 'focus'}]})
tasks = island_tasks(guide)
source = {'mode': 'single', 'kind': 'guided', 'title': guide['goal'], 'guidance': guide,
          'completedActions': [], 'totalSeconds': sum(t['time'] for t in tasks), 'totalTasks': len(tasks)}
assert backend._launch_island(tasks, 'single', source, backend._focus_options({'keepWindowOpen': True, 'guided': True}))
island = next(iter(backend.island_windows.values()))
QTest.qWait(700)
actions = []
island.signalFollowupRequested.connect(actions.append)

def text_item(item, label):
    if item.isVisible() and item.property('text') == label:
        return item
    for child in item.childItems():
        found = text_item(child, label)
        if found is not None:
            return found

def click(label):
    QTest.qWait(500)  # Settle the card flip before hit-testing its buttons.
    item = text_item(island._root, label)
    assert item is not None, label
    point = item.mapToScene(QPointF(item.width()/2, item.height()/2)).toPoint()
    QTest.mouseClick(island, Qt.LeftButton, Qt.NoModifier, point)
    QTest.qWait(150)

def expire():
    island._deadline = time.monotonic() - 1
    island._tick()
    QTest.qWait(150)

expire()
click('休息')
assert actions[-1] == 'break' and island._current_task()['type'] == 'break', actions
expire()
click('下一步')
assert actions[-1] == 'focus' and island._current_task()['title'] == '完成练习', actions
assert not island.guided_waiting and island._timer.isActive()
messages = []
backend.messageRequested.connect(lambda *args: messages.append(args))
expire()
backend._ai_request_running = True
rewards = backend._guided_reward_seq
click('下一步')  # Last step needs AI, so the busy condition must be visible.
assert island.guided_waiting and backend._guided_reward_seq == rewards
assert messages[-1][0] == 'info' and island._root.property('guidedError')
click('休息')  # A local break must not be blocked by an unrelated AI request.
assert island._current_task()['type'] == 'break' and island._timer.isActive()
assert not island._root.property('guidedError')
backend._ai_request_running = False
active = backend.focus_journey.active
active['source']['pendingClarification'] = {'id': 'q', 'questions': []}
expire()
with patch.object(backend, 'enterFocusStudio', return_value=True) as enter:
    click('补充进度')
    enter.assert_called_once()
assert island.guided_waiting
click('休息')  # Even a completed break / pending clarification can start another rest.
assert island._current_task()['type'] == 'break' and island._timer.isActive()
expire()
backend._guided_pending = {'id': active['id'], 'index': island.current_index}
backend.focusSessionChanged.emit()
assert island._root.property('guidedBusy')
click('休息')  # Cancel application of the old request when choosing a local rest.
assert backend._guided_pending is None and not island._root.property('guidedBusy')
assert island._timer.isActive()
active['source'].pop('pendingClarification', None)
backend.focusSessionChanged.emit()
island.tasks = island.tasks[:3]  # Retry the final focus step, without queued rests.
island._load_and_start_task(2)
expire()
with patch.object(backend, '_request_ai'):
    click('下一步')
    reward_count = backend._guided_reward_seq
    acknowledged_count = len(active['source']['completedActions'])
    backend._guided_pending = None  # Simulate a failed response, then retry.
    backend._guided_error = '测试：请求失败'
    backend.focusSessionChanged.emit()
    click('下一步')
    assert backend._guided_reward_seq == reward_count
    assert len(active['source']['completedActions']) == acknowledged_count
assert not island.errors() and not warnings
print(json.dumps({'ok': True, 'actions': actions, 'warnings': warnings}), flush=True)
faulthandler.cancel_dump_traceback_later()
backend.shutdown()
root.close()
DATA.cleanup()
os._exit(0)
