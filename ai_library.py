"""Local saved AI plans and independent resumable copies. Never calls a model."""
from __future__ import annotations

import copy
import json
import re
import os
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from uuid import uuid4


def now():
    return datetime.now().isoformat(timespec="seconds")


def write_state(path, state):
    """A failed write must leave the previous complete JSON intact."""
    target = Path(path)
    temporary = target.with_name(target.name + "." + uuid4().hex + ".tmp")
    try:
        temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def valid_id(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{32}", value) is not None


def find(state, plan_id):
    return next((record for record in state.get("savedPlans", [])
                 if isinstance(record, dict) and record.get("id") == plan_id), None)


def title(plan):
    name = str(plan.get("title") or "")
    if not name or name in ("AI 个性化计划", "AI 生成计划"):
        name = str((plan.get("guidance") or {}).get("goal") or plan.get("captureOriginal") or "已保存方案")
    return name.splitlines()[0][:100]


def remember(state, plan, path="", created_at=None):
    plan_id = plan.get("libraryId")
    if not valid_id(plan_id):
        plan_id = uuid4().hex
        plan["libraryId"] = plan_id
    record = find(state, plan_id)
    if plan.get("capturePhase") == "continue":
        if record:
            record["lastResponse"] = {key: copy.deepcopy(plan.get(key)) for key in ("summary", "questions", "guidance")}
            record["updatedAt"] = now()
        return record
    if record is None:
        record = {"id": plan_id, "createdAt": created_at or now(), "originalPlan": copy.deepcopy(plan), "journey": None}
        state.setdefault("savedPlans", []).append(record)
    record.update(title=title(plan), plan=copy.deepcopy(plan), path=path,
                  updatedAt=now(), kind="capture" if plan.get("captureMode") else "long" if plan.get("mode") == "long" else "short")
    record["draft"] = {"original": str(plan.get("captureOriginal") or ""), "drafts": copy.deepcopy(plan.get("tasks", [])),
                       "answerTexts": [], "editOriginal": not bool(plan.get("guidance") or plan.get("questions")), "showDrafts": False}
    state["selectedAiPlanId"] = plan_id
    return record


def snapshot(state, journey):
    if not journey:
        return False
    record = find(state, journey.get("source", {}).get("libraryId"))
    if not record:
        return False
    record["journey"] = copy.deepcopy(journey)
    if journey.get("source", {}).get("guidance"):
        record["plan"]["guidance"] = copy.deepcopy(journey["source"]["guidance"])
    record["updatedAt"] = now()
    return True


def summaries(state):
    result = []
    for record in state.get("savedPlans", []):
        if not isinstance(record, dict) or not valid_id(record.get("id")) or not isinstance(record.get("plan"), dict):
            continue
        plan, journey = record["plan"], record.get("journey") or {}
        status = journey.get("status") or ("questions" if plan.get("questions") else "imported" if plan.get("captureImported") or plan.get("ecosystemImported")
            else "incomplete" if record.get("kind") == "capture" and plan.get("tasks") and not plan.get("guidance") else "ready")
        result.append({key: record.get(key, "") for key in ("id", "title", "kind", "createdAt", "updatedAt")})
        result[-1].update(status=status, step=journey.get("step", ""), seconds=journey.get("elapsedSeconds", 0),
                          resumable=bool(journey.get("source", {}).get("kind") == "guided" and status in ("work", "paused")),
                          hasGuidance=bool(plan.get("guidance")))
    return sorted(result, key=lambda item: item["updatedAt"], reverse=True)


def duplicate(state, plan_id):
    record = find(state, plan_id)
    if not record:
        raise ValueError("这个方案暂时找不到了。")
    plan = copy.deepcopy(record["plan"])
    plan.update(libraryId=uuid4().hex, title=str(record["title"])[:95] + " · 副本")
    plan.pop("captureImported", None)
    new = remember(state, plan)
    new["copiedFrom"] = record["id"]
    new["draft"] = copy.deepcopy(record.get("draft") or new["draft"])
    new["messages"] = copy.deepcopy(record.get("messages", []))
    if not new["draft"].get("drafts") and plan.get("tasks"):
        new["draft"]["drafts"] = copy.deepcopy(plan["tasks"])
    # Copies have their own ID and draft; they cannot mutate or resume the original clock.
    return new


def migrate(state, directory):
    """Recover old result files once; existing records and originals are never removed."""
    if state.get("savedPlansMigration") == 1:
        return False
    if not isinstance(state.get("savedPlans"), list):
        state["savedPlans"] = []
    selected = state.get("selectedAiPlanId")
    latest = state.get("latestPlan")
    for path in sorted(Path(directory).glob("ai-plan-*.json")):
        try:
            plan = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(plan, dict) or not isinstance(plan.get("tasks"), list) or plan.get("capturePhase") == "continue":
                continue
            if not valid_id(plan.get("libraryId")):
                plan["libraryId"] = sha256(path.name.encode()).hexdigest()[:32]
            if not find(state, plan["libraryId"]):
                remember(state, plan, str(path), datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds"))
        except (OSError, ValueError, TypeError):
            continue
    if isinstance(latest, dict) and latest.get("capturePhase") != "continue":
        if not valid_id(latest.get("libraryId")):
            matching = next((record for record in state["savedPlans"] if record.get("path") == state.get("latestPath")), None)
            latest["libraryId"] = matching["id"] if matching else uuid4().hex
        if not find(state, latest["libraryId"]):
            remember(state, latest, state.get("latestPath", ""))
        else:
            record = find(state, latest["libraryId"])
            record["plan"] = copy.deepcopy(latest)
            if latest.get("captureImported"):
                record["draft"]["drafts"] = []
        if latest.get("captureMode") and state.get("captureDraftInput"):
            state["captureDraftPlanId"] = latest["libraryId"] if state["captureDraftInput"] == latest.get("captureOriginal") else uuid4().hex
        selected = latest["libraryId"]
    if selected:
        state["selectedAiPlanId"] = selected
    state["savedPlansMigration"] = 1
    return True
