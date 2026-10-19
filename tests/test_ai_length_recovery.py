"""Provider simulations: no live API calls, keys or user files."""
import io
import json
import unittest
from unittest.mock import patch

from ai_planning import AIContextLimit, AIOutputLimit, request_plan, system_prompt, validate_shape


class LengthRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.messages = [
            {'role': 'system', 'content': system_prompt(capture=True, capture_phase='answers')},
            {'role': 'system', 'content': 'context={"now":"2026-10-06T14:00","preferences":{"music":"安静"},"existingTasks":["OLD_BACKGROUND"]}'},
            {'role': 'user', 'content': '周五交，不是今天；化学5面，不是5张。按整块推进。保留物理、化学、英语的全部作业。'}]
        self.plan = {'tasks': [{'title': f'完成第{i}项作业', 'meta': '周五交，不是今天'} for i in range(75)],
                     'summary': '保留全部作业，按你选择的整块方式推进。', 'questions': [], 'guidance': None}

    def test_many_tasks_are_retained_including_capture(self):
        for capture in (False, True):
            self.assertEqual(len(validate_shape(self.plan.copy(), capture)['tasks']), 75)

    def test_full_json_with_length_flag_needs_no_retry(self):
        calls = []
        def call(*args, **kwargs):
            calls.append(1)
            raise AIOutputLimit('length', json.dumps(self.plan, ensure_ascii=False), 1800)
        result = request_plan(call, self.messages, json.loads, capture=True)
        self.assertEqual(len(result['tasks']), 75)
        self.assertEqual(len(calls), 1)

    def test_three_pieces_recover_every_task_without_rewriting(self):
        full = json.dumps(self.plan, ensure_ascii=False, separators=(',', ':'))
        chunks = [full[:165], full[165:2067], full[2067:]]
        calls = []
        def call(sent, long_mode=False):
            index = len(calls)
            calls.append(sent)
            if index < 2:
                raise AIOutputLimit('length', chunks[index])
            return chunks[index]
        result = request_plan(call, self.messages, json.loads, capture=True)
        self.assertEqual(result['tasks'], self.plan['tasks'])
        self.assertEqual(len(calls), 3)
        for index in (1, 2):
            self.assertEqual(calls[index][-2]['content'], ''.join(chunks[:index]))
            self.assertIn(self.messages[-1], calls[index])

    def test_split_inside_an_escape_is_joined_exactly(self):
        plan = {'tasks': [{'title': '整理资料', 'meta': '目录 C:\\资料，标记“待交”'}]}
        full = json.dumps(plan, ensure_ascii=False)
        cut = full.index('\\\\') + 1
        calls = []
        def call(*args, **kwargs):
            calls.append(1)
            if len(calls) == 1:
                raise AIOutputLimit('length', full[:cut])
            return full[cut:]
        self.assertEqual(request_plan(call, self.messages, json.loads)['tasks'], plan['tasks'])

    def test_truncated_outer_document_is_not_accepted_as_nested_plan(self):
        calls = []
        fragment = '{"unfinished": {"tasks": [{"title": "部分任务"}]}, "remaining": ['
        def call(*args, **kwargs):
            calls.append(1)
            raise AIOutputLimit('length', fragment if len(calls) == 1 else ' ')
        with self.assertRaisesRegex(RuntimeError, '自动续写已停止'):
            request_plan(call, self.messages, lambda text: {'tasks': [{'title': '错误导入'}]})
        self.assertEqual(len(calls), 4)

    def test_budget_adjustment_callback_and_no_reduction_in_count(self):
        sent = []
        def initial(*args, **kwargs):
            raise AIOutputLimit('length', output_budget=1024)
        def recover(messages, long_mode=False, failure=None):
            sent.extend(messages)
            self.assertEqual(failure.output_budget, 1024)
            return json.dumps(self.plan, ensure_ascii=False)
        result = request_plan(initial, self.messages, json.loads, capture=True, retry_call=recover)
        self.assertEqual(len(result['tasks']), 75)
        self.assertIn(self.messages[-1], sent)
        text = json.dumps(sent, ensure_ascii=False)
        self.assertNotIn('OLD_BACKGROUND', text)
        self.assertNotIn('至多4项', text)
        self.assertIn('2026-10-06', text)
        self.assertIn('不重复询问', text)

    def test_distinct_context_and_output_failures_and_bounded_requests(self):
        for error, expected in ((AIContextLimit('context'), '输入上下文'),
                                (AIOutputLimit('length'), '提高输出预算')):
            calls = []
            def call(*args, **kwargs):
                calls.append(1)
                raise error
            with self.assertRaisesRegex(RuntimeError, expected) as raised:
                request_plan(call, self.messages, json.loads, capture=True)
            self.assertIn('原话已保留', str(raised.exception))
            self.assertEqual(len(calls), 2)

    def test_content_filter_during_continuation_stops_immediately(self):
        calls = []
        def call(*args, **kwargs):
            calls.append(1)
            if len(calls) == 1:
                raise AIOutputLimit('length', '{"tasks":[')
            raise RuntimeError('服务拦截了这次回复')
        with self.assertRaisesRegex(RuntimeError, '拦截'):
            request_plan(call, self.messages, json.loads, capture=True)
        self.assertEqual(len(calls), 2)

    def test_context_recovery_keeps_earlier_tasks_and_stays_compact_when_continuing(self):
        messages = self.messages[:-1] + [
            {'role': 'user', 'content': '先前的事项：物理三张，化学五面，英语三张'},
            {'role': 'assistant', 'content': 'OLD_DIALOGUE'}, self.messages[-1]]
        full = json.dumps(self.plan, ensure_ascii=False)
        calls = []
        def call(sent, long_mode=False):
            index = len(calls)
            calls.append(sent)
            if index == 0:
                raise AIContextLimit('context')
            if index == 1:
                raise AIOutputLimit('length', full[:900])
            return full[900:]
        result = request_plan(call, messages, json.loads, capture=True)
        self.assertEqual(len(result['tasks']), 75)
        for sent in calls[1:]:
            text = json.dumps(sent, ensure_ascii=False)
            self.assertIn('先前的事项', text)
            self.assertNotIn('OLD_BACKGROUND', text)
            self.assertNotIn('OLD_DIALOGUE', text)

    def test_complete_but_invalid_task_is_still_rejected(self):
        def call(*args, **kwargs):
            raise AIOutputLimit('length', '{"tasks":[{"title":"作业","done":true}]}')
        with self.assertRaises(ValueError):
            request_plan(call, self.messages, json.loads, capture=True)


