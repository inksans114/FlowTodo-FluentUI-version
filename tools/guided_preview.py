"""Real Qt/WebChannel guided journey QA using fake AI, isolated data and muted audio."""
from pathlib import Path
source=Path(__file__).with_name('studio_preview.py').read_text(encoding='utf-8')
exec(compile(source.split('\ntry:\n')[0],str(Path(__file__).with_name('studio_preview.py')),'exec'))
from guided_focus import validate_guidance

backend.settings_database['notificationSoundEnabled']=False
backend.settings_database['aiApiKey']='MOCK_ONLY'
backend.settings_database['focusMusicAutoPlay']=False
backend.local_database=[{'id':101,'title':'已有任务','done':False}]
backend.long_plan_database={'active':True,'pendingReview':False}
calls=[]
failed=False

def guidance(minutes=2,style='chunks'):
    return {'goal':'今天推进物理3张卷子、化学5面、英语3张，先不同时面对所有作业。',
        'intro':'这么多作业挤在一天，难开始很正常。已经准备好眼前这一段，先不用想着后面的。',
        'style':style,'breakMinutes':3,'restAfterMinutes':40,
        'steps':[{'title':'物理第一张，先做两道容易题' if style=='chunks' else '集中推进物理第一张卷子',
                  'detail':'自己读题，先写确定的部分。卡住的题可以标记，等状态好些再回头。',
                  'minutes':minutes,'type':'focus','encouragement':'这一步是你自己推进的，给这一小段努力一点掌声。'},
                 {'title':'再处理这一张的下一小部分','detail':'只看这张卷子，逐题推进，暂时不切换到其他科目。',
                  'minutes':7,'type':'focus','encouragement':'又推进了一段，可以按状态决定接下来怎么走。'}]}

def response(messages,long_mode=False):
    calls.append(messages)
    latest=next(m['content'] for m in reversed(messages) if m['role']=='user')
    if '进行中的专注引导' in latest:
        context=json.loads(latest.split('：',1)[1])
        if context.get('reportedProgress',{}).get('subject')=='英语':
            if not context.get('clarificationAnswers'):
                return json.dumps({'tasks':[],'summary':'收到，已经换到英语了。先确认现在手头的这一份。',
                    'questions':[{'question':'现在做的是哪张英语卷子？','field':'paper','choices':['第1张','第2张','第3张']},
                                 {'question':'现在在做哪一部分？','field':'section','choices':['选择题','大题']},
                                 {'question':'做到哪里了？','field':'position','choices':[]}]},ensure_ascii=False)
            value=guidance(19,'whole')
            value['steps']=[{'title':'英语第2张，推进眼前这道大题','detail':'先读清题干，写确定的部分。卡住时标记，不强行限成三道题。',
                             'minutes':19,'type':'focus','encouragement':'这道大题的推进也值得记录。'}]
            if context.get('clarificationSkipped'):
                value['steps'][0]['title']='英语，先读手头这道题'
            return json.dumps({'tasks':[],'guidance':value},ensure_ascii=False)
        return json.dumps({'tasks':[],'summary':'那就试试整块推进，卡住时再调整。','guidance':guidance(35,'whole')},ensure_ascii=False)
    if '用户补充回答' in latest:
        return json.dumps({'tasks':[{'title':'物理3张卷子'},{'title':'化学5面作业纸'},{'title':'英语3张卷子'}],
                           'summary':'先不同时面对所有作业。','guidance':guidance()},ensure_ascii=False)
    return json.dumps({'tasks':[],'summary':'这么多份作业挤在一天，烦躁是可以理解的。先确认适合你的安排。',
                      'questions':[{'question':'今天真正可用的时间大概还有多少？','choices':['约1小时','约3小时','不确定']},
                                   {'question':'更喜欢怎样推进？','choices':['拆小块，每次只看一点','围绕一张卷子整块做']} ]},ensure_ascii=False)
backend._call_ai_chat=response

def qml(item,code):
    expression=QQmlExpression(window.engine.rootContext(),item,code)
    expression.evaluate()
    assert not expression.hasError(),expression.error().toString()

