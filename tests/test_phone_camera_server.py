import importlib.util
import io
import json
import ssl
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from phone_camera_server import PhoneStreamServer, private_host
from phone_network import ranked_interfaces


class AddressTests(unittest.TestCase):
    def test_only_private_lan_addresses(self):
        self.assertEqual(private_host("192.168.1.10"), "192.168.1.10")
        for host in ("8.8.8.8", "0.0.0.0", "127.0.0.1", "169.254.1.1", "198.18.0.1", "192.0.0.1", "::1"):
            with self.assertRaises(ValueError):
                private_host(host)

    def test_real_wifi_selected_before_vmware_and_disconnected_adapters(self):
        def row(name, ip, kind="Ethernet", up=True):
            return dict(name=name, ip=ip, type=kind, up=up, running=up)
        interfaces = ranked_interfaces([
            row("VMware VMnet8", "192.168.159.1"), row("WLAN", "192.168.1.11", "Wifi"),
            row("Ethernet", "10.0.0.5"), row("old WiFi", "192.168.2.9", "Wifi", False),
            row("Mihomo", "198.18.0.1", "Unknown"), row("invalid", "not-an-ip")])
        self.assertEqual([item["ip"] for item in interfaces], ["192.168.1.11", "10.0.0.5", "192.168.159.1"])
        self.assertIn("虚拟网卡", interfaces[-1]["label"])


@unittest.skipUnless(importlib.util.find_spec("cryptography"), "phone HTTPS dependency not installed")
class PhoneServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = tempfile.TemporaryDirectory()
        cls.server = PhoneStreamServer("127.0.0.1", cls.data.name, allow_loopback=True)
        cls.context = ssl.create_default_context(cadata=cls.server.ca.read_bytes())
        from PIL import Image
        image = io.BytesIO()
        Image.new("RGB", (32, 32), "white").save(image, format="JPEG")
        cls.jpeg = image.getvalue()

    @classmethod
    def tearDownClass(cls):
        cls.server.close()
        cls.data.cleanup()

    def setUp(self):
        self.server.set_running(False)
        self.server.last_frame = 0

    def request(self, path, data=None, token=None, extra=None):
        headers = {"X-FlowTodo-Token": self.server.token if token is None else token}
        if data is not None:
            headers["Content-Type"] = "image/jpeg"
        headers.update(extra or {})
        request = urllib.request.Request(self.server.origin + path, data=data, headers=headers)
        return urllib.request.urlopen(request, context=self.context, timeout=3)

    def test_page_and_tls_certificate(self):
        with self.request("/") as response:
            page = response.read().decode()
            self.assertIn("getUserMedia", page)
            self.assertIn("audio:false", page)
            self.assertIn("no-store", response.headers["Cache-Control"])
        with self.request("/status") as response:
            self.assertFalse(json.loads(response.read())["running"])

    def test_pairing_secret_required(self):
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.request("/status", token="wrong")
        self.assertEqual(error.exception.code, 403)

    def test_refresh_can_render_page_without_exposing_pairing_secret(self):
        with self.request("/", token="") as response:
            page = response.read().decode()
            self.assertEqual(response.status, 200)
            self.assertIn("address.hash", page)
            self.assertNotIn(self.server.token, page)
        self.assertTrue(self.server.last_page)
        self.assertIn("#token=", self.server.url)

    def test_http_diagnostics_do_not_expose_secret_or_accept_frames(self):
        with urllib.request.urlopen(self.server.check_url, timeout=2) as response:
            page = response.read().decode()
            self.assertIn("手机已经连到电脑", page)
            self.assertIn(self.server.fingerprint, page)
            self.assertNotIn(self.server.token, page)
        self.assertTrue(self.server.last_probe)
        with urllib.request.urlopen(self.server.check_url.replace("/check", "/certificate"), timeout=2) as response:
            self.assertEqual(response.read(), self.server.ca.read_bytes())
        self.server.set_running(True)
        with self.assertRaises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(self.server.check_url.replace("/check", "/frame"), data=self.jpeg, timeout=2)
        self.assertEqual(error.exception.code, 403)
        self.assertIsNone(self.server.take_frame())

    def test_cross_origin_post_rejected(self):
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.request("/frame", self.jpeg, extra={"Origin": "https://other.invalid"})
        self.assertEqual(error.exception.code, 403)

    def test_frames_wait_for_desktop_consent_and_clear_on_pause(self):
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.request("/frame", self.jpeg)
        self.assertEqual(error.exception.code, 409)
        self.server.set_running(True)
        with self.request("/frame", self.jpeg) as response:
            self.assertEqual(response.status, 202)
        self.assertEqual(self.server.take_frame()[0], self.jpeg)
        self.assertIsNone(self.server.take_frame())
        self.server.last_frame = 0
        with self.request("/frame", self.jpeg):
            pass
        self.server.set_running(False)
        self.assertIsNone(self.server.take_frame())
        self.assertFalse(any(Path(self.data.name).glob("*.jpg")))

    def test_invalid_and_excessive_payloads_rejected(self):
        self.server.set_running(True)
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.request("/frame", b"bad data")
        self.assertEqual(error.exception.code, 400)
        # A header-level rejection can close TLS before the client has finished
        # writing the oversized body. Both outcomes must reject the frame.
        try:
            self.request("/frame", b"x" * 350001)
        except urllib.error.HTTPError as error:
            self.assertEqual(error.code, 413)
        except urllib.error.URLError as error:
            self.assertIsInstance(error.reason, (ssl.SSLError, OSError))
        else:
            self.fail("Oversized frame was accepted")
        self.assertIsNone(self.server.take_frame())


if __name__ == "__main__":
    unittest.main()
