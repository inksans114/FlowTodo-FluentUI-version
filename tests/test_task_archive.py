import unittest
from datetime import datetime, timedelta
from task_archive import archive_expired, referenced_task_ids


class TaskArchiveTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 5, 12)
        self.old = (self.now - timedelta(days=14)).isoformat()

    def test_disabled_and_boundary(self):
        tasks = [{"id": 1, "createdAt": self.old, "done": False}]
        self.assertFalse(archive_expired(tasks, 0, self.now))
        self.assertTrue(archive_expired(tasks, 14, self.now))
        self.assertFalse(tasks[0]["done"])
        self.assertFalse(archive_expired(tasks, 14, self.now))

    def test_protected_and_future_tasks(self):
        variants = [{"taskType": "daily"}, {"taskType": "pomodoro"}, {"taskType": "long"},
                    {"projectId": 7}, {"_source": "ai"}, {"isSpecial": True}, {"done": True},
                    {"scheduledDate": "2026-10-10"}, {"id": 99}]
        tasks = [dict({"id": i, "createdAt": self.old}, **variant) for i, variant in enumerate(variants)]
        self.assertFalse(archive_expired(tasks, 3, self.now, protected_ids={99}))
        self.assertTrue(all("archivedAt" not in task for task in tasks))

    def test_legacy_grace_and_edit_reset(self):
        tasks = [{"id": 1}, {"id": 2, "createdAt": self.old, "updatedAt": self.now.isoformat()}]
        self.assertTrue(archive_expired(tasks, 3, self.now))
        self.assertTrue(all("archivedAt" not in task for task in tasks))
        self.assertTrue(archive_expired(tasks, 3, self.now + timedelta(days=3)))
        self.assertTrue(all(task.get("archivedAt") for task in tasks))

    def test_nested_plan_references(self):
        self.assertEqual(referenced_task_ids({"cycles": [{"steps": [{"taskId": 3}], "taskIds": [4]}],
                                               "tasks": [{"id": 5}]}), {"3", "4", "5"})
