import json
import unittest
from PySide6.QtCore import QObject, QCoreApplication, QByteArray, Signal
from PySide6.QtNetwork import QNetworkReply
from focus_weather import FocusWeather, weather_kind


class Reply(QObject):
    finished = Signal()

    def __init__(self):
        super().__init__()
        self.payload = {}
        self.failed = False

    def error(self):
        return QNetworkReply.TimeoutError if self.failed else QNetworkReply.NoError

    def errorString(self):
        return "Test timeout"

    def attribute(self, name):
        return None

    def readAll(self):
        return QByteArray(json.dumps(self.payload).encode())

    def deliver(self, payload, failed=False):
        self.payload, self.failed = payload, failed
        self.finished.emit()

    def abort(self):
        self.failed = True
        self.finished.emit()


class Network:
    def __init__(self):
        self.calls = []

    def get(self, request):
        reply = Reply()
        self.calls.append((request.url().toString(), reply))
        return reply


class Backend(QObject):
    _immersive_active = True

    def __init__(self):
        super().__init__()
        self.settings_database = {}

    def save_settings(self, payload):
        self.settings_database = json.loads(payload)


class WeatherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def setUp(self):
        self.backend = Backend()
        self.weather = FocusWeather(self.backend)
        self.weather.network = Network()

    def tearDown(self):
        self.weather.shutdown()

    def complete(self, code=61):
        self.weather.refresh()
        self.weather.network.calls[-1][1].deliver({"city": "Shanghai", "latitude": 31.23456, "longitude": 121.45678, "ip": "not-to-be-retained"})
        self.weather.network.calls[-1][1].deliver({"current": {"weather_code": code, "temperature_2m": 18.6, "is_day": 1, "time": "2026-10-05T14:00"}})

    def test_current_weather_and_city_only(self):
        self.complete()
        self.assertEqual(self.weather.state["kind"], "rain")
        self.assertEqual(self.weather.state["temperature"], 19)
        self.assertEqual(self.weather.state["city"], "Shanghai")
        request = self.weather.network.calls[1][0]
        self.assertIn("latitude=31.23", request)
        self.assertIn("longitude=121.46", request)
        self.assertNotIn("not-to-be-retained", json.dumps(self.weather.state))
        self.assertFalse(any(key in self.weather.state for key in ("ip", "latitude", "longitude")))

    def test_cache_and_offline_keep_last_weather(self):
        self.complete()
        self.weather.refresh()
        self.assertEqual(len(self.weather.network.calls), 2)
        self.weather.refresh(force=True)
        self.weather.network.calls[-1][1].deliver({}, failed=True)
        self.assertEqual(self.weather.state["status"], "stale")
        self.assertEqual(self.weather.state["kind"], "rain")

    def test_disable_cancels_and_stale_reply_cannot_reenable(self):
        self.weather.refresh()
        previous = self.weather.network.calls[-1][1]
        self.weather.configure("off")
        previous.deliver({"city": "old", "latitude": 20, "longitude": 30})
        self.assertEqual(self.weather.state["status"], "off")
        self.assertEqual(len(self.weather.network.calls), 1)
        self.assertEqual(self.backend.settings_database["focusWeatherMode"], "off")

    def test_hidden_studio_does_not_query(self):
        self.backend._immersive_active = False
        self.weather.refresh(force=True)
        self.assertFalse(self.weather.network.calls)

    def test_bad_location_preserves_neutral_scene(self):
        self.weather.refresh()
        self.weather.network.calls[-1][1].deliver({"latitude": 900, "longitude": 30})
        self.assertEqual(self.weather.state["status"], "unavailable")
        self.assertEqual(self.weather.state["kind"], "neutral")

    def test_manual_city_and_weather_codes(self):
        self.weather.configure("city", " 北京 ")
        self.assertIn("geocoding-api.open-meteo.com", self.weather.network.calls[0][0])
        self.weather.network.calls[0][1].deliver({"results": [{"name": "北京", "latitude": 39.9, "longitude": 116.4}]})
        self.weather.network.calls[1][1].deliver({"current": {"weather_code": 0, "temperature_2m": 22, "is_day": 1}})
        self.assertEqual(self.weather.state["kind"], "sunny")
        self.assertEqual([weather_kind(code) for code in (0, 3, 45, 65, 95, 75)], ["sunny", "cloudy", "cloudy", "rain", "rain", "snow"])


if __name__ == "__main__":
    unittest.main()
