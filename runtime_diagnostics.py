"""Early, local diagnostics for windowed builds (before Qt/native imports)."""
from __future__ import annotations

import atexit
from datetime import datetime
import faulthandler
import logging
import os
from pathlib import Path
import sys
import tempfile
import threading

_stream = None  # faulthandler needs this descriptor to stay open until exit.
_logger = logging.getLogger("flowtodo.runtime")
_qt_handler = None


def install() -> Path | None:
    """Never make an unwritable diagnostics directory prevent app startup."""
    global _stream
    if _stream is not None:
        return Path(_stream.name)
    from app_paths import user_data_dir

    name = f"runtime-{datetime.now():%Y%m%d-%H%M%S}-{os.getpid()}.log"
    for directory in (user_data_dir().parent / "logs", Path(tempfile.gettempdir()) / "FlowTodo/logs"):
        try:
            directory.mkdir(parents=True, exist_ok=True)
            _stream = (directory / name).open("a", encoding="utf-8", buffering=1)
            break
        except OSError:
            continue
    if _stream is None:
        return None

    handler = logging.StreamHandler(_stream)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(threadName)s] %(message)s"))
    _logger.addHandler(handler)
    _logger.setLevel(logging.INFO)
    _logger.propagate = False
    # Windowed Nuitka/PyInstaller builds may expose no standard streams.
    for name in ("stdout", "stderr"):
        if getattr(sys, name) is None:
            setattr(sys, name, _stream)
    try:
        faulthandler.enable(file=_stream, all_threads=True)
    except (OSError, RuntimeError):
        _logger.exception("Native fault handler unavailable")

    previous_hook = sys.excepthook

    def exception_hook(kind, value, tb):
        _logger.critical("Unhandled Python exception", exc_info=(kind, value, tb))
        previous_hook(kind, value, tb)

    sys.excepthook = exception_hook
    previous_thread_hook = threading.excepthook

    def thread_hook(args):
        _logger.critical("Unhandled worker exception", exc_info=(args.exc_type, args.exc_value, args.exc_traceback))
        previous_thread_hook(args)

    threading.excepthook = thread_hook
    # Only record selected runtime switches; never dump account data or the environment.
    _logger.info("Process start: Python=%s platform=%s", sys.version.split()[0], sys.platform)
    if sys.platform == "win32":
        _logger.info("Windows=%s", sys.getwindowsversion())
    for key in ("QT_QUICK_BACKEND", "QSG_RHI_BACKEND", "QTWEBENGINE_CHROMIUM_FLAGS"):
        _logger.info("%s=%s", key, os.environ.get(key, "<default>"))
    atexit.register(_logger.info, "Python process exit")
    # Keep a small history, deleting only our own old runtime logs.
    try:
        old = sorted(directory.glob("runtime-*.log"), key=lambda path: path.stat().st_mtime, reverse=True)
        for path in old[10:]:
            if path != Path(_stream.name):
                path.unlink(missing_ok=True)
    except OSError:
        pass
    return Path(_stream.name)


def install_qt_logging() -> None:
    global _qt_handler
    if _stream is None or _qt_handler is not None:
        return
    from PySide6.QtCore import qInstallMessageHandler

    def handler(kind, context, message):
        # Qt warnings include render-device failures and QThread fatal errors.
        _logger.warning("Qt %s: %s (%s:%s)", kind.name, message, context.file or "", context.line)
        if previous is not None:
            previous(kind, context, message)

    previous = qInstallMessageHandler(handler)
    _qt_handler = handler


def checkpoint(message: str) -> None:
    _logger.info(message)
