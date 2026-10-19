import unittest

from supervision_policy import SupervisionPolicy, held_phone, options, screen_evidence, upper_body


def config(**values):
    return options(dict(camera=True, cameraConsent=True, screen=True, screenConsent=True, **values))


class SupervisionTests(unittest.TestCase):
    def test_consent_required_for_each_selected_source(self):
        for data in ({"camera": True}, {"screen": True}, {}):
            with self.assertRaises(ValueError):
                options(data)
        self.assertTrue(options({"screen": True, "screenConsent": True})["screen"])
        self.assertFalse(options({"screen": True, "screenConsent": True})["camera"])

    def test_unknown_mode_and_strength_rejected(self):
        for values in ({"mode": "anything"}, {"sensitivity": "instant"}):
            with self.assertRaises(ValueError):
                config(**values)

    def test_upper_body_does_not_require_visible_legs(self):
        points = [{"x": .5, "y": .4, "visibility": 0} for _ in range(33)]
        for i in (0, 11, 12, 13, 14, 15, 16):
            points[i]["visibility"] = .9
        tracked, visible = upper_body(points)
        self.assertTrue(tracked)
        self.assertEqual(len(visible), 7)
        points[12]["visibility"] = .3
        self.assertFalse(upper_body(points)[0])

    def test_phone_on_desk_not_held(self):
        box = {"label": "cell phone", "score": .9, "x": .7, "y": .7, "w": .1, "h": .15}
        pose = [{"x": .1, "y": .1, "visibility": .9} for _ in range(33)]
        self.assertFalse(held_phone([box], pose))
        pose[15].update(x=.73, y=.76)
        self.assertTrue(held_phone([box], pose))
        pose[15]["visibility"] = .1
        self.assertFalse(held_phone([box], pose))

    def test_absence_needs_initial_person_and_clear_frame(self):
        p = SupervisionPolicy(config(), 0)
        absent = {"present": False, "observable": True}
        for t in range(13, 100):
            self.assertIsNone(p.camera(absent, t))
        p.camera({"present": True, "observable": True}, 100)
        for t in range(101, 136):
            self.assertIsNone(p.camera(absent, t))
        self.assertEqual(p.camera(absent, 136)["kind"], "away")
        p.reset_evidence()
        for t in range(240, 350):
            self.assertIsNone(p.camera(dict(absent, observable=False), t))

    def test_phone_learning_exempts_held_phone(self):
        p = SupervisionPolicy(config(mode="phone"), 0)
        for t in range(13, 100):
            self.assertIsNone(p.camera({"present": True, "observable": True, "heldPhone": True}, t))

    def test_phone_must_be_continuous(self):
        p = SupervisionPolicy(config(), 0)
        for t in range(13, 30):
            self.assertIsNone(p.observe("phone", True, t))
        p.observe("phone", False, 30)
        for t in range(31, 56):
            self.assertIsNone(p.observe("phone", True, t))
        self.assertEqual(p.observe("phone", True, 56)["kind"], "phone")

    def test_stalled_camera_never_counts_elapsed_gap(self):
        p = SupervisionPolicy(config(), 0)
        self.assertIsNone(p.observe("away", True, 13))
        self.assertIsNone(p.observe("away", True, 100))

    def test_cooldown_and_user_exemption(self):
        p = SupervisionPolicy(config(), 0)
        for t in range(13, 34):
            result = p.observe("screen", True, t)
        self.assertEqual(result["kind"], "screen")
        for t in range(34, 123):
            self.assertIsNone(p.observe("screen", True, t))
        p.exempt("screen", 123, 300)
        for t in range(123, 424):
            self.assertIsNone(p.observe("screen", True, t))
        self.assertEqual(p.alert_count, 1)

    def test_pause_discards_accumulated_suspicion(self):
        p = SupervisionPolicy(config(), 0)
        for t in range(13, 32):
            self.assertIsNone(p.observe("screen", True, t))
        p.reset_evidence()
        self.assertIsNone(p.observe("screen", True, 80))

    def test_ocr_keyword_and_app_rules_are_conservative(self):
        c = config()
        self.assertFalse(screen_evidence("chrome.exe", "物理资料", "光学公式", c)["suspect"])
        self.assertTrue(screen_evidence("chrome.exe", "主页", "抖音 热门短视频", c)["suspect"])
        self.assertFalse(screen_evidence("chrome.exe", "抖音", "抖音", c, allowed=True)["suspect"])
        self.assertEqual(screen_evidence("code.exe", "main.py", "print", c)["status"], "work")
        # IDE windows do not blindly whitelist entertainment content.
        self.assertTrue(screen_evidence("code.exe", "原神", "", c)["suspect"])
        self.assertEqual(screen_evidence("unknown.exe", "", "", c)["status"], "unknown")

    def test_sensitivity_changes_hold_time(self):
        strict = SupervisionPolicy(config(sensitivity="strict"), 0)
        gentle = SupervisionPolicy(config(sensitivity="gentle"), 0)
        for t in range(13, 26):
            a = strict.observe("screen", True, t)
            b = gentle.observe("screen", True, t)
        self.assertIsNotNone(a)
        self.assertIsNone(b)

    def test_personal_posture_alarms_at_five_seconds_for_every_strength(self):
        for strength in ("gentle", "normal", "strict"):
            p = SupervisionPolicy(config(sensitivity=strength), 0)
            p.last_alert = 0  # Another recent reminder must not delay this rule.
            for t in range(5):
                self.assertIsNone(p.observe("posture", True, t))
            self.assertEqual(p.observe("posture", True, 5)["kind"], "posture")
            self.assertEqual(p.alert_count, 1)

    def test_posture_recovery_unknown_and_stalled_samples_restart_five_seconds(self):
        for reset in ("recovered", "unknown", "stalled"):
            p = SupervisionPolicy(config(), 0)
            p.observe("posture", True, 0)
            p.observe("posture", True, 1)
            if reset == "recovered":
                p.observe("posture", False, 2)
            elif reset == "unknown":
                p.observe("posture", True, 2, valid=False)
            start = 10 if reset == "stalled" else 3
            for t in range(start, start + 5):
                self.assertIsNone(p.observe("posture", True, t))
            self.assertEqual(p.observe("posture", True, start + 5)["kind"], "posture")

    def test_explicit_posture_misjudgement_exemption_still_applies(self):
        p = SupervisionPolicy(config(), 0)
        p.exempt("posture", 0, 300)
        for t in range(10):
            self.assertIsNone(p.observe("posture", True, t))
        self.assertNotIn("posture", p.pending)


if __name__ == "__main__":
    unittest.main()
