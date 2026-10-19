"""Saved-plan UI/restart/resume QA with isolated data and a fake model."""
from pathlib import Path
source=Path(__file__).with_name('guided_preview.py').read_text(encoding='utf-8')
exec(compile(source.split('\ntry:\n')[0],str(Path(__file__).with_name('guided_preview.py')),'exec'))
from PySide6.QtQml import QQmlComponent
from ai_library import find as saved_record

created=[]
restarted=None


def fresh_capture():
    component=QQmlComponent(window.engine,QUrl.fromLocalFile(str(ROOT/'qml/pages/AiGuidedCapture.qml')))
    page=component.create()
    assert page is not None,[error.toString() for error in component.errors()]
    page.setParent(root)
    created.append(page)
    return page


def destroy_capture(page):
    page.deleteLater();wait_ms(150)
    created.remove(page)


try:
    backend._run_ai_plan_request(json.dumps({'captureMode':True,'messages':[{'role':'user','content':'物理3张卷子、化学5面、英语3张，今天想做完，好烦。'}]}))
    wait_ms(200)
    first_id=backend.ai_state_database['latestPlan']['libraryId']
    first=fresh_capture()
    qml(first,"setAnswer(1,'拆小块，每次只看一点')")
    destroy_capture(first)
    assert saved_record(backend.ai_state_database,first_id)['draft']['answerTexts']==['','拆小块，每次只看一点']
    first=fresh_capture()
    assert first.property('answerTexts').toVariant()[1]=='拆小块，每次只看一点','Unsubmitted answers must survive page recreation'
    qml(first,"answer()")
    wait_until(lambda:not backend.aiRequestRunning,'Answered plan missing')
    assert len(backend.ai_state_database['savedPlans'])==1,'Answering should update its original plan'
    assert first.property('guidance').toVariant() is not None
    qml(first,"showDrafts=true;var items=drafts.slice();items[0]=Object.assign({},items[0],{title:'物理第一张 · 修改后'});items[1]=Object.assign({},items[1],{_skip:true});drafts=items")
    destroy_capture(first)
    first=fresh_capture()
    drafts=first.property('drafts').toVariant()
    assert drafts[0]['title']=='物理第一张 · 修改后' and drafts[1]['_skip']
    assert first.property('showDrafts')
    destroy_capture(first)
    backend._run_ai_plan_request(json.dumps({'captureMode':True,'messages':[{'role':'user','content':'周末准备英语演讲，先整理主题'}]}))
    wait_ms(150)
    second_id=backend.ai_state_database['latestPlan']['libraryId']
    assert first_id!=second_id and len(backend.ai_state_database['savedPlans'])==2
    assert saved_record(backend.ai_state_database,first_id)['draft']['drafts'][0]['title']=='物理第一张 · 修改后'
    before_calls=len(calls)
    assert backend.openSavedAiPlan(first_id)
    copied_id=backend.copySavedAiPlan(first_id)
    assert copied_id and copied_id!=first_id
    copied=fresh_capture()
    qml(copied,"var items=drafts.slice();items[0]=Object.assign({},items[0],{title:'副本独立修改'});drafts=items;persistDraft()")
    assert saved_record(backend.ai_state_database,first_id)['draft']['drafts'][0]['title']=='物理第一张 · 修改后'
    assert saved_record(backend.ai_state_database,copied_id)['draft']['drafts'][0]['title']=='副本独立修改'
    destroy_capture(copied)
    assert len(calls)==before_calls,'Opening and copying must not call AI'
    backend.clearAiMessages()
    assert len(backend.ai_state_database['savedPlans'])==3
    assert backend.startGuidedCapture(first_id)
    studio=backend._studio_window;view=studio
    wait_until(lambda:view.loaded,'Saved guide scene missing')
    island=next(iter(backend.island_windows.values()))
    island._deadline-=121;island._tick();wait_ms(150)
    backend.guidedFocusAction('next','')
    assert island.current_index==1
    island._deadline-=15;island._tick();backend._refresh_focus_snapshot()
    step=island._current_task()['title'];remaining=island._remaining
    assert backend.parkStepFocus('第一段结束，第二段写了一点','接着第二段')
    assert saved_record(backend.ai_state_database,first_id)['journey']['index']==1
    assert backend.startGuidedCapture(copied_id)
    copy_island=next(iter(backend.island_windows.values()))
    copy_island._deadline-=7;copy_island._tick()
    assert backend.parkStepFocus('副本也推进了一点','稍后继续副本')
    stats_before=backend.stats_database.get('totalFocusSeconds',0)
    assert backend.continueSavedAiPlan(first_id)
    restored=next(iter(backend.island_windows.values()))
    assert restored._current_task()['title']==step and abs(restored._remaining-remaining)<=2
    assert backend.focus_journey.active['index']==1
    assert len(backend.focus_journey.active['tasks'])==2,'The saved absolute index needs its completed task prefix'
    assert backend.stats_database.get('totalFocusSeconds',0)==stats_before,'Loading must not count old time again'
    restored._deadline-=10;restored._tick()
    assert backend.parkStepFocus('第二段又推进了一点','继续第二段')
    assert backend.continueSavedAiPlan(first_id),'A second restore must still have the correct task index'
    again=next(iter(backend.island_windows.values()))
    assert again._current_task()['title']==step and again._remaining<remaining
    assert len(calls)==before_calls,'Resume must use local progress without an AI request'
    assert backend.parkStepFocus('留到下次继续','接着第二段')
    qml(root,"navigationView.push('"+QUrl.fromLocalFile(str(ROOT/'qml/pages/AiSavedPlans.qml')).toString()+"')")
    wait_until(lambda:find(root.contentItem(),'savedPlansSearch') is not None,'Library page missing')
    ai_render('ai-saved-plans')
    search=find(root.contentItem(),'savedPlansSearch')
    qml(search,"text='副本';textEdited()")
    wait_ms(100)
    library=search.parentItem()
    while library.metaObject().indexOfProperty('records')<0: library=library.parentItem()
    assert len(library.property('filtered').toVariant())==1
    backend.shutdown()
    restarted=type(backend)()
    assert len(json.loads(restarted.savedAiPlansJson))==3
    restored_record=json.loads(restarted.getSavedAiPlan(first_id))
    assert restored_record['draft']['drafts'][0]['title']=='物理第一张 · 修改后'
    assert restored_record['journey']['remainingSeconds']>0 and restored_record['journey']['index']==1
    assert restarted.focus_journey.active['source']['libraryId']==first_id
    assert restarted.focus_journey.active['status']=='paused'
    assert len(calls)==before_calls
    errors=[item for item in warnings if any(word in item for word in ('TypeError','ReferenceError','Cannot assign','Binding loop','Error:'))]
    assert not errors,errors
    print(json.dumps({'ok':True,'checks':['unsubmitted answers survive recreation','task edits and selection retained','new plans keep old plans','independent copy drafts','open/copy/resume make no AI calls','clearing chat retains saved plans','multiple paused plans','resume second step with remaining time','repeated resume preserves absolute index','no duplicate focus statistics','saved-plan search','new backend restores disk state'],'plans':3,'requests':len(calls),'renders':str(output)},ensure_ascii=False),flush=True)
except BaseException:
    failed=True
    traceback.print_exc()
finally:
    faulthandler.cancel_dump_traceback_later()
    if restarted: restarted.shutdown()
    backend.shutdown()
    for page in created: page.deleteLater()
    for item in app.topLevelWindows():item.hide()
    app.processEvents();DATA.cleanup()
    os._exit(1 if failed else 0)
