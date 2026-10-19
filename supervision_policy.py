"""Local supervision decisions. Evidence is approximate, never a study verdict."""
from __future__ import annotations

import math

MODES = {"homework", "code", "reading", "phone"}
THRESHOLDS = {"gentle": {"away": 60, "phone": 45, "screen": 40, "posture": 5},
              "normal": {"away": 35, "phone": 25, "screen": 20, "posture": 5},
              "strict": {"away": 20, "phone": 15, "screen": 12, "posture": 5}}
DEFAULT_BLOCKED = "抖音,快手,微博热搜,王者荣耀,原神,英雄联盟,steam"
WORK_APPS = {"code.exe", "pycharm64.exe", "idea64.exe", "devenv.exe", "notepad.exe",
             "notepad++.exe", "winword.exe", "excel.exe", "powerpnt.exe", "wps.exe"}
GAMES = {"steam.exe", "league of legends.exe", "genshinimpact.exe", "valorant-win64-shipping.exe"}


def options(value):
    if not isinstance(value, dict):
        raise ValueError("监督设置格式不正确。")
    mode = str(value.get("mode", "homework"))
    sensitivity = str(value.get("sensitivity", "normal"))
    if mode not in MODES or sensitivity not in THRESHOLDS:
        raise ValueError("请选择有效的学习方式和提醒强度。")
    camera, screen = value.get("camera") is True, value.get("screen") is True
    if not camera and not screen:
        raise ValueError("请至少开启摄像头或屏幕巡查。")
    if camera and value.get("cameraConsent") is not True:
        raise ValueError("请确认本次允许使用摄像头。")
    if screen and value.get("screenConsent") is not True:
        raise ValueError("请确认本次允许读取当前窗口与可见画面。")
    keywords = str(value.get("blockedKeywords", DEFAULT_BLOCKED)).strip()
    if len(keywords) > 600:
        raise ValueError("提醒关键词请控制在 600 字以内。")
    source = str(value.get("cameraSource", "computer"))
    if source not in ("computer", "phone"):
        raise ValueError("请选择电脑或手机摄像头。")
    return {"mode": mode, "sensitivity": sensitivity, "camera": camera, "screen": screen, "cameraSource": source,
            "cameraId": str(value.get("cameraId", ""))[:512], "blockedKeywords": keywords,
            "sound": value.get("sound", True) is True}


def upper_body(landmarks):
    """Keep only confident visible landmarks; lower limbs are not required."""
    visible = {i: p for i, p in enumerate(landmarks[:25])
               if p.get("visibility", 0) >= .55 and 0 <= p.get("x", -1) <= 1 and 0 <= p.get("y", -1) <= 1}
    tracked = 11 in visible and 12 in visible and any(i in visible for i in (0, 13, 14, 15, 16))
    points = [{"index": i, "x": p["x"], "y": p["y"]} for i, p in visible.items() if i <= 22]
    return tracked, points


def held_phone(boxes, landmarks):
    # A phone lying on a desk does not count. Require a visible wrist nearby.
    wrists = [p for p in landmarks[15:17] if p.get("visibility", 0) >= .55]
    for box in boxes:
        if box.get("label") != "cell phone" or box.get("score", 0) < .55:
            continue
        x, y, w, h = (box[k] for k in ("x", "y", "w", "h"))
        margin = min(.09, max(.035, max(w, h) * .45))
        if any(x - margin <= p["x"] <= x + w + margin and y - margin <= p["y"] <= y + h + margin for p in wrists):
            return True
    return False


def eye_direction(landmarks):
    """A rough iris direction cue, never a verdict about attention or learning."""
    if len(landmarks) < 478:
        return "unknown"
    directions = []
    for outer, inner, top, bottom, iris in ((33, 133, 159, 145, 468), (362, 263, 386, 374, 473)):
        a, b, t, d, p = (landmarks[i] for i in (outer, inner, top, bottom, iris))
        dx, dy = b["x"] - a["x"], b["y"] - a["y"]
        width = math.hypot(dx, dy)
        if width < .015:
            return "unknown"
        height = abs((d["y"] - t["y"]) * dx - (d["x"] - t["x"]) * dy) / width
        if height < width * .1:
            return "unknown"  # Blinking or a poor angle is not loss of attention.
        horizontal = ((p["x"] - a["x"]) * dx + (p["y"] - a["y"]) * dy) / width ** 2
        vertical = ((p["y"] - t["y"]) * dx - (p["x"] - t["x"]) * dy) / (width * height)
        directions.append((horizontal, vertical))
    if all(h < .22 for h, v in directions) or all(h > .78 for h, v in directions):
        return "side"
    if all(v > .72 for h, v in directions):
        return "down"
    return "front"


def screen_evidence(process, title, text, config, allowed=False):
    process = str(process).lower()
    if allowed:
        return {"status": "allowed", "label": "已允许当前内容", "suspect": False}
    needles = [s.strip().lower() for s in config["blockedKeywords"].replace("，", ",").split(",") if s.strip()]
    content = (str(title)[:500] + "\n" + str(text)[:6000]).lower()
    hit = next((s for s in needles if s in content), "")
    if hit or process in GAMES:
        return {"status": "suspect", "label": "疑似娱乐内容，等待确认", "suspect": True,
                "reason": "当前画面出现了提醒关键词" if hit else "当前应用可能是游戏"}
    if process in WORK_APPS:
        return {"status": "work", "label": "学习／工作应用在前台", "suspect": False}
    return {"status": "unknown", "label": "未发现明确异常，不能确认学习内容", "suspect": False}


class SupervisionPolicy:
    def __init__(self, config, started):
        self.config = config
        self.started = started
        self.seen_person = False
        self.pending = {}
        self.last_sample = {}
        self.last_alert = -math.inf
        self.exempt_until = {}
        self.alert_count = 0

    def reset_evidence(self):
        self.pending.clear()
        self.last_sample.clear()

    def exempt(self, kind, now, seconds=300):
        self.exempt_until[kind] = now + seconds
        self.pending.pop(kind, None)

    def observe(self, kind, anomalous, now, valid=True):
        """Require repeated, recent evidence; a stalled camera is not absence."""
        # User-calibrated posture has its own five-second rule. Neither the
        # startup grace nor another detector's cooldown may silently delay it.
        if not valid or not anomalous or now < self.exempt_until.get(kind, 0) or (kind != "posture" and now - self.started < 12):
            self.pending.pop(kind, None)
            self.last_sample[kind] = now
            return None
        max_gap = 20 if kind == "screen" else 5
        if now - self.last_sample.get(kind, now) > max_gap:
            self.pending.pop(kind, None)
        self.last_sample[kind] = now
        self.pending.setdefault(kind, now)
        if now - self.pending[kind] < THRESHOLDS[self.config["sensitivity"]][kind] or (kind != "posture" and now - self.last_alert < 90):
            return None
        self.last_alert = now
        self.alert_count += 1
        self.reset_evidence()
        return {"kind": kind, "count": self.alert_count}

    def camera(self, evidence, now):
        if evidence.get("present"):
            self.seen_person = True
        valid = evidence.get("observable") is True
        away = self.observe("away", not evidence.get("present") and self.seen_person, now, valid)
        phone = self.observe("phone", evidence.get("heldPhone") is True and self.config["mode"] != "phone", now, valid)
        return away or phone
