"""Exercise the real QML switch and COM shortcuts using isolated data and Startup folder."""
import json
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "vendor")]
os.chdir(ROOT)
DATA = tempfile.TemporaryDirectory(prefix="flowtodo-startup-ui-")
os.environ["FLOWTODO_DATA_DIR"] = str(Path(DATA.name) / "data")
os.environ["FLOWTODO_RINUI_CONFIG_DIR"] = str(Path(DATA.name) / "rinui")
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["QT_QUICK_BACKEND"] = "software"
os.environ["QT_QUICK_CONTROLS_STYLE"] = "Basic"

from PySide6.QtCore import QUrl
from PySide6.QtQml import QQmlEngine, QQmlExpression
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from RinUI import RinUIWindow
from compat_backend import RinUIBackend
from i18n_runtime import translator
from startup_manager import StartupShortcut, resolve_launch


def find(item, name):
    if item.objectName() == name:
        return item
    for child in item.childItems():
        found = find(child, name)
        if found is not None:
            return found


def qml(item, code):
    expression = QQmlExpression(QQmlEngine.contextForObject(item), item, code)
    value = expression.evaluate()
    assert not expression.hasError(), expression.error().toString()
    return value


app = QApplication([])
backend = RinUIBackend()
window = RinUIWindow(shared_engine=False)
window.engine.rootContext().setContextProperty("Backend", backend)
window.engine.rootContext().setContextProperty("I18nBridge", translator())
warnings, messages = [], []
window.engine.warnings.connect(lambda errors: warnings.extend(e.toString() for e in errors))
backend.messageRequested.connect(lambda *args: messages.append(args))
folder = Path(DATA.name) / "Startup"
folder.mkdir()
legacy = folder / "FlowDeck_AutoStart.bat"
legacy.write_text('start "" python main.py', encoding="utf-8")
backend.settings_database["autoStart"] = True  # Reproduce the stale checked setting.
with patch("main.StartupShortcut", lambda: StartupShortcut(folder)), \
        patch("main.startup_directory", lambda: folder), patch("main.winreg", None):
    window.load(ROOT / "qml/Main.qml")
    root = window.root_window
    assert root is not None, warnings
    backend.attach_native_window(root)
    root.setWidth(1240)
    root.setHeight(900)
    QTest.qWait(200)
    url = QUrl.fromLocalFile(str(ROOT / "qml/pages/AppSettings.qml")).toString()
    qml(root, "navigationView.push('" + url + "')")
    QTest.qWait(500)
    switch = find(root.contentItem(), "autoStartSwitch")
    assert switch is not None, warnings
    assert not switch.property("checked"), "The stale setting must not be shown as enabled"
    qml(switch, "checked = true; clicked()")
    shortcut = StartupShortcut(folder)
    assert switch.property("checked") and shortcut.matches(resolve_launch(ROOT))
    assert backend.settings_database["autoStart"]
    assert not legacy.exists(), "The old main.py BAT must be removed"
    old_time = shortcut.path.stat().st_mtime_ns
    backend.setSetting("focusDuration", 40)
    assert shortcut.path.stat().st_mtime_ns == old_time
    assert switch.property("checked")
    qml(switch, "checked = false; clicked()")
    assert not shortcut.path.exists() and not switch.property("checked")
    assert not backend.settings_database["autoStart"]
    with patch.object(StartupShortcut, "enable", side_effect=PermissionError("测试：启动目录不可写")):
        qml(switch, "checked = true; clicked()")
    assert not switch.property("checked") and not shortcut.path.exists()
    assert not backend.settings_database["autoStart"]
    assert messages[-1][0] == "error" and "不可写" in messages[-1][2]
    assert not warnings, warnings
    print(json.dumps({"ok": True, "checks": ["stale setting", "native app shortcut", "legacy cleanup",
          "unrelated settings", "disable", "failure rollback", "QML warnings"], "warnings": warnings},
          ensure_ascii=False), flush=True)
backend.shutdown()
root.close()
DATA.cleanup()
# Qt's global multimedia/engine cleanup is unrelated to these smoke assertions.
os._exit(0)