def ai_render(name):
    root.setWidth(1180);root.setHeight(1100);root.showNormal();wait_ms(400)
    assert root.grabWindow().save(str(output/(name+'.png')))

try:
    backend._run_ai_plan_request(json.dumps({'captureMode':True,'messages':[{'role':'user','content':'物理3张卷子、化学5面、英语3张，今天想做完，好烦。我不知道怎么开始。'}]}))
    qml(root,"navigationView.push('"+QUrl.fromLocalFile(str(ROOT/'qml/pages/AiWorkspace.qml')).toString()+"')")
    wait_until(lambda:find(root.contentItem(),'captureOriginal') is not None,'AI editor missing')
    original=find(root.contentItem(),'captureOriginal');original.setProperty('text','物理3张卷子、化学5面、英语3张，今天想做完，好烦。我不知道怎么开始。')
    page=original.parentItem()
    while page.metaObject().indexOfProperty('questions')<0: page=page.parentItem()
    assert len(page.property('questions').toVariant())==2
    ai_render('guided-questions')
    qml(page,"setAnswer(0,'约3小时');setAnswer(1,'拆小块，每次只看一点');answer()")
    wait_until(lambda:page.property('guidance') is not None and page.property('guidance').toVariant() is not None,'Answered plan missing')
    assert not find(root.contentItem(),'captureSelect_0'),'Task list must be hidden by default'
    assert '拆小块' in calls[-1][-1]['content']
    assert backend.ai_state_database['latestPlan']['captureOriginal']==original.property('text')
    assert backend.ai_state_database['captureDraftInput']==original.property('text')
    assert '用户补充回答' not in backend.ai_state_database['latestPlan']['captureOriginal']
    ai_render('guided-ready')
    assert backend.startGuidedCapture()
    studio=backend._studio_window;view=studio
    wait_until(lambda:view.loaded,'Guided web scene missing')
    assert studio.isFullScreen()
    island=next(iter(backend.island_windows.values()))
    backend.exitFocusStudio()
    assert backend.returnToGuidedFocus()
    assert next(iter(backend.island_windows.values())) is island,'Returning must not start a new session'
    assert page.property('currentGuided') is not None
    assert island._total==120,'First duration must come from AI'
    wait_until(lambda:probe("document.body.classList.contains('guided')"),'Guided controls missing')
    assert '再处理这一张' not in probe("document.body.innerText"),'Future actions leaked into full screen'
    render('guided-current')
    island._deadline-=121;island._tick();backend._refresh_focus_snapshot();wait_ms(400)
    assert island.guided_waiting and island.current_index==0 and not island._timer.isActive()
    assert all(not task['done'] for task in backend.local_database)
    render('guided-boundary')
    js('runJavaScript("document.getElementById(\'finish\').click();document.getElementById(\'finish\').click()")')
    assert island.current_index==1 and not island.guided_waiting
    assert backend._guided_reward_seq==1
    assert probe("document.getElementById('reward-confetti').children.length")>0
    assert not studio.reward_sound.isPlaying(),'QA must stay muted'
    js('runJavaScript("document.getElementById(\'reward-sound\').click()")')
    assert not backend.settings_database['guidedRewardSound']
    island._deadline-=30
    js('runJavaScript("document.getElementById(\'guided-rest\').click()")')
    assert island._current_task()['type']=='break'
    focused_before_rest=island.focus_snapshot()['completedFocusSeconds']
    island._deadline-=181;island._tick();backend._refresh_focus_snapshot();wait_ms(250)
    assert island.guided_waiting and island.focus_snapshot()['completedFocusSeconds']==focused_before_rest
    js('runJavaScript("document.getElementById(\'finish\').click()")')
    assert island._current_task()['type']=='focus' and island._remaining<420,'Rest must preserve unfinished time'
    js('runJavaScript("document.getElementById(\'guided-adjust\').click()")')
    assert not island._timer.isActive(),'Thinking about feedback must not consume focus time'
    js('runJavaScript("document.getElementById(\'guided-feedback\').value=\'状态好一些了，我想改成整张卷子推进，不要拆碎。\';document.getElementById(\'guided-form\').requestSubmit()")')
    wait_until(lambda:not backend.aiRequestRunning and island._total==2100,'Whole-block adjustment failed')
    assert backend.focus_journey.active['source']['guidance']['style']=='whole'
    assert '整张卷子' in calls[-1][-1]['content']
    assert len(calls)==3,'Clock and ready steps must not repeatedly call AI'
    render('guided-whole')
    # Reminders are opt-in, based on the authoritative focus clock, and cost no API calls.
    backend.focusStudioAction('progress-check','10');wait_ms(150)
    island._deadline-=601;island._tick();backend._refresh_focus_snapshot();wait_ms(300)
    assert probe("document.getElementById('progress-dialog').open"),'Scheduled progress question missing'
    assert not island._timer.isActive(),'Reminder input must pause the focus clock'
    assert len(calls)==3
    render('guided-progress-reminder')
    js('runJavaScript("document.getElementById(\'progress-dismiss\').click()")')
    assert island._timer.isActive(),'Skipping reminder must resume the same step'
    backend._refresh_focus_snapshot();wait_ms(150)
    assert not probe("document.getElementById('progress-dialog').open"),'Reminder must not reopen every tick'
    backend.focusStudioAction('progress-check','0');wait_ms(150)
    js('runJavaScript("document.getElementById(\'guided-progress\').click()")')
    assert not island._timer.isActive() and len(calls)==3
    js('runJavaScript("document.getElementById(\'progress-subject\').value=\'英语\';document.getElementById(\'progress-note\').value=\'物理做完了，现在开始英语，不知道先做多少合适\';document.getElementById(\'progress-form\').requestSubmit()")')
    wait_until(lambda:bool(backend.focus_journey.active['source'].get('pendingClarification')),'Progress follow-up questions missing')
    wait_until(lambda:probe("!document.getElementById('progress-questions-form').hidden"),'Native questions popup missing')
    assert island.guided_waiting and not island._timer.isActive()
    assert backend.focus_journey.active['source']['reportedProgress']['subject']=='英语'
    assert len(calls)==4,'Opening questions must not poll AI'
    assert '第2张' in probe("document.getElementById('progress-questions').innerText")
    render('guided-progress-questions')
    clarification=backend.focus_journey.active['source']['pendingClarification']
    assert json.loads(backend.focus_journey.path.read_text(encoding='utf-8'))['active']['source']['pendingClarification']['id']==clarification['id']
    calls_before=len(calls)
    backend.guidedFocusAction('answers',json.dumps({'questionId':'stale','answers':['第2张','大题','第1道']}))
    assert len(calls)==calls_before,'Stale answers must not replan'
    js('runJavaScript("document.querySelectorAll(\'.progress-question\')[0].querySelectorAll(\'button\')[1].click();document.querySelectorAll(\'.progress-question\')[1].querySelectorAll(\'button\')[1].click();document.getElementById(\'progress-answer-2\').value=\'第1道大题，刚读完题干\';document.getElementById(\'progress-questions-form\').requestSubmit()")')
    wait_until(lambda:not backend.aiRequestRunning and island._total==19*60,'English big-question replan missing')
    assert island._current_task()['title']=='英语第2张，推进眼前这道大题'
    assert not backend.focus_journey.active['source'].get('pendingClarification')
    assert backend.focus_journey.active['source']['reportedProgress']['paper']=='第2张'
    assert backend.focus_journey.active['source']['reportedProgress']['section']=='大题'
    assert '第2张' in calls[-1][-1]['content'] and '大题' in calls[-1][-1]['content']
    assert len(calls)==5 and backend._guided_reward_seq==1,'Progress reports do not imply completion or rewards'
    render('guided-progress-english')
    island._deadline-=10;backend._refresh_focus_snapshot()
    expected=island.focus_snapshot()['completedFocusSeconds']
    stats_before=backend.stats_database.get('totalFocusSeconds',0)
    backend.guidedFocusAction('end','')
    assert not backend.active_focus_session
    assert abs(backend.stats_database['totalFocusSeconds']-stats_before-expected)<=1
    assert all(not task['done'] for task in backend.local_database)
    assert len(backend.local_database)==1,'Guided start must not fill the todo list'
    backend.exitFocusStudio();backend.saveStepReview('按实际进度记录','',False)
    # Whole-block users can start at 35 minutes; no five-minute warm-up is inserted.
    backend.ai_state_database['latestPlan']={'captureMode':True,'guidance':validate_guidance(guidance(35,'whole'))}
    assert backend.startGuidedCapture()
    island=next(iter(backend.island_windows.values()))
    assert island._total==2100
    backend.guidedFocusAction('progress',json.dumps({'subject':'英语','note':'换到英语，先不用给我排题号。'}))
    wait_until(lambda:bool(backend.focus_journey.active['source'].get('pendingClarification')),'Recovery questions missing')
    saved_question=backend.focus_journey.active['source']['pendingClarification']['id']
    assert backend.parkStepFocus('已经切到英语，等补充材料','继续补充当前进度')
    assert backend.returnToGuidedFocus()
    island=next(iter(backend.island_windows.values()))
    assert island.guided_waiting and backend.focus_journey.active['source']['pendingClarification']['id']==saved_question
    wait_until(lambda:probe("document.getElementById('progress-dialog').open"),'Questions must be available after recovery')
    js('runJavaScript("document.getElementById(\'progress-skip\').click()")')
    wait_until(lambda:not backend.aiRequestRunning and island._total==19*60,'Skipping questions did not prepare a safe action')
    assert island._current_task()['title']=='英语，先读手头这道题'
    assert json.loads(calls[-1][-1]['content'].split('：',1)[1])['clarificationSkipped']
    island._deadline-=19*60+1;island._tick();wait_ms(100)
    assert island.guided_waiting
    assert backend.parkStepFocus('这一段计时结束','继续准备下一段')
    assert backend.returnToGuidedFocus()
    restored=next(iter(backend.island_windows.values()))
    wait_ms(250)
    assert restored.guided_waiting and not restored._timer.isActive(),'Boundary must survive park/recovery'
    backend.guidedFocusAction('end','')
    backend.exitFocusStudio();backend.saveStepReview('完成这段投入','',False)
    assert backend.startPomodoroFocus(-1,1,1,2,2,'普通番茄钟保持原来的自动节奏',False)
    legacy=next(iter(backend.island_windows.values()))
    assert not legacy.options.get('guided')
    legacy._deadline-=61;legacy._tick();wait_ms(500)
    assert legacy.current_index==1 and legacy._current_task()['type']=='break'
    legacy._deadline-=61;legacy._tick();wait_ms(500)
    assert legacy.current_index==2 and legacy._current_task()['type']=='focus'
    backend.cancel_focus_session()
    errors=[item for item in warnings if any(word in item for word in ('TypeError','ReferenceError','Cannot assign','Binding loop','Error:'))]
    assert not errors,errors
    assert not studio.studio_page.console_errors,studio.studio_page.console_errors
    print(json.dumps({'ok':True,'requests':len(calls),'checks':['clarify only needed questions','answers inform plan','task list hidden','native fullscreen with current action only','AI durations 2 and 35 minutes','timer holds at boundary','explicit completion confetti','muted reward audio and toggle','break excluded from focus time','unfinished time survives rest','feedback replans whole blocks','no periodic AI polling','progress reminder pauses and skips without API','physics to English progress update','in-scene paper/section/position questions','stale answers rejected','confirmed progress persists','no automatic todo completion','actual focus time recorded','boundary survives resume'],'renders':str(output)},ensure_ascii=False),flush=True)
except BaseException:
    failed=True
    traceback.print_exc()
finally:
    faulthandler.cancel_dump_traceback_later()
    backend.shutdown()
    for item in app.topLevelWindows():item.hide()
    app.processEvents();DATA.cleanup()
    os._exit(1 if failed else 0)
