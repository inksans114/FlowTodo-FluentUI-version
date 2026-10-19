"""Portable record envelopes; local integer IDs never cross device boundaries."""
import copy
import json
from pathlib import Path
from uuid import uuid4
from ai_library import write_state, title as plan_title

def collections(backend):
    return [('tasks', backend.local_database, backend.tasks_file),
            ('flows', backend.groups_database, backend.groups_file),
            ('aiPlans', backend.ai_state_database.setdefault('savedPlans', []), backend.ai_state_file)]

def snapshot(backend):
    result=[]
    for kind, records, path in collections(backend):
        changed=False
        for record in records:
            if not record.get('_cloudUid'):
                record['_cloudUid']=uuid4().hex;changed=True
        if changed:write_state(Path(path), backend.ai_state_database if kind=='aiPlans' else records)
    task_ids={r['id']:r['_cloudUid'] for r in backend.local_database}
    for kind, records, _ in collections(backend):
        for record in records:
            value=copy.deepcopy(record);uid=value.pop('_cloudUid');value.pop('id',None)
            if kind=='flows':
                for step in value.get('steps',[]):
                    if 'taskId' in step:step['taskUid']=task_ids.get(step.pop('taskId'))
                    elif step.get('unresolvedTaskUid'):step['taskUid']=step.pop('unresolvedTaskUid')
            if kind=='aiPlans':
                # Execution state is local: importing a plan never starts a focus session.
                for key in ('journey','savedPath','path'):value.pop(key,None)
            payload={'_syncUid':uid,'format':'flowtodo-desktop-v1','record':value,'note':str(value.get('meta' if kind=='tasks' else 'cloudNote',''))}
            name=record.get('title') or record.get('name') or (plan_title(record.get('plan',{})) if kind=='aiPlans' else '未命名')
            result.append({'key':kind+':'+uid,'kind':kind,'title':str(name)[:120],'payload':payload})
    return result

def import_record(backend,item,key=None):
    kind=item['kind'];payload=item['payload']
    records,path=next((r,p) for k,r,p in collections(backend) if k==kind)
    old=next((r for r in records if key==kind+':'+r.get('_cloudUid','')),None)
    if old and kind=='aiPlans' and old.get('journey',{}).get('status') in ('running','paused','active'):
        raise ValueError('请先结束当前方案的执行，再导入云端版本。')
    uid=(old or {}).get('_cloudUid') or payload.get('_syncUid') or uuid4().hex
    if not isinstance(uid,str) or len(uid)>64:raise ValueError('Invalid record identity')
    value=copy.deepcopy(payload.get('record',{})) if payload.get('format')=='flowtodo-desktop-v1' else {}
    if not isinstance(value,dict):raise ValueError('Invalid record')
    if kind=='tasks':
        value['title']=item['title'];value.setdefault('done',False)
        value['meta']=str(payload.get('note',value.get('meta','')));value.setdefault('createdAt',item['updatedAt'])
    elif kind=='flows':
        value['name']=item['title'];value.setdefault('steps',[]);value.setdefault('relationId',uuid4().hex)
        value['cloudNote']=str(payload.get('note',value.get('cloudNote','')))
        if not isinstance(value['steps'],list) or len(value['steps'])>200 or any(not isinstance(s,dict) for s in value['steps']):raise ValueError('Invalid steps')
        task_ids={r['_cloudUid']:r['id'] for r in backend.local_database if r.get('_cloudUid')}
        for step in value['steps']:
            step.pop('taskId',None);reference=step.pop('taskUid',None)
            if reference in task_ids:step['taskId']=task_ids[reference]
            elif reference:step['unresolvedTaskUid']=reference
    else:
        for field in ('journey','savedPath','path'):value.pop(field,None)
        value.setdefault('plan',{'title':item['title'],'tasks':[],'captureOriginal':str(payload.get('note',''))})
        value['cloudNote']=str(payload.get('note',value.get('cloudNote','')))
        if not isinstance(value['plan'],dict):raise ValueError('Invalid plan')
        if old and old.get('journey'):value['journey']=copy.deepcopy(old['journey'])
        value.setdefault('createdAt',item['updatedAt'])
    value['_cloudUid']=uid
    value['id']=old['id'] if old else uuid4().hex if kind=='aiPlans' else max([999]+[int(r['id']) for r in records]+[int(r.get('id',0)) for r in backend.stats_database.get('history',[]) if isinstance(r.get('id'),int)])+1
    if kind=='aiPlans':
        from ai_library import title
        value['plan']['libraryId']=value['id']
        if not old:
            value['plan'].pop('captureImported',None);value['plan'].pop('ecosystemImported',None)
        value['title']=title(value['plan'])
        value['kind']='capture' if value['plan'].get('captureMode') else 'long' if value['plan'].get('mode')=='long' else 'short'
        value.setdefault('updatedAt',item['updatedAt'])
    backups=Path(backend.data_dir)/'cloud-backups';backups.mkdir(exist_ok=True)
    backup=backups/(kind+'-'+uuid4().hex+'.json')
    write_state(backup,backend.ai_state_database if kind=='aiPlans' else records)
    # Retain twenty complete versions, without removing any unrelated files.
    for stale in sorted(backups.glob(kind+'-*.json'),key=lambda p:p.stat().st_mtime,reverse=True)[20:]:stale.unlink()
    updated=[value if r is old else r for r in records]
    if old is None:updated.append(value)
    state=copy.deepcopy(backend.ai_state_database) if kind=='aiPlans' else updated
    if kind=='aiPlans':state['savedPlans']=updated
    write_state(Path(path),state)
    if kind=='tasks':backend.local_database=updated;backend.tasksChanged.emit()
    elif kind=='flows':backend.groups_database=updated;backend.groupsChanged.emit()
    else:backend.ai_state_database=state;backend.aiLibraryChanged.emit()
    return kind+':'+uid
