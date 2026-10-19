"""Optional live provider check; only prints city and weather, never IP."""
import json
import sys
from pathlib import Path
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from PySide6.QtCore import QObject, QCoreApplication, QTimer
from focus_weather import FocusWeather

class PreviewBackend(QObject):
    _immersive_active = True
    settings_database = {"focusWeatherMode": "auto"}

app = QCoreApplication([])
backend = PreviewBackend()
if len(sys.argv) > 1:
    backend.settings_database = {"focusWeatherMode": "city", "focusWeatherCity": sys.argv[1]}
weather = FocusWeather(backend)
weather.changed.connect(lambda: app.quit() if weather.state["status"] in ("ready", "unavailable") else None)
QTimer.singleShot(0, weather.refresh)
QTimer.singleShot(25000, app.quit)
app.exec()
print(json.dumps(weather.state, ensure_ascii=False))
if weather.last_error:
    print(weather.last_error)
weather.shutdown()
sys.exit(0 if weather.state["status"] == "ready" else 1)
