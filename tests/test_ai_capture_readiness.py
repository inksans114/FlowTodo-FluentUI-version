import copy
import json
import unittest

from ai_library import remember, summaries
from ai_planning import AIOutputLimit, request_plan, system_prompt


class CaptureReadiness(unittest.TestCase):
    def setUp(self):
        self.messages = [{'role': 'system', 'content': system_prompt(capture=True)},
                         {'role': 'user', 'content': '明天一天做完物理3张卷子，想先做物理，按整张推进。'}]
        self.incomplete = {'tasks': [{'title': '完成物理3张卷子'}], 'summary': '已经记下，先做物理。'}
        self.ready = dict(self.incomplete, guidance={'goal': '完成物理3张卷子', 'intro': '先只看眼前这一张。',
                         'style': 'whole', 'steps': [{'title': '推进物理第一张', 'detail': '写确定的题，卡住的先标记。',
                                                    'minutes': 18, 'type': 'focus'}]})

    def request(self, replies):
        self.sent = []
        def call(messages, **kwargs):
            self.sent.append(messages)
            result = replies[len(self.sent) - 1]
            if isinstance(result, Exception):
                raise result
            return json.dumps(result, ensure_ascii=False)
        return request_plan(call, self.messages, json.loads, capture=True, require_progress=True)

    def test_task_only_response_is_completed_once_and_keeps_user_context(self):
        result = self.request([self.incomplete, self.ready])
        self.assertEqual(result['guidance']['steps'][0]['minutes'], 18)
        self.assertEqual(result['tasks'], self.incomplete['tasks'])
        self.assertEqual(len(self.sent), 2)
        self.assertIn(self.messages[-1], self.sent[-1])

    def test_missing_actions_fail_after_one_completion_attempt(self):
        with self.assertRaisesRegex(RuntimeError, '未返回可开始'):
            self.request([self.incomplete, self.incomplete])
        self.assertEqual(len(self.sent), 2)

    def test_ready_plan_or_questions_need_no_completion(self):
        for result in (self.ready, dict(self.incomplete, questions=[{'question': '想先做哪一张？', 'choices': []}])):
            self.request([result])
            self.assertEqual(len(self.sent), 1)

    def test_no_action_intent_stays_empty_without_inventing_focus(self):
        result = self.request([{'tasks': [], 'summary': '先休息，想做什么时再告诉我。'}])
        self.assertIsNone(result['guidance'])
        self.assertEqual(len(self.sent), 1)

    def test_complete_length_limited_json_still_needs_actions(self):
        first = AIOutputLimit('length', json.dumps(self.incomplete, ensure_ascii=False))
        result = self.request([first, self.ready])
        self.assertTrue(result['guidance'])
        self.assertEqual(len(self.sent), 2)

    def test_old_incomplete_plan_is_not_labelled_ready(self):
        state = {}
        remember(state, dict(copy.deepcopy(self.incomplete), captureMode=True))
        self.assertEqual(summaries(state)[0]['status'], 'incomplete')


if __name__ == '__main__':
    unittest.main()
