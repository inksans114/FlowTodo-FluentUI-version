"""Exercise detailed plan import through the real Qt backend with isolated data."""
from pathlib import Path
source=Path(__file__).with_name('focus_preview.py').read_text(encoding='utf-8').split('QTest.qWait(500)')[0]
source=source.replace('os.environ["LOCALAPPDATA"] = DATA.name','os.environ["LOCALAPPDATA"] = DATA.name\nos.environ["FLOWTODO_DATA_DIR"] = str(Path(DATA.name)/"data")\nos.environ["FLOWTODO_RINUI_CONFIG_DIR"] = str(Path(DATA.name)/"RinUI/config")')
exec(compile(source,str(Path(__file__).with_name('focus_preview.py')),'exec'))
from datetime import date,timedelta
from ai_library import remember,find
backend._cloud.refresh_timer.stop()
events=[];backend.messageRequested.connect(lambda *args:events.append(args))
original_ids=[t['id'] for t in backend.local_database]
today=backend._today();tomorrow=(date.fromisoformat(today)+timedelta(days=1)).isoformat()
plan={'title':'详细规划集成测试','tasks':[{'title':'完成桌面原型','scheduledDate':tomorrow,'durationMinutes':25}],'groups':[{'name':'原型流程','steps':[{'name':'完成桌面原型','duration':25}]}],'projects':[{'name':'桌面应用项目','milestones':[{'title':'原型完成'}]}]}
remember(backend.ai_state_database,plan)
backend.ai_state_database['latestPlan']=plan;backend.aiStateChanged.emit()
root.setWidth(1360);root.setHeight(900)
open_page('AiPlanWorkspace.qml');QTest.qWait(700)
render('detailed-plan-import-check',1360,900)
button=find_visual(root.contentItem(),'detailedPlanImportButton');assert button is not None and button.isVisible(),str(warnings)
QTest.mouseClick(root,Qt.LeftButton,Qt.NoModifier,button.mapToScene(button.boundingRect().center()).toPoint());QTest.qWait(250)
assert events and events[-1][0]=='success',events
task=next(t for t in backend.local_database if t['title']=='完成桌面原型')
assert task['scheduledDate']==tomorrow and task['durationMinutes']==25
group=next(g for g in backend.groups_database if g['name']=='原型流程');assert group['steps'][0]['taskId']==task['id']
assert any(p['name']=='桌面应用项目' for p in backend.projects_database)
assert all(any(t['id']==id for t in backend.local_database) for id in original_ids)
n=len(backend.local_database);assert backend.applyAiPlan(json.dumps(plan));assert len(backend.local_database)==n
assert not backend.applyAiPlan('{invalid') and events[-1][0]=='error'
long={'title':'三日学习计划','mode':'long','longPlan':{'cycles':[{'days':[{'dateOffset':i,'tasks':[{'title':'每日练习'}]} for i in range(3)]}]}}
assert backend.applyAiPlan(json.dumps(long))
daily=[t for t in backend.local_database if t['title']=='每日练习'];assert len(daily)==3 and len({t['scheduledDate'] for t in daily})==3
n=len(backend.local_database);assert backend.applyAiPlan(json.dumps(long));assert len(backend.local_database)==n
assert not backend.long_plan_database.get('active')
from cloud_records import import_record,snapshot
from uuid import uuid4
remote={'id':str(uuid4()),'kind':'aiPlans','title':'云端详细规划','version':1,'updatedAt':'2026-10-11T00:00:00Z','payload':{'format':'flowtodo-desktop-v1','_syncUid':'cloud-detailed','record':{'plan':{'libraryId':uuid4().hex,'title':'云端详细规划','tasks':[{'title':'云端导入后接入任务'}]}}}}
key=import_record(backend,remote);row=next(r for r in backend.ai_state_database['savedPlans'] if r.get('_cloudUid')=='cloud-detailed')
assert row['plan']['libraryId']==row['id'];assert backend.openSavedAiPlan(row['id'])
assert backend.applyAiPlan(json.dumps(row['plan']));assert any(t['title']=='云端导入后接入任务' for t in backend.local_database)
assert len([r for r in backend.ai_state_database['savedPlans'] if r['id']==row['id']])==1
assert find(backend.ai_state_database,row['id'])['plan']['ecosystemImported']
assert not warnings,'\n'.join(warnings)
backend.shutdown();root.hide();app.processEvents();DATA.cleanup()
print('PASS: detailed plan -> tasks, linked flow, project, dated calendar; repeat dedup; failure feedback; cloud plan library identity; no focus auto-start.',flush=True)
os._exit(0)
