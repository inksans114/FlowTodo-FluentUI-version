"""Local identity and Free trial request allowance (no timed reset)."""
from __future__ import annotations

import copy
import json
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4


def token_count(usage):
    if not isinstance(usage, dict):
        return None
    total = usage.get("total_tokens")
    if isinstance(total, int) and not isinstance(total, bool) and total >= 0:
        return total
    values = [usage.get("prompt_tokens"), usage.get("completion_tokens")]
    if all(isinstance(n, int) and not isinstance(n, bool) and n >= 0 for n in values):
        return sum(values)
    return None


class AccountState:
    FREE_REQUESTS = 5

    def __init__(self, path):
        self.path = Path(path)
        self.lock = threading.RLock()
        self._pending_default = 0
        self.data = {"version": 1, "id": uuid4().hex, "name": "专注探索者",
                     "createdAt": datetime.now(timezone.utc).isoformat(),
                     "totalTokens": 0, "totalRequests": 0, "unreportedRequests": 0, "events": [],
                     "defaultTokens": 0, "defaultRequests": 0, "defaultHistoryIncomplete": False, "avatarRevision": ""}
        try:
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict) and loaded.get("version") == 1:
                for key in ("id", "name", "createdAt"):
                    if isinstance(loaded.get(key), str) and loaded[key]:
                        self.data[key] = loaded[key]
                for key in ("totalTokens", "totalRequests", "unreportedRequests"):
                    value = loaded.get(key)
                    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                        self.data[key] = value
                self.data["events"] = [item for item in loaded.get("events", [])
                                       if isinstance(item, dict) and isinstance(item.get("at"), str)] if isinstance(loaded.get("events"), list) else []
                for key in ("defaultTokens", "defaultRequests"):
                    value = loaded.get(key)
                    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                        self.data[key] = value
                    else:
                        defaults = [e for e in self.data["events"] if e.get("service") == "default"]
                        self.data[key] = len(defaults) if key == "defaultRequests" else sum(
                            e["tokens"] for e in defaults if isinstance(e.get("tokens"), int) and not isinstance(e["tokens"], bool) and e["tokens"] >= 0)
                self.data["defaultHistoryIncomplete"] = bool(loaded.get("defaultHistoryIncomplete", self.data["totalRequests"] > len(self.data["events"])))
                revision = loaded.get("avatarRevision", "")
                if isinstance(revision, str):
                    self.data["avatarRevision"] = revision
        except (OSError, ValueError):
            pass
        self._save()

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.path)

    def rename(self, name):
        name = str(name).strip()
        if not name or len(name) > 40:
            raise ValueError("昵称请填写 1–40 个字符。")
        with self.lock:
            self.data["name"] = name
            self._save()

    def set_avatar_revision(self, revision):
        with self.lock:
            self.data["avatarRevision"] = str(revision)
            self._save()

    def begin_request(self, service):
        """Reserve a local trial slot so concurrent calls cannot exceed five."""
        if service in ("custom", "official"):
            return
        with self.lock:
            if self.data["defaultRequests"] + self._pending_default >= self.FREE_REQUESTS:
                raise RuntimeError("Free 版的 5 次 AI 使用次数已用完，请在 AI 服务中接入自己的 API。")
            self._pending_default += 1

    def end_request(self, service):
        if service == "default":
            with self.lock:
                self._pending_default = max(0, self._pending_default - 1)

    def record(self, usage, service, now=None):
        now = now or datetime.now(timezone.utc)
        tokens = token_count(usage)
        with self.lock:
            self.data["totalRequests"] += 1
            if service == "default":
                self.data["defaultRequests"] += 1
                if tokens is not None:
                    self.data["defaultTokens"] += tokens
            if tokens is None:
                self.data["unreportedRequests"] += 1
            else:
                self.data["totalTokens"] += tokens
            self.data["events"].append({"at": now.isoformat(), "tokens": tokens,
                                         "service": service if service in ('custom','official') else "default"})
            # Keep the rolling seven-day window; lifetime counters are independent.
            cutoff = now - timedelta(days=7)
            retained = []
            for event in self.data["events"]:
                try:
                    at = datetime.fromisoformat(event["at"])
                    if at.tzinfo is not None and cutoff <= at <= now:
                        retained.append(event)
                except (TypeError, ValueError):
                    continue
            self.data["events"] = retained
            self._save()

    def snapshot(self, service="default", now=None):
        with self.lock:
            data = copy.deepcopy(self.data)
        custom = service == "custom"
        used = data["totalRequests"] - data["defaultRequests"] if custom else data["defaultRequests"]
        remaining = max(0, self.FREE_REQUESTS - used)
        usage = {"title": "AI 使用次数", "used": max(0, used),
                 "limit": None if custom else self.FREE_REQUESTS,
                 "remaining": None if custom else remaining,
                 "remainingFraction": None if custom else remaining / self.FREE_REQUESTS,
                 "historyIncomplete": data["defaultHistoryIncomplete"],
                 "status": "provider" if custom else "exhausted" if remaining == 0 else "available"}
        return {"name": data["name"], "initials": data["name"][:2].upper(),
                "handle": "@" + data["id"][:12], "local": True,
                "plan": "自定义 API" if custom else "Free",
                "service": service, "totalTokens": data["totalTokens"],
                "totalRequests": data["totalRequests"], "unreportedRequests": data["unreportedRequests"],
                "avatarRevision": data["avatarRevision"], "usage": usage}
