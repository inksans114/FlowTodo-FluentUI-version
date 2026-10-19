"""Reversible expiry for ordinary, unfinished tasks in the existing task file."""
from datetime import datetime, timedelta


def archive_expired(tasks, days, now=None, protected_ids=()):
    now = now or datetime.now()
    try:
        days = int(days)
    except (TypeError, ValueError):
        days = 0
    if days not in (3, 7, 14):
        return False
    protected_ids = {str(value) for value in protected_ids}
    changed = False
    for task in tasks:
        if (task.get("archivedAt") or task.get("done")
                or task.get("taskType", "normal") != "normal"
                or str(task.get("id")) in protected_ids
                or task.get("_source") == "ai"
                or any(task.get(key) for key in ("projectId", "groupId", "longPlanId", "longTerm", "isLongTerm", "special", "isSpecial", "pinned"))):
            continue
        stamp = task.get("updatedAt") or task.get("createdAt") or task.get("archiveClockStartedAt")
        if not stamp:
            task["archiveClockStartedAt"] = now.isoformat(timespec="seconds")
            changed = True
            continue
        try:
            started = datetime.fromisoformat(str(stamp)).replace(tzinfo=None)
        except ValueError:
            # Unknown legacy timestamps get a fresh grace period.
            task["updatedAt"] = now.isoformat(timespec="seconds")
            changed = True
            continue
        future = str(task.get("deadline") or task.get("dueDate") or task.get("scheduledDate") or "")[:10]
        if future > now.date().isoformat():
            continue
        if now - started >= timedelta(days=days):
            task["archivedAt"] = now.isoformat(timespec="seconds")
            task["archiveReason"] = "expired"
            changed = True
    return changed


def referenced_task_ids(value):
    result = set()
    if isinstance(value, dict):
        if value.get("taskId") is not None:
            result.add(str(value["taskId"]))
        result.update(str(item) for item in (value.get("taskIds") or []) if not isinstance(item, (dict, list)))
        for key, child in value.items():
            if key == "tasks" and isinstance(child, list):
                result.update(str(item["id"]) for item in child if isinstance(item, dict) and "id" in item)
            result.update(referenced_task_ids(child))
    elif isinstance(value, list):
        for child in value:
            result.update(referenced_task_ids(child))
    return result
