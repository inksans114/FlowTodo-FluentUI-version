import ctypes
import unittest
from system_dictation import Input, open_voice_typing, close_voice_typing, system_motion_enabled


class FakeWindows:
    def __init__(self, foreground=123, modifier=False, partial=False):
        self.foreground, self.modifier, self.partial = foreground, modifier, partial
        self.calls = []

    def GetForegroundWindow(self):
        return self.foreground

    def GetAsyncKeyState(self, key):
        return 0x8000 if self.modifier else 0

    def SendInput(self, count, keys, size):
        self.calls.append([(item.value.keyboard.vk, item.value.keyboard.flags) for item in keys])
        assert size == ctypes.sizeof(Input)
        return 1 if self.partial else count


class SystemDictationTests(unittest.TestCase):
    def test_keyboard_abi_and_shortcut(self):
        self.assertEqual(ctypes.sizeof(Input), 40 if ctypes.sizeof(ctypes.c_void_p) == 8 else 28)
        windows = FakeWindows()
        self.assertTrue(open_voice_typing(123, windows))
        self.assertEqual(windows.calls, [[(0x5B, 0), (0x48, 0), (0x48, 2), (0x5B, 2)]])

    def test_other_window_never_receives_shortcut(self):
        for handle in (0, 999):
            windows = FakeWindows()
            self.assertFalse(open_voice_typing(handle, windows))
            self.assertEqual(windows.calls, [])

    def test_held_modifiers_do_not_change_shortcut(self):
        windows = FakeWindows(modifier=True)
        with self.assertRaisesRegex(RuntimeError, '松开组合键'):
            open_voice_typing(123, windows)
        self.assertEqual(windows.calls, [])

    def test_partial_delivery_releases_keys_and_offers_manual_shortcut(self):
        windows = FakeWindows(partial=True)
        with self.assertRaisesRegex(RuntimeError, 'Win \\+ H'):
            open_voice_typing(123, windows)
        self.assertEqual(windows.calls[-1], [(0x48, 2), (0x5B, 2)])

    def test_dismiss_only_in_owned_foreground_window(self):
        windows = FakeWindows()
        self.assertFalse(close_voice_typing(999, windows))
        self.assertEqual(windows.calls, [])
        self.assertTrue(close_voice_typing(123, windows))
        self.assertEqual(windows.calls, [[(0x1B, 0), (0x1B, 2)]])

    def test_partial_dismiss_releases_escape(self):
        windows = FakeWindows(partial=True)
        self.assertFalse(close_voice_typing(123, windows))
        self.assertEqual(windows.calls[-1], [(0x1B, 2)])

    def test_windows_motion_preference(self):
        class Preference:
            def __init__(self, enabled): self.enabled = enabled
            def SystemParametersInfoW(self, action, size, value, flags):
                self.action = action
                ctypes.cast(value, ctypes.POINTER(ctypes.c_int)).contents.value = self.enabled
                return True
        for enabled in (0, 1):
            windows = Preference(enabled)
            self.assertEqual(system_motion_enabled(windows), bool(enabled))
            self.assertEqual(windows.action, 0x1042)


if __name__ == '__main__':
    unittest.main()
