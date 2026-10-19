"""Real WebEngine return/recovery and Chinese install paths, offline and isolated."""
from pathlib import Path
source = Path(__file__).with_name('studio_preview.py').read_text(encoding='utf-8').split('\ntry:\n')[0]
source = source.replace('os.environ["LOCALAPPDATA"] = DATA.name',
    'os.environ["LOCALAPPDATA"] = DATA.name\nos.environ["FLOWTODO_DATA_DIR"] = str(Path(DATA.name)/"data")\nos.environ["FLOWTODO_RINUI_CONFIG_DIR"] = str(Path(DATA.name)/"rinui")')
exec(compile(source, str(Path(__file__).with_name('studio_preview.py')), 'exec'))
import shutil
import time
from guided_focus import island_tasks, validate_guidance

backend.settings_database['notificationSoundEnabled'] = False
backend.settings_database['focusMusicAutoPlay'] = False
guide = validate_guidance({'goal': '完成英语作业', 'style': 'chunks', 'intro': '只做眼前这一段。',
    'breakMinutes': 3, 'restAfterMinutes': 40, 'steps': [
    {'title': '阅读材料', 'detail': '先读这一页', 'minutes': 2, 'type': 'focus'},
    {'title': '完成练习', 'detail': '写下答案', 'minutes': 7, 'type': 'focus'}]})
tasks = island_tasks(guide)
session = {'mode': 'single', 'kind': 'guided', 'title': guide['goal'], 'guidance': guide,
           'completedActions': [], 'totalSeconds': sum(t['time'] for t in tasks), 'totalTasks': len(tasks)}
assert backend._launch_island(tasks, 'single', session, backend._focus_options({'keepWindowOpen': True, 'guided': True}))
island = next(iter(backend.island_windows.values()))
assert backend.enterFocusStudio('tree')
studio = view = backend._studio_window
wait_until(lambda: view.loaded, 'Initial scene did not load')
wait_until(lambda: probe('Boolean(window.flowFocus && window.flowFocus.connected)'), 'WebChannel missing')
session_id = backend.focus_journey.active['id']

def ready():
    wait_until(lambda: view.loaded, 'Returned scene did not load')
    wait_until(lambda: probe('Boolean(window.flowFocus && window.flowFocus.connected && document.getElementById("timer"))'), 'Returned scene is blank')
    assert probe('document.body.innerText.length') > 100
    frame = view.grab().toImage()
    colors = {frame.pixelColor(x, y).rgb() for x in range(0, frame.width(), max(1, frame.width()//12))
              for y in range(0, frame.height(), max(1, frame.height()//12))}
    assert len(colors) > 4, 'Scene window is a uniform blank frame'
    assert next(iter(backend.island_windows.values())) is island
    assert backend.focus_journey.active['id'] == session_id
    assert not view.studio_page.console_errors, view.studio_page.console_errors

def click_island(action):
    wait_ms(500)
    item = find(island._root, 'followup_' + action)
    assert item is not None and item.isVisible(), action
    point = item.mapToScene(item.boundingRect().center()).toPoint()
    QTest.mouseClick(island, Qt.LeftButton, Qt.NoModifier, point)
    wait_ms(250)

def expire():
    island._deadline = time.monotonic() - 1
    island._tick()
    wait_ms(250)

backend.exitFocusStudio()
expire()
click_island('break')
assert island._current_task()['type'] == 'break'
expire()
click_island('focus')
assert island._current_task()['title'] == '完成练习' and island._timer.isActive()
expire()
for _ in range(3):
    click_island('studio')
    ready()
    assert studio.isFullScreen() and not island.isVisible()
    assert probe('document.getElementById("timer").textContent') == '00:00'
    backend.exitFocusStudio()
    assert island.isVisible()

# Load a real relocated set of assets to reproduce testers' Chinese/space directories.
assets = Path(DATA.name) / 'FlowTodo 中文测试 50% #版' / 'focus-studio'
shutil.copytree(ROOT / 'focus-studio', assets)
view.studio_page.entry_path = (assets / 'index.html').resolve()
view._entry_url = QUrl.fromLocalFile(str(view.studio_page.entry_path))
view._entry_url.setFragment('software')
view.setUrl(view._entry_url)
click_island('studio')
ready()
assert Path(view.url().toLocalFile()).resolve() == view.studio_page.entry_path
backend.exitFocusStudio()

# Reproduce a cached, empty page, then exercise the bounded readiness recovery.
view.studio_page.runJavaScript('document.body.replaceChildren(); window.flowFocus = null')
wait_ms(100)
click_island('studio')
wait_ms(5500)
print(json.dumps({'recovery': view._recovery_attempts, 'loaded': view.loaded, 'loading': view._loading,
    'watchdog': view._ready_watchdog.isActive(), 'immersive': backend._immersive_active,
    'visible': view.isVisible(), 'errors': view.studio_page.console_errors}, ensure_ascii=False), flush=True)
ready()
assert view._recovery_attempts == 1
backend.exitFocusStudio()

# Simulate renderer failure through Qt's handler without killing a user process.
click_island('studio')
view._on_renderer_terminated(None, 1)
wait_ms(500)
ready()
assert island.guided_waiting and island.current_index == 2
backend.exitFocusStudio()

active = backend.focus_journey.active
active['source']['pendingClarification'] = {'id': 'return-questions', 'context': {},
    'questions': [{'question': '现在做到哪里了？', 'field': 'position', 'choices': []}]}
backend.focusSessionChanged.emit()
click_island('focus')
ready()
wait_until(lambda: probe('document.getElementById("progress-dialog").open'), 'Floating next did not open questions')
probe('(document.getElementById("progress-dialog").close(), true)')
backend.exitFocusStudio()
click_island('studio')
ready()
wait_until(lambda: probe('document.getElementById("progress-dialog").open'), 'Returning did not reopen unanswered questions')
backend.exitFocusStudio()

# A genuinely unrecoverable local page must leave fullscreen rather than stay blank.
view._entry_url = QUrl.fromLocalFile(str(assets / 'missing.html'))
click_island('studio')
view._on_renderer_terminated(None, 1)
wait_until(lambda: not backend._immersive_active, 'Unrecoverable scene trapped the user in fullscreen')
assert root.isVisible() and island.isVisible() and island.guided_waiting
assert backend.focus_journey.active['id'] == session_id

print(json.dumps({'ok': True, 'checks': ['actual rest/next/return clicks', 'three fullscreen returns',
    'same session and timer', 'Chinese space percent/hash install path', 'empty cached page recovery',
    'renderer failure recovery', 'pending questions reopen', 'unrecoverable page returns to app'], 'warnings': warnings}, ensure_ascii=False), flush=True)
faulthandler.cancel_dump_traceback_later()
backend.shutdown()
for item in app.topLevelWindows():
    item.hide()
DATA.cleanup()
os._exit(0)
