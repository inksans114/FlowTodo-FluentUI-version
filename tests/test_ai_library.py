import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ai_library import remember, snapshot, duplicate, find, migrate, summaries, write_state


def plan(title='物理作业'):
    return {'title':title,'captureMode':True,'captureOriginal':'3张物理卷子，先做选择题',
            'tasks':[{'title':title}], 'guidance':{'goal':title,'steps':[{'title':'先做两道题','minutes':3}]},'questions':[]}


class SavedPlans(unittest.TestCase):
    def test_interrupted_write_keeps_previous_data(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'state.json'
            write_state(path,{'savedPlans':['original']})
            with patch('ai_library.os.replace',side_effect=OSError('disk unavailable')):
                with self.assertRaises(OSError): write_state(path,{'savedPlans':['new']})
            self.assertEqual(json.loads(path.read_text(encoding='utf-8'))['savedPlans'],['original'])
            self.assertEqual(list(Path(directory).glob('*.tmp')),[])

    def test_new_results_do_not_replace_existing_plans(self):
        state={}
        first=remember(state,plan())
        second=remember(state,plan('英语作业'))
        self.assertNotEqual(first['id'],second['id'])
        self.assertEqual(first['plan']['tasks'][0]['title'],'物理作业')
        self.assertEqual(len(summaries(state)),2)

    def test_answers_update_the_same_saved_plan(self):
        state={};original=plan();original.update(guidance=None,questions=[{'question':'哪张？'}])
        saved=remember(state,original)
        ready=plan();ready.update(libraryId=saved['id'],capturePhase='answers',captureAnswers=[{'answer':'第2张'}])
        remember(state,ready)
        self.assertEqual(len(state['savedPlans']),1)
        self.assertEqual(saved['plan']['captureAnswers'][0]['answer'],'第2张')
        self.assertIsNone(saved['originalPlan']['guidance'])

    def test_continuations_do_not_replace_original_description_or_create_new_entry(self):
        state={};saved=remember(state,plan())
        update=plan('英语');update.update(libraryId=saved['id'],capturePhase='continue',captureOriginal='internal context')
        remember(state,update)
        self.assertEqual(len(state['savedPlans']),1)
        self.assertNotEqual(saved['plan']['captureOriginal'],'internal context')
        self.assertEqual(saved['plan']['title'],'物理作业')
        self.assertEqual(saved['lastResponse']['guidance']['goal'],'英语')

    def test_copies_have_independent_drafts_and_no_shared_timer(self):
        state={};saved=remember(state,plan())
        saved['journey']={'remainingSeconds':100}
        saved['draft']['drafts'][0]['_skip']=True
        copied=duplicate(state,saved['id'])
        copied['draft']['drafts'][0]['title']='副本修改'
        self.assertEqual(saved['draft']['drafts'][0]['title'],'物理作业')
        self.assertNotEqual(copied['id'],saved['id'])
        self.assertIsNone(copied['journey'])
        self.assertEqual(copied['copiedFrom'],saved['id'])

    def test_json_reload_retains_progress_pending_questions_and_editor_answers(self):
        state={};saved=remember(state,plan())
        saved['draft']['answerTexts']=['','我喜欢整块']
        journey={'id':'session','source':{'kind':'guided','libraryId':saved['id'],'pendingClarification':{'id':'q','questions':[{'question':'哪张？'}]}},
                 'status':'paused','index':2,'indexBase':1,'remainingSeconds':90,'elapsedSeconds':130,'step':'第2张','tasks':[{'time':30}]*3}
        self.assertTrue(snapshot(state,journey))
        journey['remainingSeconds']=0
        restored=json.loads(json.dumps(state))
        record=find(restored,saved['id'])
        self.assertEqual(record['journey']['remainingSeconds'],90)
        self.assertEqual(record['journey']['source']['pendingClarification']['id'],'q')
        self.assertEqual(record['draft']['answerTexts'][1],'我喜欢整块')
        self.assertTrue(summaries(restored)[0]['resumable'])

    def test_no_silent_history_limit(self):
        state={}
        for number in range(101): remember(state,plan(str(number)))
        self.assertEqual(len(summaries(state)),101)

    def test_old_result_files_migrate_once_and_skip_broken_or_internal_results(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);path=root/'ai-plan-20261006-120000.json'
            old=plan();path.write_text(json.dumps(old),encoding='utf-8')
            (root/'ai-plan-bad.json').write_text('{broken',encoding='utf-8')
            (root/'ai-plan-internal.json').write_text(json.dumps(dict(old,capturePhase='continue')),encoding='utf-8')
            state={'latestPlan':copy.deepcopy(old),'latestPath':str(path)}
            self.assertTrue(migrate(state,root))
            self.assertEqual(len(state['savedPlans']),1)
            self.assertEqual(state['selectedAiPlanId'],state['latestPlan']['libraryId'])
            self.assertFalse(migrate(state,root))
            self.assertEqual(len(state['savedPlans']),1)

    def test_plan_files_saved_in_the_same_second_are_unique(self):
        from main import BackendBridge
        with tempfile.TemporaryDirectory() as directory:
            class Fake:
                ai_plans_dir=directory
                _save_json=lambda self,path,value:Path(path).write_text(json.dumps(value),encoding='utf-8')
            backend=Fake()
            first=BackendBridge._save_ai_plan(backend,plan('一'))
            second=BackendBridge._save_ai_plan(backend,plan('二'))
            self.assertNotEqual(first,second)
            self.assertEqual(json.loads(Path(first).read_text(encoding='utf-8'))['title'],'一')


if __name__=='__main__': unittest.main()
