import io
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from ai_planning import AIOutputLimit, AIContextLimit, request_plan, system_prompt, validate_shape, compact_capture_input
from guided_focus import validate_guidance, island_tasks, continuation_context, validate_progress, validate_replies


def guide(minutes=2, style='chunks'):
    return {'goal':'今天推进物理3张、化学5面、英语3张，不保证一段时间做完全部。',
            'intro':'这么多作业挤在一天，烦是可以理解的。先只看眼前这一份。',
            'style':style,'breakMinutes':4,'restAfterMinutes':35,
            'steps':[{'title':'先做物理第一张的两道容易题' if style=='chunks' else '推进物理第一张卷子',
                      'detail':'先自己读题，卡住就标记，不需要现在解决整天的作业。',
                      'minutes':minutes,'type':'focus','encouragement':'这两题，就是实实在在的一步。'}]}


class GuidedContracts(unittest.TestCase):
    def test_progress_has_specific_material_section_and_position(self):
        report = validate_progress({'subject':'英语','paper':'第2张','section':'大题','position':'第1道还没做完','note':'物理已做完，现在换英语'})
        source={'guidance':guide(),'reportedProgress':report,'progressReports':[report]}
        context=continuation_context(source,{'title':'旧物理步骤'},{},'更新进度')
        self.assertEqual(context['reportedProgress']['section'],'大题')
        self.assertEqual(context['reportedProgress']['position'],'第1道还没做完')
        self.assertEqual(context['recentProgress'][0]['paper'],'第2张')
        self.assertNotIn('done',report)
        with self.assertRaises(ValueError): validate_progress({})
        with self.assertRaises(ValueError): validate_progress({'note':'a'*701})
        with self.assertRaises(ValueError): validate_progress({'paper':3})

    def test_progress_answers_preserve_question_order_and_allow_skip(self):
        questions=validate_shape({'tasks':[],'questions':[{'question':'哪张？','field':'paper'},{'question':'题型？','field':'section'}]},True)['questions']
        self.assertEqual(questions[0]['field'],'paper')
        self.assertEqual(validate_replies(['第2张','大题'],questions)[1],{'question':'题型？','answer':'大题'})
        self.assertEqual(validate_replies(['',''],questions)[0]['answer'],'')
        with self.assertRaises(ValueError): validate_replies(['第2张'],questions)
        with self.assertRaises(ValueError): validate_replies([True,'大题'],questions)

    def test_progress_context_keeps_latest_fact_and_bounds_old_reports(self):
        reports=[{'subject':'物理','note':'x'*700}]*20
        context=continuation_context({'reportedProgress':{'subject':'英语'},'progressReports':reports},{},{},'换科目')
        self.assertEqual(context['reportedProgress']['subject'],'英语')
        self.assertEqual(len(context['recentProgress']),3)
        self.assertEqual(len(context['recentProgress'][0]['note']),160)

    def test_long_input_processes_every_character_and_keeps_late_correction(self):
        original='我有好多作业。'*1000+'不要安排英语，不对，只剩最后一面英语。'
        segments=[]
        def fake(messages,long_mode=False):
            segment=json.loads(messages[-1]['content'])
            segments.append(segment['text'])
            return json.dumps({'facts':[segment['text'][-90:]],'uncertain':[]},ensure_ascii=False)
        compact=compact_capture_input(fake,original)
        self.assertEqual(''.join(segments),original)
        self.assertIn('只剩最后一面英语',compact)
        self.assertLess(len(compact),len(original))
        self.assertEqual(len(segments),4)

    def test_short_input_does_not_need_an_extra_request(self):
        self.assertEqual(compact_capture_input(lambda *a,**k:self.fail('unexpected request'),'周五交报告，不是明天'),'周五交报告，不是明天')
    def test_first_duration_is_ai_decision_not_five_minute_template(self):
        for minutes, style in ((2,'chunks'),(35,'whole'),(70,'whole')):
            result = validate_guidance(guide(minutes,style))
            self.assertEqual(island_tasks(result)[0]['time'],minutes*60)
            self.assertEqual(result['style'],style)

    def test_questions_or_ready_action_not_both(self):
        plan={'tasks':[],'questions':[{'question':'更喜欢怎么推进？','choices':['小块','整块']}],'guidance':None}
        self.assertEqual(validate_shape(plan,True)['questions'][0]['choices'],['小块','整块'])
        with self.assertRaises(ValueError): validate_shape(dict(plan,guidance=guide()),True)
        with self.assertRaises(ValueError): validate_shape(dict(plan,questions=plan['questions']*4),True)

    def test_rest_can_be_the_first_action_when_user_needs_buffer(self):
        value=guide();value['steps'][0].update(type='break',title='先把作业放下，喝口水')
        self.assertEqual(island_tasks(value)[0]['type'],'break')

    def test_bounded_steps_and_valid_clock(self):
        for minutes in (0,91,True,2.5):
            value=guide();value['steps'][0]['minutes']=minutes
            with self.assertRaises(ValueError): validate_guidance(value)
        value=guide();value['steps']*=4
        with self.assertRaises(ValueError): validate_guidance(value)

    def test_feedback_context_preserves_preference_and_actual_progress(self):
        context=continuation_context({'guidance':guide(35,'whole'),'captureAnswers':[{'answer':'整块推进'}],
                                     'captureTasks':[{'title':'物理3张卷子'}]},
                                     {'title':'第一张','subtitle':'自己读题'},
                                     {'taskSeconds':2100,'remaining':1800,'completedFocusSeconds':300},'还有两道，想休息')
        self.assertEqual(context['actualMinutes'],5)
        self.assertEqual(context['style'],'whole')
        self.assertIn('整块',context['answers'][0]['answer'])
        self.assertEqual(context['feedback'],'还有两道，想休息')

    def test_compact_retry_keeps_latest_correction_and_date_anchor(self):
        messages=[{'role':'system','content':system_prompt(capture=True)},
                  {'role':'system','content':'context={"now":"2026-10-06T13:00","existingTasks":["PRIVATE_BACKGROUND"]}'},
                  {'role':'assistant','content':'OLDER_HISTORY'},
                  {'role':'user','content':'今天做完，不对，周五交；化学5面，不是5张。我喜欢整块。'}]
        calls=[]
        def fake(sent,long_mode=False):
            calls.append(sent)
            if len(calls)==1: raise AIOutputLimit('length')
            return json.dumps({'tasks':[],'guidance':guide(35,'whole')},ensure_ascii=False)
        self.assertEqual(request_plan(fake,messages,json.loads,capture=True)['guidance']['style'],'whole')
        self.assertIn(messages[-1],calls[1])
        retry=json.dumps(calls[1],ensure_ascii=False)
        self.assertIn('2026-10-06',retry)
        self.assertNotIn('PRIVATE_BACKGROUND',retry)
        self.assertNotIn('OLDER_HISTORY',retry)

    def test_retries_are_bounded_and_invalid_tasks_not_imported(self):
        calls=[]
        def fail(*args,**kwargs): calls.append(1);raise AIContextLimit('limit')
        with self.assertRaisesRegex(RuntimeError,'原话已保留'):
            request_plan(fail,[{'role':'system','content':'rule'},{'role':'user','content':'full input'}],json.loads,capture=True)
        self.assertEqual(len(calls),2)
        with self.assertRaises(ValueError):
            request_plan(lambda *a,**kw:'{"tasks":[{"title":"卷子","done":true}]}',[],json.loads,capture=True)


