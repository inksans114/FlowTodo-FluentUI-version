import unittest

from focus_rhythm import pomodoro_tasks


class PomodoroTests(unittest.TestCase):
    def test_alternates_and_finishes_on_work(self):
        tasks = pomodoro_tasks("写作", "写第一段", rounds=4)
        self.assertEqual([task["type"] for task in tasks], ["focus", "break"] * 3 + ["focus"])
        self.assertEqual(sum(task["time"] for task in tasks if task["type"] == "focus"), 100 * 60)
        self.assertEqual(sum(task["time"] for task in tasks if task["type"] == "break"), 15 * 60)
        self.assertEqual([task["round"] for task in tasks if task["type"] == "focus"], [1, 2, 3, 4])

    def test_long_break_after_four_rounds(self):
        tasks = pomodoro_tasks("写作", "第一段", work=15, short_break=3, long_break=10, rounds=5)
        self.assertEqual(tasks[7]["type"], "break")
        self.assertEqual(tasks[7]["time"], 600)
        self.assertEqual(tasks[-1]["round"], 5)

    def test_single_round_and_bounds(self):
        self.assertEqual(len(pomodoro_tasks("a", "b", rounds=1)), 1)
        self.assertEqual(pomodoro_tasks("a", "b", work=0, rounds=0)[0]["time"], 60)
        tasks = pomodoro_tasks("a", "b", work=1000, rounds=1000)
        self.assertEqual(len(tasks), 23)
        self.assertEqual(tasks[0]["time"], 180 * 60)

    def test_custom_long_break_interval(self):
        tasks = pomodoro_tasks("写作", "第一段", work=25, short_break=5, long_break=10, rounds=4, long_break_every=3)
        self.assertEqual([task["time"] for task in tasks], [1500, 300, 1500, 300, 1500, 600, 1500])


if __name__ == "__main__":
    unittest.main()
