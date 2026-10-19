"""Windows login startup: a verified shortcut to the native application."""
from dataclasses import dataclass
from pathlib import Path
import ctypes
import os
import subprocess
import sys
import uuid


@dataclass(frozen=True)
class LaunchTarget:
    executable: str
    arguments: str
    working_directory: str

    @property
    def command(self):
        return subprocess.list2cmdline([self.executable]) + (" " + self.arguments if self.arguments else "")


def resolve_launch(application_dir, *, executable=None, argv0=None, frozen=None, compiled=None):
    """Never persist a onefile extraction path or the old WebEngine main.py."""
    root = Path(application_dir).resolve()
    from app_paths import windows_package_family
    family = windows_package_family()
    if family:
        # The AUMID survives Store updates; a versioned WindowsApps path does not.
        explorer = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'explorer.exe'
        return LaunchTarget(str(explorer), 'shell:AppsFolder\\' + family + '!FlowTodo', str(explorer.parent))
    executable = Path(executable or sys.executable).resolve()
    frozen = getattr(sys, "frozen", False) if frozen is None else frozen
    if frozen:
        target = executable
        arguments = ""
    elif compiled is not None:
        # Nuitka documents argv[0] as the outer EXE, even in onefile mode.
        invocation = Path(argv0 or sys.argv[0])
        containing_dir = getattr(compiled, "containing_dir", None)
        if not invocation.is_absolute() and containing_dir:
            invocation = Path(containing_dir) / invocation.name
        target = invocation.resolve()
        if target.suffix.lower() != ".exe":
            raise RuntimeError("无法定位打包后的 FlowTodo.exe，请从软件本体启动后重试。")
        arguments = ""
    else:
        script = root / "app.py"
        if not script.is_file():
            raise RuntimeError("找不到 app.py，无法设置源码版自启动。")
        # The venv's pythonw preserves its dependencies without a console window.
        pythonw = executable.with_name("pythonw.exe")
        target = pythonw if pythonw.is_file() else executable
        arguments = subprocess.list2cmdline([str(script)])
    if not target.is_file():
        raise RuntimeError("启动文件已移动或不存在，请从当前软件位置重新开启自启动。")
    return LaunchTarget(str(target), arguments, str(target.parent if frozen or compiled is not None else root))


def startup_directory():
    if sys.platform != "win32":
        raise RuntimeError("此版本暂不支持系统登录时自动启动。")
    # CSIDL_STARTUP follows the current user's redirected/localized Startup folder.
    folder = ctypes.create_unicode_buffer(32768)
    result = ctypes.windll.shell32.SHGetFolderPathW(None, 7, None, 0, folder)
    if result != 0 or not folder.value:
        raise RuntimeError("无法定位 Windows 启动文件夹。")
    return Path(folder.value)


def _shell():
    # Lazy Windows import also keeps macOS builds independent of pywin32.
    import win32com.client
    return win32com.client.Dispatch("WScript.Shell")


def _same_path(left, right):
    if not left or not right:
        return False
    return os.path.normcase(os.path.abspath(left)) == os.path.normcase(os.path.abspath(right))


class StartupShortcut:
    def __init__(self, folder=None, shell_factory=None):
        self.folder = Path(folder) if folder is not None else startup_directory()
        self.path = self.folder / "FlowTodo.lnk"
        self.shell_factory = shell_factory or _shell

    def matches(self, launch, path=None):
        path = Path(path) if path is not None else self.path
        if not path.is_file() or not Path(launch.executable).is_file():
            return False
        try:
            link = self.shell_factory().CreateShortcut(str(path))
            return (_same_path(link.TargetPath, launch.executable)
                    and link.Arguments == launch.arguments
                    and _same_path(link.WorkingDirectory, launch.working_directory))
        except Exception:
            return False

    def enable(self, launch):
        if self.matches(launch):
            return
        self.folder.mkdir(parents=True, exist_ok=True)
        temporary = self.folder / (".FlowTodo-" + uuid.uuid4().hex + ".lnk")
        try:
            link = self.shell_factory().CreateShortcut(str(temporary))
            link.TargetPath = launch.executable
            link.Arguments = launch.arguments
            link.WorkingDirectory = launch.working_directory
            link.Description = "FlowTodo"
            icon = Path(launch.working_directory) / "logopromax.ico"
            link.IconLocation = str(icon if icon.is_file() else launch.executable) + ",0"
            link.Save()
            if not self.matches(launch, temporary):
                raise RuntimeError("自启动快捷方式校验失败，请重试。")
            os.replace(temporary, self.path)
            if not self.matches(launch):
                raise RuntimeError("未能保存自启动快捷方式。")
        finally:
            temporary.unlink(missing_ok=True)

    def disable(self):
        self.path.unlink(missing_ok=True)
