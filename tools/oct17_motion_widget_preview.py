"""Render light motion, settings and the compact desktop widget using disposable data."""
from pathlib import Path
source=Path(__file__).with_name('focus_preview.py').read_text(encoding='utf-8').split('QTest.qWait(500)')[0]
source=source.replace('os.environ["LOCALAPPDATA"] = DATA.name','os.environ["LOCALAPPDATA"] = DATA.name\nos.environ["FLOWTODO_DATA_DIR"] = str(Path(DATA.name)/"data")\nos.environ["FLOWTODO_RINUI_CONFIG_DIR"] = str(Path(DATA.name)/"rinui")')
exec(compile(source,str(Path(__file__).with_name('focus_preview.py')),'exec'))
output=ROOT/'work/oct17-ui';output.mkdir(parents=True,exist_ok=True)
backend._cloud.refresh_timer.stop();backend._cloud.refresh=lambda:None
def collect(item,name):
    rows=[item] if item.objectName()==name else []
    for child in item.childItems():rows+=collect(child,name)
    return rows
for name in ['NoteSettings.qml','AppSettings.qml','AppAppearanceSettings.qml','FocusGuardApps.qml','CustomAppearance.qml']:
    root.setWidth(1180);root.setHeight(850)
    open_page('SettingsHub.qml');QTest.qWait(650)
    open_page(name);QTest.qWait(650)
    back=find_visual(root.contentItem(),'settingsPageBack')
    if name in ('NoteSettings.qml','CustomAppearance.qml'):assert back is not None,(name,warnings)
    if name=='NoteSettings.qml':
        render('note-settings-back',1180,850)
        QTest.mouseClick(root,Qt.LeftButton,Qt.NoModifier,back.mapToScene(back.boundingRect().center()).toPoint());QTest.qWait(250)
        nav=root.findChild(QObject,'MainNavigationView');assert str(nav.property('currentPage')).endswith('SettingsHub.qml')
open_page('IslandSettings.qml');QTest.qWait(350)
render('island-settings-wide',1360,850);render('island-settings-narrow',850,850)
open_page('AiWorkspace.qml');QTest.qWait(450);root.setWidth(1180)
buttons=collect(root.contentItem(),'voiceCaptureButton');voice=next(b for b in buttons if b.isVisible() and b.metaObject().indexOfProperty('expanded')>=0)
voice.setProperty('motionEnabled',True)
start=voice.width();voice.setProperty('expanded',True);QTest.qWait(80)
assert start<voice.width()<160,(start,voice.width())
def assert_voice_spacing():
    help=find_visual(root.contentItem(),'inlineHelp');assert help
    a=voice.mapRectToScene(voice.boundingRect());b=help.mapRectToScene(help.boundingRect())
    assert b.left()-a.right()>=7,(a,b)
    parent=find_visual(root.contentItem(),'aiVoiceCapture');assert parent
    assert abs(parent.width()-voice.width())<1,(parent.width(),voice.width())
assert_voice_spacing()
QTest.qWait(220);assert voice.width()>=150
assert_voice_spacing()
render('ai-voice-expanded',1180,850)
voice.setProperty('expanded',False);QTest.qWait(70);assert_voice_spacing();QTest.qWait(150);assert_voice_spacing()
help=find_visual(root.contentItem(),'inlineHelp');assert help is not None
QTest.mouseClick(root,Qt.LeftButton,Qt.NoModifier,help.mapToScene(help.boundingRect().center()).toPoint());QTest.qWait(250)
render('ai-help-expanded',1180,850)
backend.local_database=[{'id':789,'title':'用一句话写下应用要解决的问题','meta':'建议先花10分钟，先写下一个小目标，再开始行动。无需一次完成所有事情。','done':False}]
backend.tasksChanged.emit()
component=QQmlComponent(window.engine,QUrl.fromLocalFile(str(ROOT/'qml/DesktopTodoWidget.qml')))
desktop=component.create(window.engine.rootContext());assert desktop is not None,[e.toString() for e in component.errors()]
desktop.show();QTest.qWait(300)
assert desktop.height()<220,desktop.height()
assert desktop.grabWindow().save(str(output/'desktop-widget-compact.png'))
check=find_visual(desktop.contentItem(),'DesktopTaskCheckbox_789');assert check is not None
QTest.mouseClick(desktop,Qt.LeftButton,Qt.NoModifier,check.mapToScene(check.boundingRect().center()).toPoint());QTest.qWait(250)
assert backend.local_database[0]['done']
assert not warnings,'\n'.join(warnings)
desktop.hide();desktop.deleteLater();backend.shutdown();root.hide();app.processEvents();DATA.cleanup()
print('PASS: settings back navigation, responsive island previews, voice expansion timing, help popup, compact widget checkbox; no QML warnings.',flush=True)
os._exit(0)
