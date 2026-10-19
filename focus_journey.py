"""Local, durable progress and return points; the island owns the clock."""

from __future__ import annotations

import copy
import json
from hashlib import sha256
from datetime import datetime
from pathlib import Path
from uuid import uuid4


class FocusJourney:
    def __init__(self, path):
        self.path = Path(path)
        self.data = {"version": 1, "active": None, "checkpoint": None, "thoughts": [], "history": [], "forest": []}
        migrate_forest = False
        try:
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict) and loaded.get("version") == 1:
                for key in ("active", "checkpoint"):
                    self.data[key] = loaded.get(key) if isinstance(loaded.get(key), dict) else None
                migrate_forest = "forest" not in loaded
                for key in ("thoughts", "history", "forest"):
                    self.data[key] = [item for item in loaded.get(key, []) if isinstance(item, dict)] if isinstance(loaded.get(key), list) else []
        except (OSError, ValueError):
            pass
        self.data["forest"] = [tree for tree in self.data["forest"] if isinstance(tree.get("id"), str) and isinstance(tree.get("seed"), int)]
        self._tree_ids = {tree.get("id") for tree in self.data["forest"]}
        if migrate_forest:
            for record in self.data["history"]:
                self._plant(record)
            if self.active and self.active.get("status") == "review":
                self._plant(self.active)
            self.save()
        # A saved process cannot keep running after the process has exited.
        active = self.active
        if active and active.get("status") in ("work", "paused"):
            active.update(status="paused", recovered=True)
            self.save()

    @property
    def active(self):
        return self.data["active"]

    @staticmethod
    def now():
        return datetime.now().isoformat(timespec="seconds")

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.path)

    def begin(self, session, tasks, step="", preserve=False):
        if preserve and self.active:
            active = self.active
            active["elapsedBase"] = active.get("elapsedSeconds", 0)
            active["indexBase"] = active.get("index", 0)
            active["status"] = "work"
            active["recovered"] = False
        else:
            if self.active:
                self.finish(self.active.get("progress", ""), self.active.get("nextAction", ""), False)
            total = max(0, int(session.get("totalSeconds") or 0))
            active = {
                "id": uuid4().hex, "title": str(session.get("title") or ""),
                "step": str(step or session.get("title") or "").strip()[:1000],
                "taskId": session.get("taskId"), "mode": session.get("mode", "single"),
                "status": "work", "startedAt": self.now(), "progress": "", "nextAction": "",
                "elapsedSeconds": 0, "elapsedBase": 0, "remainingSeconds": total,
                "plannedSeconds": total, "index": 0, "indexBase": 0,
                "source": copy.deepcopy(session), "tasks": copy.deepcopy(tasks),
            }
            self.data["active"] = active
        self.data["checkpoint"] = None
        self.save()

    def snapshot(self, state, persist=True):
        active = self.active
        if not active or active.get("status") == "review":
            return
        if state.get("remaining") is not None:
            active["remainingSeconds"] = max(0, int(state["remaining"]))
        elif state.get("event") == "task":
            active["remainingSeconds"] = max(0, int(state.get("taskSeconds") or 0))
        active["index"] = int(active.get("indexBase", 0)) + int(state.get("index") or 0)
        active["elapsedSeconds"] = max(
            int(active.get("elapsedSeconds") or 0),
            int(active.get("elapsedBase") or 0) + int(state.get("completedFocusSeconds") or 0),
        )
        if state.get("event") == "paused" or state.get("running") is False:
            active["status"] = "paused"
        elif state.get("event") in ("resumed", "task", "started"):
            active["status"] = "work"
        if (active.get("mode") != "single" or active.get("source", {}).get("kind") == "guided") and state.get("title"):
            active["step"] = str(state["title"])
        if persist:
            self.save()

    def bookmark(self, progress, next_action):
        if not self.active:
            return False
        self.active.update(progress=str(progress).strip()[:4000], nextAction=str(next_action).strip()[:1000])
        self.save()
        return True

    def review(self, state, reason="timer"):
        self.snapshot(state, persist=False)
        if self.active:
            self.active.update(status="review", endReason=reason)
            self._plant(self.active)
            self.save()

    def _plant(self, record):
        """One permanent tree per completed session, independent of review saves."""
        try:
            seconds = int(record.get("elapsedSeconds") or 0)
        except (TypeError, ValueError):
            return False
        if record.get("endReason") not in ("timer", "step_done") or seconds <= 0:
            return False
        tree_id = str(record.get("id") or "legacy-" + sha256(json.dumps(record, sort_keys=True, ensure_ascii=False).encode()).hexdigest())
        if tree_id in self._tree_ids:
            return False
        self.data["forest"].append({"id": tree_id, "seed": self.tree_seed(tree_id), "seconds": seconds, "plantedAt": record.get("finishedAt") or self.now()})
        self._tree_ids.add(tree_id)
        return True

    @staticmethod
    def tree_seed(tree_id):
        return int(sha256(str(tree_id).encode()).hexdigest()[:8], 16)

    def capture(self, text):
        text = str(text).strip()[:2000]
        if not text:
            return False
        self.data["thoughts"].append({
            "id": uuid4().hex, "text": text, "createdAt": self.now(), "resolved": False,
            "stepId": self.active.get("id") if self.active else None,
        })
        # Never silently discard an unprocessed thought.
        self.save()
        return True

    def resolve(self, thought_id):
        for item in self.data["thoughts"]:
            if item.get("id") == thought_id:
                item["resolved"] = True
                self.save()
                return True
        return False

    def finish(self, progress, next_action, task_done=False):
        if not self.active or self.active.get("status") not in ("review", "paused"):
            return None
        self.bookmark(progress, next_action)
        record = copy.deepcopy(self.active)
        record.update(finishedAt=self.now(), taskDone=bool(task_done))
        record.pop("tasks", None)
        record.pop("source", None)
        self.data["history"] = (self.data["history"] + [record])[-500:]
        self.data["checkpoint"] = {
            "title": record["title"], "taskId": record.get("taskId"),
            "step": record["nextAction"], "progress": record["progress"],
            "plannedSeconds": record.get("plannedSeconds", 1500),
        } if record["nextAction"] and not task_done else None
        self.data["active"] = None
        self.save()
        return record

    def clear(self):
        self.data = {"version": 1, "active": None, "checkpoint": None, "thoughts": [], "history": [], "forest": []}
        self._tree_ids.clear()
        self.save()
