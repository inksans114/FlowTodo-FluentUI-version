"""Offline pipeline and native UI QA; never records or calls a paid provider."""
from pathlib import Path
source = Path(__file__).with_name('focus_preview.py').read_text(encoding='utf-8')
exec(compile(source.split('QTest.qWait(500)')[0], str(Path(__file__).with_name('focus_preview.py')), 'exec'))
from PySide6.QtQml import QQmlEngine
import compat_backend

# Never send a global shortcut or open system microphone UI in automation.
dictation_calls = []
compat_backend.open_voice_typing = lambda handle: dictation_calls.append(handle) or True

backend.settings_database['notificationSoundEnabled'] = False
backend.settings_database['aiAutoApply'] = True
backend.settings_database['aiReplaceOnApply'] = True
backend.long_plan_database = {'active':True, 'pendingReview':False}
backend.local_database = [{'id':101,'title':'已有的任务','done':False}]
requests, results = [], []
backend.signalAiPlanReady.connect(lambda data: results.append(json.loads(data)))
def response(messages, long_mode=False, **kwargs):
    requests.append(messages)
    return json.dumps({'title':'先记下来','mode':'short','summary':'记下两件事。报告先打开数据表，今天不安排买猫粮。',
        'tasks':[{'title':'交报告','meta':'先打开数据表；完成后检查数据','scheduledDate':'2026-10-13','scheduledTime':'14:00'},
                 {'title':'联系组员','meta':'确认交稿时间'}],'groups':[],'projects':[],
        'guidance':{'goal':'交报告并联系组员','intro':'先打开数据表就可以开始。','style':'chunks',
            'steps':[{'title':'打开报告数据表','detail':'查看已有数据，先标记待核对的一处。','minutes':8,'type':'focus'}]}},ensure_ascii=False)
backend._call_ai_chat = response
QTest.qWait(500)
assert len(root.property('navigationItems').toVariant()) == 6
open_page('AiWorkspace.qml')
QTest.qWait(300)
render('ai-simple',1180,900)
assert find_visual(root.contentItem(),'voiceCaptureButton')
voice_button = find_visual(root.contentItem(),'voiceCaptureButton')
press = QQmlExpression(QQmlEngine.contextForObject(voice_button),voice_button,'clicked()')
press.evaluate()
assert not press.hasError(), press.error().toString()
QTest.qWait(400)
original = find_visual(root.contentItem(),'captureOriginal')
assert original.property('activeFocus'), 'System dictation must target the text editor'
assert len(dictation_calls) == 1, 'Default voice input must work without API credentials'
assert backend.speechInput.state == 'idle'
consent = root.findChild(QObject,'voiceConsent')
assert not consent.property('visible'), 'System voice input must not ask for cloud upload'
# Focus changing before delayed activation must cancel the shortcut.
backend.openSystemDictation(original)
original.setProperty('focus',False)
QTest.qWait(200)
assert len(dictation_calls) == 1
backend.setSetting('speechInputMode','cloud')
press.evaluate()
QTest.qWait(400)
consent = root.findChild(QObject,'voiceConsent')
assert consent and consent.property('visible')
assert backend.speechInput.state == 'idle', 'Consent must precede microphone capture'
consent.setProperty('visible',False)
backend.setSetting('speechInputMode','system')
backend._run_ai_plan_request(json.dumps({'captureMode':True, 'messages':[{'role':'user','content':'明天交报告，不对，下周二下午两点。还得联系组员，猫粮不用买。'}]}))
QTest.qWait(250)
assert results[-1]['ok'] and not results[-1]['applied']
assert len(backend.local_database) == 1
assert requests[-1][-1]['content'].endswith('猫粮不用买。')
page = find_visual(root.contentItem(),'captureOriginal')
while page and page.metaObject().indexOfProperty('drafts') < 0:
    page = page.parentItem()
