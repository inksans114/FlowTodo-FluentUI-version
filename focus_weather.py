"""City-level weather, fetched asynchronously only for the focus studio."""
import json
import math
from time import monotonic
from PySide6.QtCore import QObject, QTimer, QUrl, QUrlQuery, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest


def weather_kind(code):
    code = int(code)
    if code in (71, 73, 75, 77, 85, 86):
        return "snow"
    if code in (51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82, 95, 96, 99):
        return "rain"
    return "cloudy" if code in (2, 3, 45, 48) else "sunny"


class FocusWeather(QObject):
    changed = Signal()

    def __init__(self, backend):
        super().__init__(backend)
        self.backend = backend
        self.network = QNetworkAccessManager(self)
        self.state = {"status": "idle", "kind": "neutral", "city": ""}
        self.pending = set()
        self.generation = 0
        self.updated = None
        self.last_attempt = None
        self.last_error = ""
        self.timer = QTimer(self)
        self.timer.setInterval(30 * 60 * 1000)
        self.timer.timeout.connect(self.refresh)
        self.timer.start()

    def configure(self, mode, city=""):
        if mode not in ("auto", "city", "off"):
            return
        city = str(city).strip()[:80]
        if mode == "city" and not city:
            return
        settings = dict(self.backend.settings_database)
        settings.update(focusWeatherMode=mode, focusWeatherCity=city)
        self.backend.save_settings(json.dumps(settings, ensure_ascii=False))
        self.stop()
        self.state = {"status": "off" if mode == "off" else "idle", "kind": "neutral", "city": ""}
        self.updated = None
        self.changed.emit()
        self.refresh(force=True)

    def refresh(self, force=False):
        if not self.backend._immersive_active or self.pending:
            return
        mode = self.backend.settings_database.get("focusWeatherMode", "auto")
        if mode == "off":
            self.state = {"status": "off", "kind": "neutral", "city": ""}
            self.changed.emit()
            return
        now = monotonic()
        if not force and ((self.updated is not None and now-self.updated < 1800) or (self.last_attempt is not None and now-self.last_attempt < 300)):
            return
        self.last_attempt = now
        self.state = dict(self.state, status="loading", issue="")
        self.changed.emit()
        if mode == "city":
            self._get("https://geocoding-api.open-meteo.com/v1/search", {"name": self.backend.settings_database.get("focusWeatherCity", ""), "count": "1", "language": "zh", "format": "json"}, self._city)
        else:
            self._get("https://ipapi.co/json/", {}, self._location)

    def _get(self, endpoint, params, callback):
        url, query = QUrl(endpoint), QUrlQuery()
        for key, value in params.items():
            query.addQueryItem(key, str(value))
        url.setQuery(query)
        request = QNetworkRequest(url)
        request.setTransferTimeout(10000)
        request.setRawHeader(b"User-Agent", b"FlowTodo/FocusWeather")
        reply = self.network.get(request)
        self.pending.add(reply)
        generation = self.generation

        def finish():
            self.pending.discard(reply)
            try:
                if generation != self.generation:
                    return
                if reply.error() != QNetworkReply.NoError:
                    self.last_error = reply.errorString()
                    self.state = dict(self.state, issue="rate-limit" if reply.attribute(QNetworkRequest.HttpStatusCodeAttribute) == 429 else "network")
                    raise ValueError("Weather network unavailable")
                payload = json.loads(bytes(reply.readAll()))
                if not isinstance(payload, dict) or payload.get("error"):
                    raise ValueError("Invalid weather response")
                callback(payload)
            except (ValueError, TypeError, KeyError, IndexError, OverflowError):
                self.state = dict(self.state, status="stale" if self.updated is not None else "unavailable")
                self.changed.emit()
            finally:
                reply.deleteLater()
        reply.finished.connect(finish)

    def _city(self, payload):
        self._location(payload["results"][0])

    def _location(self, payload):
        lat, lon = float(payload["latitude"]), float(payload["longitude"])
        if not math.isfinite(lat) or not math.isfinite(lon) or not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError("Invalid coordinates")
        # Retain neither IP nor coordinates. Round the location to city scale
        # before sending it to the weather provider; the page only gets a label.
        self.state = dict(self.state, city=str(payload.get("city") or payload.get("name") or "")[:80])
        self._get("https://api.open-meteo.com/v1/forecast", {"latitude": f"{lat:.2f}", "longitude": f"{lon:.2f}", "current": "temperature_2m,weather_code,is_day", "timezone": "auto", "forecast_days": "1"}, self._weather)

    def _weather(self, payload):
        current = payload["current"]
        code, temperature = int(current["weather_code"]), float(current["temperature_2m"])
        if not math.isfinite(temperature) or code not in (0, 1, 2, 3, 45, 48, 51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 71, 73, 75, 77, 80, 81, 82, 85, 86, 95, 96, 99):
            raise ValueError("Invalid current weather")
        self.updated = monotonic()
        self.last_error = ""
        self.state = dict(self.state, status="ready", issue="", kind=weather_kind(code), temperature=round(temperature), isDay=bool(current.get("is_day", 1)), code=code, observedAt=current.get("time", ""), provider="Open-Meteo")
        self.changed.emit()

    def stop(self):
        self.generation += 1
        for reply in list(self.pending):
            reply.abort()
        self.pending.clear()

    def shutdown(self):
        self.timer.stop()
        self.stop()
