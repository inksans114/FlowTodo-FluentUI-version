"""Local navigation and bounded renderer recovery without starting Chromium."""
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from PySide6.QtCore import QUrl
from PySide6.QtWebEngineCore import QWebEnginePage
from focus_studio_window import FocusStudioWindow, StudioPage


class StudioNavigationTests(unittest.TestCase):
    def test_unicode_space_percent_and_hash_in_install_path_are_valid(self):
        for directory in ('FlowTodo', 'FlowTodo 新版本', '中文目录', 'FlowTodo 50% #test'):
            path = Path.cwd() / directory / 'focus-studio/index.html'
            page = SimpleNamespace(entry_path=path.resolve())
            url = QUrl.fromLocalFile(str(path))
            for fragment in ('', 'software'):
                url.setFragment(fragment)
                self.assertTrue(StudioPage.acceptNavigationRequest(page, url, QWebEnginePage.NavigationTypeOther, True))

    def test_unrelated_local_pages_and_remote_navigation_are_still_rejected(self):
        path = Path.cwd() / 'focus-studio/index.html'
        page = SimpleNamespace(entry_path=path.resolve())
        for url in (QUrl.fromLocalFile(str(path.parent / 'other.html')), QUrl('https://example.test/'), QUrl('about:blank')):
            self.assertFalse(StudioPage.acceptNavigationRequest(page, url, QWebEnginePage.NavigationTypeOther, True))


class StudioRecoveryTests(unittest.TestCase):
    def test_leaving_fullscreen_keeps_the_inflight_guided_request(self):
        from compat_backend import RinUIBackend
        pending = {'id': 'session', 'index': 1}
        backend = SimpleNamespace(_immersive_active=True, _guided_pending=pending,
                                  _sync_saved_ai_journey=Mock(), _studio_window=SimpleNamespace(hide=Mock()),
                                  immersiveFocusClosed=SimpleNamespace(emit=Mock()), island_windows={})
        RinUIBackend.exitFocusStudio(backend)
        self.assertIs(backend._guided_pending, pending)
        self.assertFalse(backend._immersive_active)

    def view(self):
        backend = SimpleNamespace(_immersive_active=True, exitFocusStudio=Mock(),
                                  messageRequested=SimpleNamespace(emit=Mock()),
                                  focus_journey=SimpleNamespace(active={}))
        return SimpleNamespace(backend=backend, isVisible=Mock(return_value=True),
                               _presentation_id=1, _recovery_attempts=0,
                               _ready_watchdog=SimpleNamespace(start=Mock(), stop=Mock()),
                               _entry_url=QUrl('file:///scene/index.html'), _reload_entry=Mock(),
                               studio_page=SimpleNamespace(runJavaScript=Mock()),
                               bridge=SimpleNamespace(publish=Mock()), update=Mock())

    def test_failed_renderer_retries_once_then_returns_to_app(self):
        view = self.view()
        with patch('focus_studio_window.QTimer.singleShot', side_effect=lambda _, callback: callback()):
            FocusStudioWindow._recover_scene(view)
        view._reload_entry.assert_called_once()
        self.assertEqual(view._recovery_attempts, 1)
        FocusStudioWindow._recover_scene(view)
        view.backend.exitFocusStudio.assert_called_once()
        view.backend.messageRequested.emit.assert_called_once()
        self.assertFalse(view.backend.focus_journey.active)  # Recovery does not change a session.

    def test_hidden_scene_never_steals_focus_or_reloads(self):
        view = self.view()
        view.isVisible.return_value = False
        FocusStudioWindow._recover_scene(view)
        view._reload_entry.assert_not_called()
        view.backend.exitFocusStudio.assert_not_called()

    def test_stale_readiness_callback_does_not_affect_new_presentation(self):
        view = self.view()
        FocusStudioWindow._scene_ready(view, True, 0)
        view._ready_watchdog.stop.assert_not_called()
        view.bridge.publish.assert_not_called()

    def test_connected_page_publishes_latest_state_and_reopens_pending_questions(self):
        view = self.view()
        view.backend.focus_journey.active = {'source': {'pendingClarification': {'id': 'q'}}}
        FocusStudioWindow._scene_ready(view, True, 1)
        view._ready_watchdog.stop.assert_called_once()
        view.bridge.publish.assert_called_once()
        view.studio_page.runJavaScript.assert_called_once_with('window.flowFocus.showProgressQuestions()')

    def test_unresponsive_page_leaves_watchdog_running(self):
        view = self.view()
        FocusStudioWindow._scene_ready(view, False, 1)
        view._ready_watchdog.stop.assert_not_called()

    def test_same_fragment_url_forces_reload_instead_of_same_document_navigation(self):
        url = QUrl('file:///scene/index.html#software')
        view = SimpleNamespace(url=lambda: url, _entry_url=url, reload=Mock(), load=Mock())
        FocusStudioWindow._reload_entry(view)
        view.reload.assert_called_once()
        view.load.assert_not_called()
        self.assertFalse(view.loaded)

    def test_unloaded_url_loads_the_entry(self):
        target = QUrl('file:///scene/index.html#software')
        view = SimpleNamespace(url=lambda: QUrl('about:blank'), _entry_url=target, reload=Mock(), load=Mock())
        FocusStudioWindow._reload_entry(view)
        view.load.assert_called_once_with(target)
        view.reload.assert_not_called()


if __name__ == '__main__':
    unittest.main()
