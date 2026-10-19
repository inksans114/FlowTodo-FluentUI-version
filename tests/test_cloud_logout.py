import json
import tempfile
import threading
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import Mock

from cloud_client import CloudClient, CloudError, SessionVault


class LogoutTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.vault = SessionVault(Path(self.temp.name) / 'session', (lambda b: b, lambda b: b))
        self.vault.save({'accessToken': 'old-token'})

    def test_local_session_clears_before_network_failure(self):
        opener = Mock()
        def offline(request, timeout):
            self.assertFalse(self.vault.memory)
            self.assertFalse(self.vault.path.exists())
            self.assertEqual(request.get_header('Authorization'), 'Bearer old-token')
            raise urllib.error.URLError('offline')
        opener.open.side_effect = offline
        with self.assertRaises(CloudError):
            CloudClient(self.vault, opener).logout()

    def test_old_revocation_cannot_clear_new_login(self):
        opener = Mock()
        client = CloudClient(self.vault, opener)
        old = client.clear_session()
        self.vault.save({'accessToken': 'new-token'})
        opener.open.side_effect = urllib.error.HTTPError('url', 401, 'expired', {}, None)
        with self.assertRaises(CloudError):
            client.revoke_session(old)
        self.assertEqual(self.vault.memory['accessToken'], 'new-token')
        self.assertEqual(json.loads(self.vault.path.read_text())['accessToken'], 'new-token')

    def test_delayed_login_cannot_restore_logged_out_session(self):
        client = CloudClient(self.vault)
        for native in (False, True):
            with self.subTest(native=native):
                def response(*args, **kwargs):
                    client.clear_session()
                    return {'accessToken': 'late-token'}
                client.request = response
                with self.assertRaises(CloudError):
                    if native:
                        client.native_verify('a@example.com', '123456', 'device')
                    else:
                        client.poll_login('device')
                self.assertFalse(client.logged_in)
                self.assertFalse(self.vault.path.exists())

    def test_busy_refresh_cannot_restore_account_after_logout(self):
        from PySide6.QtCore import QCoreApplication, QObject, Signal
        from PySide6.QtTest import QTest
        from cloud_controller import CloudController
        app = QCoreApplication.instance() or QCoreApplication([])
        class Backend(QObject):
            accountChanged = Signal()
            settingsChanged = Signal()
        backend = Backend()
        backend.data_dir = self.temp.name
        controller = CloudController(backend)
        controller.refresh_timer.stop()
        controller.client = CloudClient(self.vault)
        controller.cache = {'user': {'id': 'account'}}
        released = threading.Event()
        started = threading.Event()
        def refresh():
            started.set()
            released.wait(3)
            return {'user': {'id': 'account'}}
        controller.client.revoke_session = lambda session: None
        try:
            controller.job(refresh, lambda value: setattr(controller, 'cache', value))
            self.assertTrue(started.wait(1))
            self.assertTrue(controller.busy)
            controller.logout()
            self.assertFalse(controller.logged_in())
            self.assertFalse(controller.busy)
            self.assertEqual(controller.cache, {})
            released.set()
            for _ in range(50):
                QTest.qWait(10)
                if not controller.jobs:
                    break
            self.assertEqual(controller.cache, {})
            self.assertFalse(controller.logged_in())
        finally:
            released.set()
            controller.close()


if __name__ == '__main__':
    unittest.main()
