"""Automatic desktop sync selects portable records and respects user control."""
import tempfile
import unittest
from unittest.mock import Mock
from PySide6.QtCore import QCoreApplication, QObject, Signal
from cloud_controller import CloudController


class Backend(QObject):
    accountChanged = Signal()
    settingsChanged = Signal()
    tasksChanged = Signal()
    groupsChanged = Signal()


class AutoSyncTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.backend = Backend()
        self.backend.data_dir = self.temp.name
        self.backend.settings_database = {}
        self.backend._cloud_snapshot = lambda: [
            {'kind': 'tasks', 'key': 'tasks:task'},
            {'kind': 'flows', 'key': 'flows:flow'},
            {'kind': 'aiPlans', 'key': 'aiPlans:plan'},
        ]
        self.controller = CloudController(self.backend)
        self.addCleanup(self.controller.close)
        self.controller.refresh_timer.stop()
        self.controller.auto_timer.stop()
        self.controller.client = Mock(logged_in=True)
        self.controller.cache = {'user': {'id': 'test-account'}}
        self.controller.sync = Mock(return_value=True)

    def test_uploads_tasks_and_flows_without_periodic_toasts(self):
        self.assertTrue(self.controller.auto_sync())
        self.controller.sync.assert_called_once_with(['tasks:task', 'flows:flow'], quiet=True)

    def test_still_pulls_when_local_library_is_empty(self):
        self.backend._cloud_snapshot = lambda: []
        self.assertTrue(self.controller.auto_sync())
        self.controller.sync.assert_called_once_with([], quiet=True)

    def test_pauses_for_disabled_busy_logged_out_or_unresolved_conflict(self):
        cases = ['disabled', 'busy', 'logged-out', 'conflict', 'no-user']
        for case in cases:
            with self.subTest(case=case):
                self.backend.settings_database = {'cloudAutoSync': case != 'disabled'}
                self.controller.busy = case == 'busy'
                self.controller.client.logged_in = case != 'logged-out'
                self.controller.conflicts = [{}] if case == 'conflict' else []
                self.controller.cache = {} if case == 'no-user' else {'user': {'id': 'test-account'}}
                self.assertFalse(self.controller.auto_sync())
        self.controller.sync.assert_not_called()

    def test_local_changes_schedule_one_debounced_sync(self):
        self.backend.tasksChanged.emit()
        self.assertTrue(self.controller.auto_debounce.isActive())
        self.backend.groupsChanged.emit()
        self.assertTrue(self.controller.auto_debounce.isSingleShot())
        self.assertEqual(self.controller.auto_debounce.interval(), 1500)


if __name__ == '__main__':
    unittest.main()
