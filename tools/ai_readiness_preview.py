"""Offline regression for new ideas, task-only replies and real fullscreen launch."""
from pathlib import Path
source = Path(__file__).with_name('guided_preview.py').read_text(encoding='utf-8')
exec(compile(source.split('\ntry:\n')[0], str(Path(__file__).with_name('guided_preview.py')), 'exec'))
import copy
from ai_library import remember, find as saved_record

failed = True
try:
    backend.setSetting('aiApiKey', 'MOCK_ONLY')
    backend.setSetting('notificationSoundEnabled', False)
    backend.setSetting('focusMusicAutoPlay', False)
    assert backend.aiServiceReady and backend.getSetting('aiApiKey', '') == '', 'Default key must stay hidden while service remains ready'
    replies = []
    def fake(messages, **kwargs):
        calls.append(messages)
        return json.dumps(replies.pop(0), ensure_ascii=False)
    backend._call_ai_chat = fake
    # Ensure retry transport is also isolated from paid providers.
    qml(root, "navigationView.push('" + QUrl.fromLocalFile(str(ROOT/'qml/pages/AiWorkspace.qml')).toString() + "')")
    wait_until(lambda:find(root.contentItem(), 'captureOriginal') is not None, 'Editor missing')
    original = find(root.contentItem(), 'captureOriginal')
    page = original
    while page.metaObject().indexOfProperty('savedId') < 0:
        page = page.parentItem()
    initial_tasks = copy.deepcopy(backend.local_database)
    ids = []
    for index, minutes in enumerate((7, 18)):
        qml(page, 'newCapture()')
        assert not page.property('currentGuided'), 'A new idea must not display another plan\'s journey'
        text = f'第{index+1}个想法：物理三张，明天做，先整张推进。'
        original.setProperty('text', text)
        assert find(root.contentItem(), 'capturePrepare').property('enabled'), 'Real user must be able to generate'
        task_only = {'tasks': [{'title': '完成物理三张'}], 'summary': '收到，已经记下。'}
        ready = dict(task_only, guidance=guidance(minutes, 'whole'))
        replies.extend([task_only, ready])
        qml(find(root.contentItem(), 'capturePrepare'), 'clicked()')
        wait_until(lambda:not backend.aiRequestRunning and not page.property('waiting'), 'New idea request stuck')
        assert page.property('guidance').toVariant()['steps'][0]['minutes'] == minutes
        start = find(root.contentItem(), 'captureGuidedStart')
        assert start.property('visible') and start.property('enabled'), 'Ready start action missing'
        ids.append(page.property('savedId'))
        assert json.loads(backend.getSelectedAiCapture())['id'] == ids[-1]
        ai_render('ai-readiness-ready')
        qml(start, 'clicked()')
        wait_until(lambda:backend._studio_window and backend._studio_window.loaded, 'Fullscreen did not load')
        assert backend._studio_window.isFullScreen()
        island = next(iter(backend.island_windows.values()))
        assert island._total == minutes * 60, 'Must use AI duration, not a fixed template'
        assert backend.parkStepFocus('先暂停', '继续当前这一张')
    assert ids[0] != ids[1] and len(backend.ai_state_database['savedPlans']) == 2
    assert len(calls) == 4
    assert backend.local_database == initial_tasks, 'Preparing and focusing must not silently import tasks'
    # Old imported/edited drafts can be empty even though the saved plan has tasks.
    legacy = dict(task_only, captureMode=True, captureOriginal='化学四张，明天做完', capturePhase='answers',
                  captureAnswers=[{'question': '怎样推进？', 'answer': '整张'}])
    with backend._ai_state_lock:
        record = remember(backend.ai_state_database, legacy)
        record['draft']['drafts'] = []
        backend._save_ai_state()
    legacy_id = record['id']
    assert backend.openSavedAiPlan(legacy_id)
    wait_ms(100)
    assert page.property('needsGuidance')
    recover = find(root.contentItem(), 'capturePrepareGuidance')
    ai_render('ai-readiness-recover')
    assert recover.property('visible') and recover.property('enabled'), {
        'visible': recover.property('visible'), 'enabled': recover.property('enabled'),
        'changed': page.property('originalChanged'), 'running': backend.aiRequestRunning,
        'guided': bool(page.property('currentGuided')), 'service': page.property('serviceReady')}
    replies.append(dict(task_only, guidance=guidance(12, 'whole')))
    qml(recover, 'clicked()')
    wait_until(lambda:not backend.aiRequestRunning and not page.property('waiting'), 'Legacy recovery stuck')
    assert page.property('savedId') == legacy_id
    assert len(backend.ai_state_database['savedPlans']) == 3
    assert saved_record(backend.ai_state_database, legacy_id)['plan']['captureAnswers'] == legacy['captureAnswers']
    assert '整张' in calls[-1][-1]['content']
    assert find(root.contentItem(), 'captureGuidedStart').property('enabled')
    # Still-invalid output must preserve the previous saved result and original input.
    before = copy.deepcopy(saved_record(backend.ai_state_database, legacy_id)['plan'])
    replies.extend([task_only, task_only])
    backend.prepareSavedAiCapture(legacy_id)
    wait_until(lambda:not backend.aiRequestRunning, 'Failed completion did not stop')
    assert saved_record(backend.ai_state_database, legacy_id)['plan'] == before
    assert original.property('text') == legacy['captureOriginal']
    assert backend.local_database == initial_tasks
    errors = [w for w in warnings if any(x in w for x in ('TypeError', 'ReferenceError', 'Cannot assign', 'Binding loop', 'Error:'))]
    assert not errors, errors
    print(json.dumps({'ok': True, 'checks': ['two fresh ideas auto-complete missing actions', 'ready button enabled',
        'real fullscreen starts with AI duration', 'independent saved plans', 'empty legacy draft can recover',
        'existing answers retained', 'bounded failure keeps old plan', 'no task import or paid API'], 'calls': len(calls)}, ensure_ascii=False), flush=True)
    failed = False
except BaseException:
    traceback.print_exc()
finally:
    faulthandler.cancel_dump_traceback_later()
    backend.shutdown()
    for item in app.topLevelWindows(): item.hide()
    app.processEvents()
    DATA.cleanup()
    os._exit(1 if failed else 0)