class TransportContracts(unittest.TestCase):
    def setUp(self):
        from main import BackendBridge
        class FakeBridge:
            _call_ai_chat=BackendBridge._call_ai_chat
            _ai_request_temperature=BackendBridge._ai_request_temperature
            _ai_chat_endpoint=BackendBridge._ai_chat_endpoint
            _safe_int=BackendBridge._safe_int
            _safe_float=BackendBridge._safe_float
        self.backend=FakeBridge()
        self.backend.settings_database={'aiApiKey':'TEST_ONLY','aiShortOutputLimit':1024,'aiServiceOutputLimit':False}

    def test_configurable_budget_and_length_detection(self):
        def fake(request,timeout):
            self.assertEqual(json.loads(request.data)['max_tokens'],1024)
            return io.BytesIO(b'{"choices":[{"finish_reason":"length","message":{"content":"truncated"}}]}')
        with patch('urllib.request.urlopen',fake),self.assertRaises(AIOutputLimit):
            self.backend._call_ai_chat([])

    def test_content_filter_is_not_bypassed(self):
        with patch('urllib.request.urlopen',return_value=io.BytesIO(b'{"choices":[{"finish_reason":"content_filter"}]}')),self.assertRaisesRegex(RuntimeError,'拦截'):
            self.backend._call_ai_chat([])

    def test_context_limit_is_distinct_and_http_body_not_exposed(self):
        def limit(*args,**kwargs): raise HTTPError('https://example',400,'bad',{},io.BytesIO(b'{"error":{"code":"context_length_exceeded"}}'))
        with patch('urllib.request.urlopen',limit),self.assertRaises(AIContextLimit): self.backend._call_ai_chat([])
        def blocked(*args,**kwargs): raise HTTPError('https://example',403,'bad',{},io.BytesIO(b'SECRET_PROVIDER_BODY'))
        with patch('urllib.request.urlopen',blocked),self.assertRaises(RuntimeError) as result: self.backend._call_ai_chat([])
        self.assertNotIn('SECRET',str(result.exception))


if __name__=='__main__':unittest.main()
