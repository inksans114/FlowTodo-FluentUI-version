"""Exercise native home dictation without activating a real microphone."""
import faulthandler
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'vendor')]
os.chdir(ROOT)
DATA = tempfile.TemporaryDirectory(prefix='flowtodo-inline-dictation-')
os.environ['FLOWTODO_DATA_DIR'] = DATA.name
os.environ['FLOWTODO_RINUI_CONFIG_DIR'] = str(Path(DATA.name) / 'rinui')
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
os.environ['QT_QUICK_BACKEND'] = 'software'
os.environ['QT_QUICK_CONTROLS_STYLE'] = 'Basic'
faulthandler.dump_traceback_later(45, exit=True)
from PySide6.QtCore import QPointF, Qt, QUrl, QCoreApplication
from PySide6.QtGui import QFontDatabase, QInputMethodEvent
from PySide6.QtQml import QQmlEngine, QQmlExpression
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from RinUI import RinUIWindow
from compat_backend import RinUIBackend
from i18n_runtime import translator

app = QApplication([])
for font in ('msyh.ttc', 'segoeui.ttf', 'seguisb.ttf'):
    QFontDatabase.addApplicationFont(str(Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts' / font))
backend = RinUIBackend()
backend.local_database = []
backend.groups_database = []
backend.projects_database = []
window = RinUIWindow(shared_engine=False)
window.engine.rootContext().setContextProperty('Backend', backend)
window.engine.rootContext().setContextProperty('I18nBridge', translator())
warnings = []
window.engine.warnings.connect(lambda errors: warnings.extend(e.toString() for e in errors))
window.load(ROOT / 'qml/Main.qml')
root = window.root_window
assert root is not None, warnings
backend.attach_native_window(root)
root.setWidth(1180); root.setHeight(820)
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

def click(item):
    root.grabWindow(); QTest.qWait(60)
    point = item.mapToScene(QPointF(item.width()/2, item.height()/2)).toPoint()
    QTest.mouseMove(root, point); QTest.qWait(50)
    QTest.mouseClick(root, Qt.LeftButton, Qt.NoModifier, point)

def render(name):
    (ROOT / 'work').mkdir(exist_ok=True)
    assert root.grabWindow().save(str(ROOT / 'work' / (name + '.png')))

field = find(root.contentItem(), 'homeNewTask')
voice = find(root.contentItem(), 'homeVoice')
assert field is not None and voice is not None, warnings
render('inline-voice-idle')
with patch('compat_backend.open_voice_typing', return_value=True) as start, patch('compat_backend.close_voice_typing', return_value=True) as finish:
    field.setProperty('text', '今天：')
    field.setProperty('cursorPosition', len('今天：'))
    click(voice)
    QTest.qWait(350)
    assert start.call_count == 1
    assert start.call_args.args[0] == int(root.winId())
    assert field.property('activeFocus'), 'Windows receives the intended input field'
    assert voice.property('expanded') and voice.width() == 156
    assert find(root.contentItem(), 'QuickCapture') is None, 'No page navigation'
    bar = find(root.contentItem(), 'inlineWaveBar_3')
    amplitude = bar.property('amplitude')
    QTest.qWait(150)
    assert abs(bar.property('amplitude') - amplitude) > 0.001, 'The status waveform animates'
    event = QInputMethodEvent()
    event.setCommitString('整理研究材料')
    QCoreApplication.sendEvent(root, event)
    QTest.qWait(80)
    assert field.property('text') == '今天：整理研究材料', field.property('text')
    render('inline-voice-active')
    assert not backend.local_database, 'Dictation never automatically adds a task'
    click(voice); QTest.qWait(220)
    assert not voice.property('active') and abs(voice.width() - 44) < 0.1, (voice.property('active'), voice.width(), start.call_count, finish.call_count)
    assert finish.call_count == 1
    assert field.property('text') == '今天：整理研究材料'
    click(voice); QTest.qWait(350)
    QTest.keyClick(root, Qt.Key_Escape); QTest.qWait(200)
    assert not voice.property('active')
    # Cancel before the delayed Win+H request; no late opening is allowed.
    calls = start.call_count
    qml(voice, 'begin(); finish()')
    QTest.qWait(300)
    assert start.call_count == calls
    qml(voice, 'begin()')
    find(root.contentItem(), 'homeSearch').forceActiveFocus()
    QTest.qWait(300)
    assert start.call_count == calls and not voice.property('active'), 'A changed input focus cancels delayed activation'
    # Failed activation collapses the button, retaining all draft text.
    start.return_value = False
    click(voice); QTest.qWait(350)
    assert not voice.property('active')
    assert field.property('text') == '今天：整理研究材料'
    start.return_value = True
    # Reduced motion and dark/compact views use the same native controls.
    voice.setProperty('motionEnabled', False)
    backend.setSetting('speechInputMode', 'cloud')
    click(voice); QTest.qWait(200)
    assert voice.property('expanded') and voice.width() == 156
    assert backend.speechInput.state == 'idle', 'This shortcut always uses system dictation'
    backend.setSetting('theme', 'dark'); QTest.qWait(180)
    render('inline-voice-dark')
    root.setWidth(900); root.setHeight(620); QTest.qWait(220)
    assert field.width() > 200
    render('inline-voice-compact')
    backend.setSetting('theme', 'light'); QTest.qWait(180)
    render('inline-voice-compact-light')
    click(find(root.contentItem(), 'homeAddButton')); QTest.qWait(200)
    assert len(backend.local_database) == 1
    assert backend.local_database[0]['title'] == '今天：整理研究材料'
    assert field.property('text') == '' and not voice.property('active')
    print('PASS: direct home dictation; focus and text insertion; expand/collapse; Escape; cancellation; failure recovery; explicit Add; light/dark/compact; reduced motion.', flush=True)
assert not warnings, warnings
backend.shutdown()
root.hide(); app.processEvents(); DATA.cleanup()
os._exit(0)
