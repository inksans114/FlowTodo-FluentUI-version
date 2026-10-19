"""Writable application data paths, independent of an installed app bundle."""
import os
import sys
from pathlib import Path


def windows_package_family():
    """Return MSIX identity, or an empty string for ordinary desktop launches."""
    if sys.platform != 'win32':
        return ''
    import ctypes
    length = ctypes.c_uint32(0)
    api = ctypes.windll.kernel32.GetCurrentPackageFamilyName
    if api(ctypes.byref(length), None) != 122:
        return ''
    value = ctypes.create_unicode_buffer(length.value)
    return value.value if api(ctypes.byref(length), value) == 0 else ''


def user_data_dir(platform=None, environ=None, home=None):
    platform = platform or sys.platform
    environ = os.environ if environ is None else environ
    home = Path.home() if home is None else Path(home)
    if environ.get('FLOWTODO_DATA_DIR'):
        return Path(environ['FLOWTODO_DATA_DIR']).expanduser()
    if platform == 'darwin':
        return home / 'Library/Application Support/FlowTodo/data'
    if platform == 'win32':
        return Path(environ.get('LOCALAPPDATA') or home) / 'FlowTodo/data'
    return Path(environ.get('XDG_DATA_HOME') or home / '.local/share') / 'FlowTodo/data'
