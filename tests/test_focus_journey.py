from __future__ import annotations

import tempfile
import json
import unittest
from pathlib import Path

from focus_journey import FocusJourney


class FocusJourneyTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "focus_journey.json"
        self.journal = FocusJourney(self.path)
        self.session = {"title": "论文", "taskId": 7, "totalSeconds": 900, "mode": "single"}
        self.tasks = [{"title": "论文", "time": 900, "type": "focus"}]
        self.journal.begin(self.session, self.tasks, "整理三个观点")

    def test_restart_recovers_a_frozen_return_point(self):
        self.journal.snapshot({"remaining": 733, "completedFocusSeconds": 167})
        self.journal.bookmark("读到第三节", "整理第二个观点")
        recovered = FocusJourney(self.path)
        self.assertEqual(recovered.active["status"], "paused")
        self.assertEqual(recovered.active["remainingSeconds"], 733)
        self.assertEqual(recovered.active["elapsedSeconds"], 167)
        self.assertEqual(recovered.active["nextAction"], "整理第二个观点")

    def test_resumed_segments_preserve_elapsed_and_one_step_identity(self):
        self.journal.snapshot({"remaining": 733, "completedFocusSeconds": 167, "event": "paused"})
        step_id = self.journal.active["id"]
        self.journal.begin(self.session, self.tasks, preserve=True)
        self.journal.snapshot({"remaining": 700, "completedFocusSeconds": 33})
        self.assertEqual(self.journal.active["elapsedSeconds"], 200)
        self.assertEqual(self.journal.active["id"], step_id)

    def test_minimizing_a_paused_island_does_not_restart_the_clock(self):
        self.journal.snapshot({"event": "paused", "remaining": 800, "completedFocusSeconds": 100})
        self.journal.snapshot({"event": "mini", "running": False, "remaining": 800})
        self.assertEqual(self.journal.active["status"], "paused")
        self.assertEqual(self.journal.active["elapsedSeconds"], 100)

    def test_timer_expiration_requires_review_and_explicit_task_completion(self):
        self.journal.review({"remaining": 0, "completedFocusSeconds": 900}, "timer")
        self.assertEqual(self.journal.active["status"], "review")
        self.assertEqual(self.journal.data["history"], [])
        record = self.journal.finish("整理了三个观点", "写第一段")
        self.assertFalse(record["taskDone"])
        self.assertEqual(self.journal.data["checkpoint"]["step"], "写第一段")
        self.assertIsNone(self.journal.finish("duplicate", ""))
        self.assertEqual(len(self.journal.data["history"]), 1)

    def test_thoughts_survive_completion_and_restart(self):
        self.assertFalse(self.journal.capture("   "))
        self.assertTrue(self.journal.capture("晚上买东西"))
        thought = self.journal.data["thoughts"][0]
        self.assertEqual(thought["stepId"], self.journal.active["id"])
        self.journal.review({"remaining": 800, "completedFocusSeconds": 100})
        self.journal.finish("有了进展", "")
        recovered = FocusJourney(self.path)
        self.assertEqual(recovered.data["thoughts"][0]["text"], "晚上买东西")
        self.assertTrue(recovered.resolve(thought["id"]))
        self.assertTrue(FocusJourney(self.path).data["thoughts"][0]["resolved"])

    def test_multiple_restarts_keep_the_absolute_flow_index(self):
        self.journal.snapshot({"index": 1, "remaining": 300, "completedFocusSeconds": 600})
        self.journal.begin(self.session, self.tasks, preserve=True)
        self.journal.snapshot({"index": 1, "remaining": 100, "completedFocusSeconds": 200})
        self.assertEqual(self.journal.active["index"], 2)
        self.journal.begin(self.session, self.tasks, preserve=True)
        self.journal.snapshot({"index": 0, "remaining": 80, "completedFocusSeconds": 20})
        self.assertEqual(self.journal.active["index"], 2)
        self.assertEqual(self.journal.active["elapsedSeconds"], 820)

    def test_reset_removes_journey_data(self):
        self.journal.capture("待处理")
        self.journal.clear()
        recovered = FocusJourney(self.path)
        self.assertIsNone(recovered.active)
        self.assertEqual(recovered.data["thoughts"], [])
        self.assertEqual(recovered.data["forest"], [])

    def test_tree_is_saved_at_completion_before_review_and_only_once(self):
        self.journal.review({"remaining": 0, "completedFocusSeconds": 900}, "timer")
        tree = self.journal.data["forest"][0]
        self.assertEqual(tree["id"], self.journal.active["id"])
        self.assertEqual(tree["seconds"], 900)
        self.assertEqual(FocusJourney(self.path).data["forest"], [tree])
        self.journal.review({}, "timer")
        self.journal.finish("完成", "")
        self.assertEqual(FocusJourney(self.path).data["forest"], [tree])

    def test_pause_cancel_and_empty_work_do_not_plant(self):
        self.journal.review({"completedFocusSeconds": 100}, "stopped")
        self.assertEqual(self.journal.data["forest"], [])
        self.journal.finish("", "")
        self.journal.begin(self.session, self.tasks)
        self.journal.review({"completedFocusSeconds": 0}, "step_done")
        self.assertEqual(self.journal.data["forest"], [])

    def test_migrates_existing_completed_history_without_duplicate_trees(self):
        old = {"version": 1, "history": [{"id": "old-a", "endReason": "timer", "elapsedSeconds": 600}, {"id": "old-b", "endReason": "step_done", "elapsedSeconds": 120}, {"id": "cancelled", "endReason": "stopped", "elapsedSeconds": 90}]}
        self.path.write_text(json.dumps(old), encoding="utf-8")
        recovered = FocusJourney(self.path)
        self.assertEqual({tree["id"] for tree in recovered.data["forest"]}, {"old-a", "old-b"})
        self.assertEqual(FocusJourney(self.path).data["forest"], recovered.data["forest"])

    def test_forest_survives_history_truncation(self):
        self.journal.data["history"] = [{"id": str(i)} for i in range(500)]
        self.journal.review({"completedFocusSeconds": 100}, "step_done")
        tree = self.journal.data["forest"][0]
        self.journal.finish("", "")
        self.assertEqual(len(self.journal.data["history"]), 500)
        self.journal.data["history"] = []
        self.journal.save()
        self.assertEqual(FocusJourney(self.path).data["forest"], [tree])


if __name__ == "__main__":
    unittest.main()