assert page
expr = QQmlExpression(window.engine.rootContext(),page,'showResult(); showDrafts=true')
expr.evaluate()
assert not expr.hasError(), expr.error().toString()
QTest.qWait(200)
checkbox = find_visual(root.contentItem(),'captureSelect_1')
assert checkbox
checkbox.setProperty('checked',False)
local = QQmlExpression(QQmlEngine.contextForObject(checkbox),checkbox,'toggled()')
local.evaluate()
QTest.qWait(100)
assert page.property('drafts').toVariant()[1]['_skip']
render('ai-drafts',1180,1000)
tasks = [t for t in page.property('drafts').toVariant() if not t.get('_skip')]
assert backend.importCapture(json.dumps(tasks))
assert len(backend.local_database) == 2
assert backend.local_database[0]['scheduledDate'] == '2026-10-13'
assert backend.local_database[0]['scheduledTime'] == '14:00'
assert backend.importCapture(json.dumps(tasks))
assert len(backend.local_database) == 2
assert backend.ai_state_database['latestPlan']['captureImported']
backend._call_ai_chat = lambda *a,**kw: '{"tasks":[{"title":"错误任务","done":true}]}'
backend._run_ai_plan_request(json.dumps({'captureMode':True,'messages':[{'role':'user','content':'记一件事'}]}))
assert not results[-1]['ok'] and len(backend.local_database) == 2
assert backend.speechInput.state == 'idle'
assert not backend.speechInput.start()  # No configured key: must not open mic.
class FakeMusic:
    def __init__(self): self.status = QMediaPlayer.PlaybackState.StoppedState; self.starts = 0
    def setSource(self, _source): pass
    def play(self): self.starts += 1; self.status = QMediaPlayer.PlaybackState.PlayingState
    def pause(self): self.status = QMediaPlayer.PlaybackState.PausedState
    def stop(self): self.status = QMediaPlayer.PlaybackState.StoppedState
    def playbackState(self): return self.status
from PySide6.QtMultimedia import QMediaPlayer
backend._focus_music = FakeMusic()
backend._play_focus_music()
assert backend._focus_music.starts == 0
backend.settings_database['focusMusicPath'] = str(ROOT/'audio.mp3')
backend.settings_database['focusMusicAutoPlay'] = True
backend._play_focus_music()
assert backend._focus_music.starts == 1
backend._on_focus_session_payload('{"event":"paused"}')
assert backend._focus_music.status == QMediaPlayer.PlaybackState.PausedState
backend._on_focus_session_payload('{"event":"resumed"}')
assert backend._focus_music.starts == 2
backend.setSetting('focusMusicAutoPlay',False)
assert backend._focus_music.status == QMediaPlayer.PlaybackState.StoppedState
for name in ('AiSettings','AiPlanWorkspace','HomeDashboard','ToolsHub'):
    if name == 'AiSettings': QTest.qWait(7000)
    component = QQmlComponent(window.engine, QUrl.fromLocalFile(str(ROOT/'qml/pages'/(name+'.qml'))))
    assert not component.isError(), '\n'.join(e.toString() for e in component.errors())
    open_page(name+'.qml')
    QTest.qWait(1000)
    render('ai-'+name,1180,1000)
open_page('AiWorkspace.qml')
QTest.qWait(1000)
render('ai-compact',900,700)
errors=[w for w in warnings if any(x in w for x in ('TypeError','ReferenceError','Cannot assign','Binding loop','Error:'))]
assert not errors, '\n'.join(errors)
backend.shutdown()
root.hide()
DATA.cleanup()
print(json.dumps({'ok':True,'checks':['six navigation entries','system dictation without API key','editor focus and delayed cancellation','cloud upload remains opt-in','capture draft only','ongoing long plan preserved','select/unselect drafts','date/time retained','merge without replacement','duplicate prevention','invalid output rejected','unconfigured mic remains closed','AI/settings/compact renders'],'warnings':warnings},ensure_ascii=False),flush=True)
os._exit(0)
