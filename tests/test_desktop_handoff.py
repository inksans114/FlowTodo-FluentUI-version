import unittest
from desktop_handoff import wake_code

class HandoffTests(unittest.TestCase):
    def test_only_public_wake_code_is_accepted(self):
        self.assertEqual(wake_code('flowtodo://auth/complete?code=ABCDEF1234'),'ABCDEF1234')
        for value in ('https://auth/complete?code=ABCDEF1234','flowtodo://evil/complete?code=ABCDEF1234','flowtodo://auth/complete?accessToken=secret','flowtodo://auth/complete?code=ABCDEF1234&code=AAAAAAAAAA','flowtodo://auth/complete?code=ABCDEF1234#token','flowtodo://auth/complete?code=AAAAAAAAA','flowtodo://auth/complete?code=abcdef1234'):
            self.assertIsNone(wake_code(value))
    def test_local_wake_reaches_the_running_instance(self):
        import tempfile
        from PySide6.QtCore import QCoreApplication
        from PySide6.QtTest import QTest
        from desktop_handoff import Handoff
        app=QCoreApplication.instance() or QCoreApplication([])
        with tempfile.TemporaryDirectory() as directory:
            listener=Handoff(directory);received=[];listener.wake.connect(received.append)
            self.assertTrue(listener.listen())
            # A browser starts another process. A Python thread holding the GIL
            # in Qt's blocking socket wait cannot model that exchange reliably.
            import subprocess, sys, time
            from pathlib import Path
            sender = subprocess.Popen([sys.executable, '-c',
                "import sys; from PySide6.QtCore import QCoreApplication; "
                "from desktop_handoff import Handoff; app=QCoreApplication([]); "
                "sys.exit(0 if Handoff(sys.argv[1]).forward('ABCDEF1234') else 1)", directory],
                cwd=Path(__file__).resolve().parents[1], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                deadline = time.monotonic() + 8
                while sender.poll() is None and time.monotonic() < deadline:
                    app.processEvents()
                    time.sleep(0.005)
                if sender.poll() is None:
                    sender.kill()
                out, err = sender.communicate(timeout=2)
                self.assertEqual(sender.returncode, 0, repr((received, out, err)))
                self.assertEqual(received, ['ABCDEF1234'])
            finally:
                if sender.poll() is None:
                    sender.kill()
                    sender.wait()
                listener.server.close()

if __name__=='__main__':unittest.main()
