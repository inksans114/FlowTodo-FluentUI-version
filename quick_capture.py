"""Small, independent quick-entry parsing; optional AI never plans a day."""
from __future__ import annotations

import json
import re
from hashlib import sha256

CATEGORIES = ("其他", "学习", "工作", "生活")
MAX_INPUT = 6000
MAX_TASKS = 100
PROMPT = ('你是待办记录员。只把用户明确要做的事分成独立待办，并分类为学习、工作、生活或其他。'
          '保留数量、日期与最后的纠正，排除明确取消的事项。不要拆成执行步骤、安排专注、安慰、提问或添加用户没说的事项。'
          '标题简短但保留关键信息。只返回JSON：{"tasks":[{"title":"待办","category":"生活"}]}。不输出其他字段。')


def local_tasks(text):
    if not isinstance(text, str) or len(text) > MAX_INPUT:
        raise ValueError("一次最多记录 6000 字，请分批记下。")
    parts = re.split(r"[\r\n；;。]+", text)
    tasks = []
    for part in parts:
        title = re.sub(r"^\s*(?:[-*•]\s+|\d+[、.)）]\s*)", "", part).strip()
        if title:
            tasks.append({"title": title, "category": "其他"})
    return validate_tasks(tasks)


def validate_tasks(tasks, allow_skip=False):
    if not isinstance(tasks, list) or len(tasks) > MAX_TASKS:
        raise ValueError("一次最多记录 100 件事，请分批记下。")
    clean = []
    for item in tasks:
        if not isinstance(item, dict) or not isinstance(item.get("title"), str):
            raise ValueError("待办格式不完整，请检查后再记下。")
        title = item["title"].strip()
        if not title or len(title) > 400:
            raise ValueError("每件事需要 1–400 字；长描述可以换行拆开，或选择 AI 整理。")
        category = item.get("category", "其他")
        if category not in CATEGORIES:
            raise ValueError("请选择学习、工作、生活或其他分类。")
        task = {"title": title, "category": category}
        if allow_skip:
            task["_skip"] = bool(item.get("_skip"))
        clean.append(task)
    return clean


def ai_tasks(call, text):
    if not isinstance(text, str) or not text.strip() or len(text) > 4000:
        raise ValueError("AI 快速整理一次最多 4000 字，请分批输入；直接记录无需 AI。")
    # One explicit request; no history, existing tasks, user profile, guided
    # planning or automatic repair calls. Failure leaves the local draft intact.
    reply = call([{"role": "system", "content": PROMPT}, {"role": "user", "content": text}],
                 long_mode=False, output_limit=1600)
    raw = json.loads(reply.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip())
    if not isinstance(raw, dict) or set(raw) != {"tasks"}:
        raise ValueError("AI 未返回待办清单，原话已保留，可以直接记录。")
    tasks = validate_tasks(raw["tasks"])
    if not tasks:
        raise ValueError("没有整理出待办，原话已保留。")
    return tasks


def fingerprint(tasks):
    return sha256(json.dumps(tasks, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
