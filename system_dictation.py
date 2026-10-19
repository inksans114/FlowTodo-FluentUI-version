"""Open Windows voice typing in the focused editor; no audio or API handling."""
import ctypes
import sys


class KeyboardInput(ctypes.Structure):
    _fields_ = [("vk", ctypes.c_uint16), ("scan", ctypes.c_uint16),
                ("flags", ctypes.c_uint32), ("time", ctypes.c_uint32),
                ("extra", ctypes.c_size_t)]


class MouseInput(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_int32), ("dy", ctypes.c_int32),
                ("data", ctypes.c_uint32), ("flags", ctypes.c_uint32),
                ("time", ctypes.c_uint32), ("extra", ctypes.c_size_t)]


class InputUnion(ctypes.Union):
    _fields_ = [("keyboard", KeyboardInput), ("mouse", MouseInput)]


class Input(ctypes.Structure):
    _fields_ = [("type", ctypes.c_uint32), ("value", InputUnion)]


def _keys(sequence):
    return (Input * len(sequence))(*(Input(1, InputUnion(keyboard=KeyboardInput(vk, 0, flags, 0, 0)))
                                   for vk, flags in sequence))


def open_voice_typing(window_id, user32=None):
    """Send Win+H only while our editor's window remains in the foreground.

    A caller may inject a fake user32 for tests. No microphone is opened here;
    Windows owns its listening UI, transcription and microphone permissions.
    """
    if user32 is None:
        if sys.platform != "win32":
            raise RuntimeError("请使用系统输入法的语音输入，在文本框内输入文字。")
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.GetForegroundWindow.restype = ctypes.c_void_p
        user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
        user32.GetAsyncKeyState.restype = ctypes.c_int16
        user32.SendInput.argtypes = [ctypes.c_uint32, ctypes.POINTER(Input), ctypes.c_int]
        user32.SendInput.restype = ctypes.c_uint32
    if not window_id or user32.GetForegroundWindow() != int(window_id):
        return False
    if any(user32.GetAsyncKeyState(key) & 0x8000 for key in (0x10, 0x11, 0x12, 0x5B, 0x5C)):
        raise RuntimeError("请松开组合键，再点击语音输入；也可以在文本框中直接按 Win + H。")
    keys = _keys(((0x5B, 0), (0x48, 0), (0x48, 2), (0x5B, 2)))
    if user32.SendInput(len(keys), keys, ctypes.sizeof(Input)) != len(keys):
        # A partial insertion must never leave our synthetic modifier held down.
        release = _keys(((0x48, 2), (0x5B, 2)))
        user32.SendInput(len(release), release, ctypes.sizeof(Input))
        raise RuntimeError("未能唤起系统听写。请点击文本框，再按 Win + H。")
    return True


def close_voice_typing(window_id, user32=None):
    """Dismiss the input flyout with Escape only in our foreground window."""
    if user32 is None:
        if sys.platform != 'win32':
            return False
        user32 = ctypes.WinDLL('user32', use_last_error=True)
        user32.GetForegroundWindow.restype = ctypes.c_void_p
        user32.SendInput.argtypes = [ctypes.c_uint32, ctypes.POINTER(Input), ctypes.c_int]
        user32.SendInput.restype = ctypes.c_uint32
    if not window_id or user32.GetForegroundWindow() != int(window_id):
        return False
    keys = _keys(((0x1B, 0), (0x1B, 2)))
    if user32.SendInput(len(keys), keys, ctypes.sizeof(Input)) != len(keys):
        release = _keys(((0x1B, 2),))
        user32.SendInput(len(release), release, ctypes.sizeof(Input))
        return False
    return True


def system_motion_enabled(user32=None):
    """Read the Windows client-area animation preference without changing it."""
    if user32 is None:
        if sys.platform != 'win32':
            return True
        user32 = ctypes.WinDLL('user32', use_last_error=True)
        user32.SystemParametersInfoW.argtypes = [ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32]
        user32.SystemParametersInfoW.restype = ctypes.c_int
    enabled = ctypes.c_int(1)
    return bool(enabled.value) if user32.SystemParametersInfoW(0x1042, 0, ctypes.byref(enabled), 0) else True