class OutputBudgetTests(unittest.TestCase):
    def setUp(self):
        from main import BackendBridge
        class FakeBridge:
            _call_ai_chat = BackendBridge._call_ai_chat
            _retry_ai_chat = BackendBridge._retry_ai_chat
            _ai_request_temperature = BackendBridge._ai_request_temperature
            _ai_chat_endpoint = BackendBridge._ai_chat_endpoint
            _safe_int = BackendBridge._safe_int
            _safe_float = BackendBridge._safe_float
        self.backend = FakeBridge()
        self.backend.settings_database = {'aiApiKey': 'TEST_ONLY', 'aiShortOutputLimit': 1800}
        self.payloads = []

    def response(self, request, timeout):
        self.payloads.append(json.loads(request.data))
        return io.BytesIO(b'{"choices":[{"finish_reason":"stop","message":{"content":"{\\"tasks\\":[]}"}}]}')

    def test_default_mode_omits_limit_even_with_old_budget_saved(self):
        with patch('urllib.request.urlopen', self.response):
            self.backend._call_ai_chat([])
        self.assertNotIn('max_tokens', self.payloads[0])

    def test_manual_large_budget_is_not_clamped_to_8192(self):
        self.backend.settings_database.update(aiServiceOutputLimit=False, aiShortOutputLimit=32768)
        with patch('urllib.request.urlopen', self.response):
            self.backend._call_ai_chat([])
        self.assertEqual(self.payloads[0]['max_tokens'], 32768)

    def test_recovery_increases_manual_budget_without_saving_it(self):
        self.backend.settings_database['aiServiceOutputLimit'] = False
        before = dict(self.backend.settings_database)
        with patch('urllib.request.urlopen', self.response):
            self.backend._retry_ai_chat([], failure=AIOutputLimit('length', output_budget=1800))
        self.assertEqual(self.payloads[0]['max_tokens'], 3600)
        self.assertEqual(self.backend.settings_database, before)

    def test_length_failure_preserves_partial_content_and_actual_budget(self):
        self.backend.settings_database['aiServiceOutputLimit'] = False
        value = {'choices': [{'finish_reason': 'length', 'message': {'content': '{"tasks":['}}]}
        with patch('urllib.request.urlopen', return_value=io.BytesIO(json.dumps(value).encode())), self.assertRaises(AIOutputLimit) as raised:
            self.backend._call_ai_chat([])
        self.assertEqual(raised.exception.content, '{"tasks":[')
        self.assertEqual(raised.exception.output_budget, 1800)

    def test_real_transport_continuation_keeps_long_plan_complete(self):
        plan = {'tasks': [{'title': f'处理事项{i}'} for i in range(75)]}
        full = json.dumps(plan, ensure_ascii=False)
        parts = [full[:357], full[357:]]
        def respond(request, timeout):
            self.payloads.append(json.loads(request.data))
            index = len(self.payloads) - 1
            result = {'choices': [{'finish_reason': 'length' if index == 0 else 'stop',
                                   'message': {'content': parts[index]}}]}
            return io.BytesIO(json.dumps(result, ensure_ascii=False).encode('utf-8'))
        messages = [{'role': 'system', 'content': system_prompt()},
                    {'role': 'user', 'content': '保留我说的所有75项事项'}]
        with patch('urllib.request.urlopen', respond):
            result = request_plan(self.backend._call_ai_chat, messages, json.loads,
                                  retry_call=self.backend._retry_ai_chat)
        self.assertEqual(result['tasks'], plan['tasks'])
        self.assertEqual(len(self.payloads), 2)
        self.assertTrue(all('max_tokens' not in payload for payload in self.payloads))


if __name__ == '__main__':
    unittest.main()
