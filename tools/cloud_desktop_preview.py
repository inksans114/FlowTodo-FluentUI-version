"""Check portable import IDs and render the new cloud account controls in isolation."""
from pathlib import Path
from uuid import uuid4
source=Path(__file__).with_name('focus_preview.py').read_text(encoding='utf-8').split('QTest.qWait(500)')[0]
source=source.replace('os.environ["LOCALAPPDATA"] = DATA.name','os.environ["LOCALAPPDATA"] = DATA.name\nos.environ["FLOWTODO_DATA_DIR"] = str(Path(DATA.name) / "data")\nos.environ["FLOWTODO_RINUI_CONFIG_DIR"] = str(Path(DATA.name) / "RinUI/config")')
exec(compile(source,str(Path(__file__).with_name('focus_preview.py')),'exec'))
output=ROOT/'work/cloud-preview';output.mkdir(parents=True,exist_ok=True)
from cloud_records import snapshot,import_record
import copy
backend._cloud.refresh_timer.stop();backend._cloud.refresh=lambda:None
backend._cloud.client.request=lambda *args,**kwargs:copy.deepcopy(backend._cloud.cache)
backend.local_database=[{'id':101,'title':'跨设备记录','meta':'同步备注','done':False}]
backend.groups_database=[{'id':201,'name':'关联流程','steps':[{'name':'执行记录','duration':15,'taskId':101}]}]
rows=snapshot(backend);task=next(r for r in rows if r['kind']=='tasks');flow=next(r for r in rows if r['kind']=='flows')
assert 'taskId' not in flow['payload']['record']['steps'][0]
assert flow['payload']['record']['steps'][0]['taskUid']==task['payload']['_syncUid']
backend.local_database=[];backend.groups_database=[]
for row in rows:
    if row['kind'] not in ('tasks','flows'):continue
    item={**copy.deepcopy(row),'id':str(uuid4()),'version':1,'updatedAt':'2026-10-11T00:00:00Z'}
    import_record(backend,item)
assert backend.local_database[0]['id']!=101
assert backend.groups_database[0]['steps'][0]['taskId']==backend.local_database[0]['id']
assert backend.local_database[0]['meta']=='同步备注'
uid=str(uuid4());backend._cloud.client.vault.memory={'accessToken':'0'*64}
backend._cloud.cache={'user':{'id':uid,'name':'Cheems','email':'preview@example.invalid','plan':'lite','balance':0},'avatar':{'data':'','revision':0},'officialAI':{'active':True,'remaining':100,'limit':100,'used':0}}
backend._cloud.cloud_library_uid=uid
backend._cloud.cloud_library=[{'id':str(uuid4()),'title':'明天一天内的多科作业计划','kind':'aiPlans','version':1,'payload':{'format':'flowtodo-desktop-v1','_syncUid':'preview-plan','record':{'plan':{'title':'学习计划','tasks':[{'title':'完成物理三张卷子','duration':35},{'title':'完成英语作业','duration':25},{'title':'整理化学练习','duration':30}],'captureOriginal':'先完成物理作业，再复习英语和化学。'*8}}}}]
backend.accountChanged.emit();open_page('UserAccount.qml');QTest.qWait(500)
render('cloud-account-preview',1180,980)
backend._cloud.browse_cloud=lambda trash=False: None
backend._cloud.cloud_library[0]['updatedAt']='2026-10-11T12:00:00Z'
backend._cloud.cache['cloud']={'connected':True,'location':'xiangyang-direct'}
backend._cloud.cache['usage']={'tasks':1,'flows':0,'aiPlans':0,'storageMB':0.01}
backend.accountChanged.emit();open_page('CloudStorage.qml');QTest.qWait(500)
render('cloud-storage-preview',1180,850)
render('cloud-storage-narrow',800,850)
def visible_items(name,item=None):
    item=item or root.contentItem()
    found=[item] if item.objectName()==name else []
    for child in item.childItems():found.extend(visible_items(name,child))
    return found
cards=visible_items('cloudRecordCard');assert cards
for card in cards:card.setProperty('expanded',True)
QTest.qWait(300)
render('cloud-storage-expanded',800,850)
details=visible_items('cloudRecordDetail');assert details
for detail in details:
    if detail.property('visible'):
        assert detail.property('lineHeight')==1.5
        assert detail.property('height')>80
root.setWidth(1180)
backend.setSetting('aiServiceMode','official');open_page('AiSettings.qml');QTest.qWait(500)
render('official-ai-preview',1180,850)
assert backend.settings_database['aiApiKey']==''
assert not warnings,'\n'.join(warnings)
cloud_plan=copy.deepcopy(backend._cloud.cloud_library[0])
backend._cloud.client.list_records=lambda trash=False: [] if trash else [cloud_plan]
before=len(backend.ai_state_database.get('savedPlans',[]))
backend.cloudImport(cloud_plan['id'])
import time
for _ in range(60):
    app.processEvents();time.sleep(0.025)
    if not backend._cloud.busy:break
print('IMPORT_CHECK',backend._cloud.status,backend._cloud.error,flush=True)
assert len(backend.ai_state_database['savedPlans'])==before+1
backend.cloudImport(cloud_plan['id'])
for _ in range(60):
    app.processEvents();time.sleep(0.025)
    if not backend._cloud.busy:break
assert len(backend.ai_state_database['savedPlans'])==before+1
assert '跳过' in backend._cloud.status
assert not warnings,'\n'.join(warnings)
old_rows=copy.deepcopy(backend.local_database)
backend.cloudLogout();QTest.qWait(600)
assert not backend._cloud.logged_in()
assert backend.local_database==old_rows
backend._cloud.client.vault.memory={};backend._cloud.close()
backend.shutdown();root.hide();app.processEvents()
print('PASS: remapped task IDs and flow references, retained note, cloud account QML, official selector without key, no QML warnings.',flush=True)
DATA.cleanup();os._exit(0)
