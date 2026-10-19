"""Install only supervision dependencies in THIS interpreter, never build the app."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    print(f"识别组件安装环境：Python {sys.version.split()[0]}\n{sys.executable}", flush=True)
    if sys.version_info < (3, 9):
        print("需要 Python 3.9 或以上。", file=sys.stderr)
        return 1
    result = subprocess.run([sys.executable, "-m", "pip", "install", "--only-binary=:all:",
                             "-r", str(ROOT / "requirements-supervision.txt")], cwd=ROOT)
    if result.returncode:
        return result.returncode
    result = subprocess.run([sys.executable, str(ROOT / "tools/prepare_supervision_models.py")], cwd=ROOT)
    if result.returncode:
        return result.returncode
    # Use a clean child process: the installer may have replaced already-loaded DLLs.
    env = dict(os.environ, PYTHONPATH=str(ROOT))
    result = subprocess.run([sys.executable, "-c",
        "from supervision_environment import bootstrap,availability; bootstrap(); "
        "s=availability(); print(s['cameraReason'] or '摄像头组件就绪'); "
        "print(s['screenReason'] or '屏幕组件就绪'); "
        "raise SystemExit(0 if s['camera'] and s['screen'] else 1)"], cwd=ROOT, env=env)
    if result.returncode == 0:
        print("安装完成，请重新启动 FlowTodo。没有运行打包，也没有开启摄像头或截图。")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
