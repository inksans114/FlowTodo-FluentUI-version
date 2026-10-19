"""Two user-labelled posture profiles. Stores feature numbers, never images."""
from __future__ import annotations

import math
import statistics

SAMPLES = 10


def clean(features):
    return {str(k): float(v) for k, v in features.items()
            if isinstance(v, (int, float)) and math.isfinite(v) and -3 <= v <= 3}


def profile(samples):
    keys = [key for key in samples[0] if sum(key in s for s in samples) >= len(samples) * .8]
    return {key: {"mean": statistics.mean(s[key] for s in samples if key in s),
                  "variance": statistics.pvariance(s[key] for s in samples if key in s)} for key in keys}


class PostureCalibration:
    def __init__(self):
        self.phase = "idle"
        self.samples = []
        self.learning = self.other = None
        self.started = 0
        self.message = "先记录你的学习姿势，再记录平时玩手机或游戏的姿势。"
        self.verdict = "unknown"
        self.reason = ""
        self.recent = []

    def state(self):
        return {"phase": self.phase, "count": len(self.samples), "target": SAMPLES,
                "hasLearning": self.learning is not None, "ready": self.phase == "ready",
                "message": self.message, "verdict": self.verdict, "reason": self.reason}

    def start(self, kind, now):
        if kind not in ("learning", "other"):
            raise ValueError("请选择学习姿态或非学习姿态。")
        if kind == "other" and self.learning is None:
            raise ValueError("请先记录学习姿态。")
        if kind == "learning":
            self.learning = self.other = None
        self.phase = kind
        self.samples = []
        self.started = now
        self.verdict = "unknown"
        self.reason = ""
        self.recent = []
        self.message = "保持你平时的" + ("学习" if kind == "learning" else "玩手机／游戏") + "姿势约 10 秒，不需要夸张摆拍。"

    def cancel(self):
        self.phase = "ready" if self.learning and self.other else "idle"
        self.samples = []
        self.verdict = "unknown"
        self.reason = ""
        self.recent = []
        self.message = "校准已取消，可以重新记录。"

    def observe(self, features, now):
        features = clean(features)
        if self.phase in ("learning", "other"):
            if now - self.started > 25:
                self.phase = "idle"
                self.samples = []
                self.message = "画面里的有效线索不够。请调整镜头，让脸或手清晰入镜，再重新记录。"
                return "unknown"
            if len(features) < 5:
                self.message = "还没有足够的姿态线索，请让脸或手进入画面。"
                return "unknown"
            self.samples.append(features)
            if len(self.samples) < SAMPLES:
                return "unknown"
            recorded = profile(self.samples)
            self.samples = []
            if self.phase == "learning":
                self.learning = recorded
                self.phase = "idle"
                self.message = "学习姿态记好了。接着记录你平时玩手机／游戏的样子。"
            else:
                common = set(recorded) & set(self.learning)
                distinct = [key for key in common if abs(recorded[key]["mean"] - self.learning[key]["mean"]) > .06]
                separation = statistics.mean((recorded[key]["mean"] - self.learning[key]["mean"]) ** 2 /
                    (recorded[key]["variance"] + self.learning[key]["variance"] + .0025) for key in common) if common else 0
                if len(common) < 5 or len(distinct) < 2 or separation < 1:
                    self.other = None
                    self.phase = "idle"
                    self.message = "两种姿态太相似，暂时无法可靠区分。可以调整镜头后重录；普通巡查仍可使用。"
                else:
                    self.other = recorded
                    self.phase = "ready"
                    self.message = "个人校准完成。非学习、姿态不稳定或偏离学习参考连续 5 秒会提醒；镜头移动后请重新校准。"
            return "unknown"
        if self.phase != "ready":
            return "unknown"
        common = set(features) & set(self.learning) & set(self.other)
        expected = set(self.learning) & set(self.other)
        if len(common) < 5 or len(common) < len(expected) * .7:
            self.verdict = "unknown"
            self.reason = ""
            self.recent = []
            return self.verdict
        # Compare recent visible motion with variation in the user's actual
        # learning samples. Ordinary recorded writing motion is the baseline.
        self.recent = [(t, f) for t, f in self.recent if 0 <= now - t <= 4][-2:]
        self.recent.append((now, features))
        moving = 0
        if len(self.recent) == 3:
            motion_keys = set.intersection(*(set(f) for _, f in self.recent)) & common
            for key in motion_keys:
                if not (key.endswith(("X", "Y")) or key in ("faceTilt", "handsSpread")):
                    continue
                values = [f[key] for _, f in self.recent]
                tolerance = max(.06, 3 * math.sqrt(self.learning[key]["variance"]))
                moving += max(values) - min(values) > tolerance
        unstable = moving >= 2
        def distance(recorded):
            return statistics.mean((features[k] - recorded[k]["mean"]) ** 2 /
                                   (recorded[k]["variance"] + .0025) for k in common)
        learning, other = distance(self.learning), distance(self.other)
        if unstable:
            self.verdict, self.reason = "other", "unstable"
        elif min(learning, other) > 9 or abs(learning - other) < 1:
            self.verdict, self.reason = "other", "unmatched"
        else:
            self.verdict = "learning" if learning < other else "other"
            self.reason = ""
        return self.verdict
