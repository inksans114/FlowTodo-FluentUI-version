"""Native RinUI/QML entry point for the FlowTodo migration."""

from __future__ import annotations

import os
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
VENDOR_DIR = BASE_DIR / "vendor"

sys.path.insert(0, str(VENDOR_DIR))
sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")
os.chdir(BASE_DIR)

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

from RinUI import RinUIWindow  # noqa: E402
from PySide6.QtCore import QCoreApplication, Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from compat_backend import RinUIBackend  # noqa: E402


def main() -> int:
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    app = QApplication(sys.argv)
    QCoreApplication.setOrganizationName("FlowTodo")
    QCoreApplication.setApplicationName("FlowTodo Native QML")

    backend = RinUIBackend()
    window = RinUIWindow(shared_engine=False)
    window.engine.rootContext().setContextProperty("Backend", backend)
    window.load(BASE_DIR / "qml" / "Main.qml")
    backend.attach_native_window(window.root_window)
    app.aboutToQuit.connect(backend.shutdown)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
