import json
import unittest

from quick_capture import ai_tasks, local_tasks, validate_tasks
from ai_planning import AIOutputLimit


class QuickCaptureTests(unittest.TestCase):
    def test_local_multiple_tasks_preserve_commas_and_duplicate_intentions(self):
        tasks = local_tasks("买猫粮；交报告。联系同学,确认时间\n喝水\n喝水")
        self.assertEqual([item["title"] for item in tasks], ["买猫粮", "交报告", "联系同学,确认时间", "喝水", "喝水"])

    def test_invalid_batch_is_rejected_entirely(self):
        with self.assertRaises(ValueError):
            validate_tasks([{"title": "有效任务"}, {"title": ""}])
        with self.assertRaises(ValueError):
            local_tasks("x" * 6001)

    def test_ai_only_sends_current_input_and_small_budget_once(self):
        calls = []
        def call(messages, **options):
            calls.append((messages, options))
            return json.dumps({"tasks": [{"title": "交报告", "category": "工作"}, {"title": "买猫粮", "category": "生活"}]})
        self.assertEqual(len(ai_tasks(call, "交报告，还要买猫粮")), 2)
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(calls[0][0]), 2)
        self.assertEqual(calls[0][0][-1]["content"], "交报告，还要买猫粮")
        self.assertEqual(calls[0][1]["output_limit"], 1600)
        self.assertLess(len(calls[0][0][0]["content"]), 300)

    def test_truncated_ai_is_not_silently_imported_or_retried(self):
        calls = []
        def call(*args, **kwargs):
            calls.append(1)
            raise AIOutputLimit("length", '{"tasks":[{"title":"部分任务"}')
        with self.assertRaises(AIOutputLimit):
            ai_tasks(call, "物理、化学、英语作业")
        self.assertEqual(len(calls), 1)

    def test_planning_payload_is_rejected_in_quick_entry(self):
        with self.assertRaises(ValueError):
            ai_tasks(lambda *a, **kw: '{"tasks":[],"guidance":{}}', "买猫粮")


if __name__ == "__main__":
    unittest.main()
