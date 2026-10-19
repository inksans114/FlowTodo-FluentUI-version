import unittest
from datetime import datetime
from ai_planning import bounded_messages, compact_context, validate_shape, system_prompt

class PlanningContracts(unittest.TestCase):
    def test_latest_correction_is_not_truncated(self):
        messages = [{'role': 'assistant', 'content': 'x' * 7900}, {'role': 'user', 'content': '明天交，不对，是下周二交报告。别加学习任务。'}]
        result = bounded_messages(messages, 100)
        self.assertEqual(result, messages[-1:])

    def test_oversized_latest_input_is_rejected_not_lost(self):
        with self.assertRaises(ValueError):
            bounded_messages([{'role':'user', 'content':'x' * 101}], 100)

    def test_context_has_anchor_and_no_music_path_or_key(self):
        text = compact_context([{'title':'报告','scheduledDate':'2026-10-07','done':False}], [], now=datetime(2026,10,6,10), preferences={'focusMusicPreference':'雨声','focusMusicPath':'SECRET_PATH','aiApiKey':'SECRET_KEY'})
        self.assertIn('2026-10-06T10:00', text)
        self.assertIn('雨声', text)
        self.assertNotIn('SECRET', text)

    def test_capture_cannot_create_project_or_mark_done(self):
        for plan in ({'tasks':[{'title':'写报告','done':True}]}, {'tasks':[], 'projects':[{'name':'大项目'}]}):
            with self.assertRaises(ValueError): validate_shape(plan, capture=True)

    def test_unrelated_json_is_not_treated_as_a_plan(self):
        with self.assertRaises(ValueError): validate_shape({'hello': 'world'})

    def test_empty_intent_is_valid(self):
        self.assertEqual(validate_shape({'tasks':[], 'summary':'先休息，想做什么时再记。'}, capture=True)['tasks'], [])

    def test_real_calendar_date_and_time_required(self):
        for date,time in [('2026-02-30',''), ('2026-10-07','25:00'), ('','12:00')]:
            with self.assertRaises(ValueError): validate_shape({'tasks':[{'title':'交报告','scheduledDate':date,'scheduledTime':time}]})
        validate_shape({'tasks':[{'title':'交报告','scheduledDate':'2026-10-07','scheduledTime':'14:00'}]})

    def test_compact_context_is_bounded(self):
        text = compact_context([{'title':'长标题' * 500, 'done':False} for _ in range(1000)], [])
        self.assertLess(len(text), 1800)

    def test_prompts_distinguish_capture_and_long_plans(self):
        self.assertIn('随口记录模式', system_prompt(capture=True))
        self.assertIn('longPlan=', system_prompt(long_mode=True))

if __name__ == '__main__': unittest.main()
