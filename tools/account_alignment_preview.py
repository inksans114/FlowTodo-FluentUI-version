"""Check the sidebar row at fractional display scales using temporary data."""
from pathlib import Path
source=Path(__file__).with_name('focus_preview.py').read_text(encoding='utf-8').split('QTest.qWait(500)')[0]
source=source.replace('os.environ["LOCALAPPDATA"] = DATA.name','os.environ["LOCALAPPDATA"] = DATA.name\nos.environ["FLOWTODO_DATA_DIR"] = str(Path(DATA.name)/"data")\nos.environ["FLOWTODO_RINUI_CONFIG_DIR"] = str(Path(DATA.name)/"rinui")')
exec(compile(source,str(Path(__file__).with_name('focus_preview.py')),'exec'))
output=ROOT/'work/account-alignment';output.mkdir(parents=True,exist_ok=True)
backend._cloud.refresh_timer.stop();backend._cloud.refresh=lambda:None
root.setWidth(1180);root.setHeight(760);QTest.qWait(650)
evaluate('navigationView.navigationBar.collapsed = false');QTest.qWait(350)
row=find_visual(root.contentItem(),'accountMenuRoot');assert row
for plan in ['free','lite','standard']:
    row.setProperty('account',{'name':'本地访客','initials':'F','planId':plan,'plan':plan.title(),'local':True,'usage':{}})
    QTest.qWait(120)
    items=[find_visual(root.contentItem(),n) for n in ['sidebarAccountAvatar','sidebarAccountName','sidebarAccountBadge','sidebarAccountMore']]
    assert all(x is not None for x in items)
    centers=[x.mapToScene(x.boundingRect().center()).y() for x in items]
    assert max(centers)-min(centers)<0.6,centers
    frame=root.grabWindow();ratio=frame.devicePixelRatio()
    rect=row.mapRectToScene(row.boundingRect())
    crop=frame.copy(int(rect.x()*ratio),int(rect.y()*ratio),int(rect.width()*ratio),int(rect.height()*ratio))
    assert crop.save(str(output/(plan+'-'+os.environ.get('QT_SCALE_FACTOR','1')+'.png')))
assert not warnings,'\n'.join(warnings)
backend.shutdown();root.hide();app.processEvents();DATA.cleanup()
print('PASS: avatar, name, plan badge and menu centers aligned; all three plans; scale '+os.environ.get('QT_SCALE_FACTOR','1'),flush=True)
os._exit(0)
