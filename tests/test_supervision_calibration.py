import unittest

from supervision_calibration import PostureCalibration
from supervision_policy import SupervisionPolicy, eye_direction, options


def sample(value):
    return {"handsVisible": 1, "faceVisible": 1, "phoneVisible": 0,
            "headY": value, "handsCenterY": value, "headX": .4, "eyesY": value}


class CalibrationTests(unittest.TestCase):
    def record(self, calibration, kind, value, start):
        calibration.start(kind, start)
        for i in range(10):
            calibration.observe(sample(value + i * .0001), start + i)

    def test_user_labelled_postures_and_uncertain_new_pose(self):
        c = PostureCalibration()
        self.record(c, "learning", .2, 0)
        self.record(c, "other", .7, 20)
        self.assertTrue(c.state()["ready"])
        self.assertEqual(c.observe(sample(.2), 35), "learning")
        self.assertEqual(c.observe(sample(.7), 36), "other")
        self.assertEqual(c.observe(sample(.45), 37), "other")
        self.assertEqual(c.observe({"headY": .7}, 38), "unknown")

    def test_unstable_visible_motion_counts_as_other_then_stable_learning_recovers(self):
        c = PostureCalibration()
        self.record(c, "learning", .2, 0)
        self.record(c, "other", .7, 20)
        c.observe(sample(.16), 40)
        c.observe(sample(.24), 41)
        self.assertEqual(c.observe(sample(.16), 42), "other")
        self.assertEqual(c.state()["reason"], "unstable")
        for t in range(43, 46):
            verdict = c.observe(sample(.2), t)
        self.assertEqual(verdict, "learning")
        self.assertEqual(c.reason, "")

    def test_unmatched_clear_posture_triggers_existing_five_second_alarm(self):
        c = PostureCalibration()
        self.record(c, "learning", .2, 0)
        self.record(c, "other", .7, 20)
        p = SupervisionPolicy(options({"camera": True, "cameraConsent": True}), 40)
        for t in range(40, 46):
            verdict = c.observe(sample(.45), t)
            self.assertEqual(verdict, "other")
            self.assertEqual(c.reason, "unmatched")
            alert = p.observe("posture", verdict == "other", t, verdict != "unknown")
            if t < 45:
                self.assertIsNone(alert)
        self.assertEqual(alert["kind"], "posture")

    def test_continuous_unstable_motion_alarms_after_five_seconds(self):
        c = PostureCalibration()
        self.record(c, "learning", .2, 0)
        self.record(c, "other", .7, 20)
        p = SupervisionPolicy(options({"camera": True, "cameraConsent": True}), 40)
        for t in range(40, 48):
            verdict = c.observe(sample(.16 if t % 2 == 0 else .24), t)
            alert = p.observe("posture", verdict == "other", t, verdict != "unknown")
            if t >= 42:
                self.assertEqual(c.reason, "unstable")
            if t < 47:
                self.assertIsNone(alert)
        self.assertEqual(alert["kind"], "posture")

    def test_missing_or_stale_frames_cannot_establish_unstable_motion(self):
        c = PostureCalibration()
        self.record(c, "learning", .2, 0)
        self.record(c, "other", .7, 20)
        c.observe(sample(.16), 40)
        c.observe(sample(.24), 41)
        self.assertEqual(c.observe({}, 42), "unknown")
        self.assertEqual(c.observe(sample(.16), 43), "learning")
        c.observe(sample(.24), 44)
        self.assertEqual(c.observe(sample(.16), 60), "learning")

    def test_similar_examples_must_not_claim_accuracy(self):
        c = PostureCalibration()
        self.record(c, "learning", .2, 0)
        self.record(c, "other", .21, 20)
        self.assertFalse(c.state()["ready"])
        self.assertIn("太相似", c.message)

    def test_needs_both_user_labels_and_visible_features(self):
        c = PostureCalibration()
        with self.assertRaises(ValueError):
            c.start("other", 0)
        c.start("learning", 0)
        for i in range(10):
            c.observe({}, i)
        self.assertFalse(c.state()["hasLearning"])
        c.observe({}, 30)
        self.assertEqual(c.phase, "idle")

    def test_cancel_drops_pending_samples_and_recalibrate_resets_profiles(self):
        c = PostureCalibration()
        self.record(c, "learning", .2, 0)
        self.record(c, "other", .7, 20)
        c.start("learning", 40)
        self.assertIsNone(c.other)
        c.observe(sample(.2), 41)
        c.cancel()
        self.assertEqual(c.samples, [])
        self.assertFalse(c.state()["ready"])

    def test_missing_eye_landmarks_are_unknown(self):
        self.assertEqual(eye_direction([]), "unknown")
        self.assertEqual(eye_direction([{"x": 0, "y": 0} for _ in range(478)]), "unknown")


if __name__ == "__main__":
    unittest.main()
