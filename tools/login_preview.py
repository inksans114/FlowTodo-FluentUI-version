"""Render isolated native login states; assert unauthenticated profile writes are blocked."""
from pathlib import Path
source=Path(__file__).with_name('focus_preview.py').read_text(encoding='utf-8').split('QTest.qWait(500)')[0]
source=source.replace('os.environ["LOCALAPPDATA"] = DATA.name','os.environ["LOCALAPPDATA"] = DATA.name\nos.environ["FLOWTODO_DATA_DIR"] = str(Path(DATA.name) / "data")\nos.environ["FLOWTODO_RINUI_CONFIG_DIR"] = str(Path(DATA.name) / "RinUI/config")')
exec(compile(source,str(Path(__file__).with_name('focus_preview.py')),'exec'))
output=ROOT/'work/login-preview';output.mkdir(parents=True,exist_ok=True)
backend._cloud.refresh_timer.stop();backend._cloud.refresh=lambda:None
backend._cloud.client.vault.memory={}
QTest.qWait(700);open_page('LoginPage.qml');QTest.qWait(700)
page=find_visual(root.contentItem(),'LoginPage')
if page is None:
    diagnostic=QQmlComponent(window.engine,QUrl.fromLocalFile(str(ROOT/'qml/pages/LoginPage.qml')))
    print('LOGIN DIAGNOSTICS',[e.toString() for e in diagnostic.errors()],warnings,flush=True)
assert page is not None,'Login page missing'
render('login-light',1180,820)
render('login-compact',900,760)
backend.settings_database['theme']='dark';evaluate('applySavedAppearance()');QTest.qWait(150)
render('login-dark',1180,820)
backend._cloud.error='暂时无法连接，请检查网络后重试。';backend.accountChanged.emit()
render('login-error',1180,820)
assert backend.renameAccount('Forbidden guest edit') is False
assert backend.loadAccountAvatar('nonexistent.png')==''
assert backend.saveAccountAvatar(.5,.5,1) is False
assert backend.removeAccountAvatar() is False
assert not warnings,'\n'.join(warnings)
backend.shutdown();root.hide();app.processEvents()
print('PASS: independent login, light/dark/compact/error render, guest profile protection, no QML warnings.',flush=True)
DATA.cleanup();os._exit(0)
