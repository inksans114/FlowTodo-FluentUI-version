"""Capture actual QML pages using only disposable sample data."""
from pathlib import Path
source = Path(__file__).with_name('focus_preview.py').read_text(encoding='utf-8').split('QTest.qWait(500)')[0]
source = source.replace('os.environ["LOCALAPPDATA"] = DATA.name', 'os.environ["LOCALAPPDATA"] = DATA.name\nos.environ["FLOWTODO_DATA_DIR"] = str(Path(DATA.name)/"data")\nos.environ["FLOWTODO_RINUI_CONFIG_DIR"] = str(Path(DATA.name)/"rinui")')
exec(compile(source, str(Path(__file__).with_name('focus_preview.py')), 'exec'))
output = ROOT / 'docs/images'
output.mkdir(parents=True, exist_ok=True)
backend._cloud.refresh_timer.stop()
backend._cloud.refresh = lambda: None
backend.settings_database['notificationSoundEnabled'] = False
backend.setSetting('theme', 'light')
backend.local_database = [
    {'id': 101, 'title': '毕业论文 · 整理文献中的三个观点', 'scheduledDate': backend._today_key(), 'done': False},
    {'id': 102, 'title': '英语阅读 · 完成一篇并整理生词', 'scheduledDate': backend._today_key(), 'done': False},
    {'id': 103, 'title': '散步 20 分钟，给大脑留一点空白', 'scheduledDate': backend._today_key(), 'done': False},
    {'id': 104, 'title': '整理今天的学习材料', 'scheduledDate': backend._today_key(), 'done': True}]
backend.tasksChanged.emit()
from ai_library import remember
plan = {'title': '把毕业论文推进一小步', 'tasks': [
    {'title': '阅读参考文献，提取三个观点', 'durationMinutes': 25},
    {'title': '把观点整理成文献综述的一段', 'durationMinutes': 25}],
    'groups': [{'name': '文献到段落', 'steps': [{'name': '整理资料', 'duration': 5},
        {'name': '专心阅读', 'duration': 25}, {'name': '写出第一段', 'duration': 25}]}], 'projects': []}
remember(backend.ai_state_database, plan)
backend.ai_state_database['latestPlan'] = plan
backend.aiStateChanged.emit()
root.setWidth(1360)
root.setHeight(900)
QTest.qWait(700)
for page, name in [('HomeDashboard.qml', 'today'), ('AiPlanWorkspace.qml', 'planning'),
                   ('GroupsWorkspace.qml', 'flows'), ('FocusWorkspace.qml', 'focus'),
                   ('IslandSettings.qml', 'island'), ('QuickCapture.qml', 'capture')]:
    open_page(page)
    QTest.qWait(750)
    render(name, 1360, 900)
assert not warnings, '\n'.join(warnings)
from PIL import Image
Image.open(ROOT / 'logopromax.ico').save(output / 'logo.png')
forest = ROOT / '.superdesign/qa/studio-forest-completed.png'
if forest.exists():
    Image.open(forest).save(output / 'forest.png')
backend.shutdown()
root.hide()
app.processEvents()
DATA.cleanup()
print('PASS: six current screenshots, disposable sample data, no QML warnings.', flush=True)
os._exit(0)
