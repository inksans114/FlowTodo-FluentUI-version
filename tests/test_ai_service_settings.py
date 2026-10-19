import json
import unittest

from ai_service_settings import public_settings, switch_service


class ServiceSettingsTests(unittest.TestCase):
    def setUp(self):
        self.settings = {"aiApiKey": "fake-test-secret", "aiBaseUrl": "https://test.invalid/v1",
                         "aiModel": "test-model", "language": "zh_CN"}

    def test_default_connection_is_not_exposed(self):
        public = public_settings(self.settings)
        self.assertNotIn("aiApiKey", public)
        self.assertNotIn("aiBaseUrl", public)
        self.assertEqual(public["aiModel"], "test-model")
        self.assertEqual(self.settings["aiApiKey"], "fake-test-secret")

    def test_switch_preserves_both_connections_and_model_edits(self):
        custom = switch_service(self.settings, "custom")
        self.assertEqual(custom["aiApiKey"], "")
        custom.update(aiApiKey="fake-custom-secret", aiBaseUrl="https://custom.invalid/v1", aiModel="custom-model")
        self.assertNotIn("fake-test-secret", json.dumps(public_settings(custom)))
        default = switch_service(custom, "default")
        self.assertEqual(default["aiApiKey"], "fake-test-secret")
        default["aiModel"] = "another-test-model"
        self.assertNotIn("fake-custom-secret", json.dumps(public_settings(default)))
        restored = switch_service(default, "custom")
        self.assertEqual(restored["aiApiKey"], "fake-custom-secret")
        self.assertEqual(restored["aiModel"], "custom-model")
        self.assertEqual(switch_service(restored, "default")["aiModel"], "another-test-model")

    def test_same_mode_does_not_clear_connection(self):
        self.assertEqual(switch_service(self.settings, "default"), self.settings)

    def test_invalid_mode_is_rejected(self):
        with self.assertRaises(ValueError):
            switch_service(self.settings, "invalid")


if __name__ == "__main__":
    unittest.main()
