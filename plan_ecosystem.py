"""Detailed plans join existing task, flow, project and calendar stores."""
import copy
from datetime import datetime,timedelta
def prepare(backend,raw):
    if not isinstance(raw,dict):raise ValueError('规划数据无效，请重新打开已保存方案。')
    plan=backend._normalize_ai_plan(raw)
    for key in ('libraryId','captureMode','captureImported','captureOriginal'):
        if key in raw:plan[key]=copy.deepcopy(raw[key])
    dated=copy.deepcopy(raw.get('tasks') or [])
    from ai_library import find
    previous=find(backend.ai_state_database,raw.get('libraryId')) or {}
    start=datetime.strptime((previous.get('ecosystemImport') or {}).get('startDate') or backend._today(),'%Y-%m-%d').date()
    for cycle in (plan.get('longPlan') or {}).get('cycles',[]):
        for day in cycle.get('days',[]):
            date=(start+timedelta(days=max(0,int(day.get('dateOffset',0))))).isoformat()
            for task in day.get('tasks',[]):dated.append({**task,'scheduledDate':date})
    tasks=[];seen=set()
    for task in dated:
        if not isinstance(task,dict):continue
        rows=backend._normalize_ai_plan({'tasks':[task]})['tasks']
        if not rows:continue
        row=rows[0];key=(backend._fingerprint(row['title']),row.get('scheduledDate',''),row.get('scheduledTime',''))
        if key in seen:continue
        seen.add(key);row['id']=backend._new_id(len(tasks));tasks.append(row)
    plan['tasks']=tasks
    if not any(plan.get(k) for k in ('tasks','groups','projects')):raise ValueError('这份规划还没有可导入的任务、任务流或项目。')
    return plan
def apply(backend,raw):
    from ai_library import remember,find
    plan=prepare(backend,raw)
    added=backend._apply_ai_plan(plan,merge_missing=True,replace_ai=False)
    record=find(backend.ai_state_database,plan.get('libraryId'))
    if not record:record=remember(backend.ai_state_database,plan)
    record['plan']['ecosystemImported']=True
    record['ecosystemImport']={'added':added,'at':datetime.now().isoformat(timespec='seconds'),'startDate':(record.get('ecosystemImport') or {}).get('startDate') or backend._today()}
    by_title={}
    for task in backend.local_database:by_title.setdefault(backend._fingerprint(task['title']),[]).append(task)
    names={backend._fingerprint(g['name']) for g in plan['groups']}
    for group in backend.groups_database:
        if backend._fingerprint(group['name']) not in names:continue
        for step in group.get('steps',[]):
            candidates=by_title.get(backend._fingerprint(step.get('name','')),[])
            if len(candidates)==1 and not step.get('taskId'):step['taskId']=candidates[0]['id']
    backend._save_json(backend.groups_file,backend.groups_database)
    backend._save_ai_state(latest_plan=record['plan']);backend._emit_data_updates()
    return added
