"""Contracts for small AI planning windows, not a fixed five-minute routine."""
import copy


def validate_progress(value):
    if not isinstance(value, dict):
        raise ValueError("请说明当前进度。")
    result = {key: _text(value.get(key, ""), limit, "进度", required=False)
              for key, limit in (("subject", 60), ("paper", 80), ("section", 60), ("position", 120), ("note", 700))}
    if not any(result.values()):
        raise ValueError("先写一句你正在做什么，再告诉 AI。")
    return result


def validate_replies(value, questions):
    if not isinstance(value, list) or len(value) != len(questions) or len(value) > 3:
        raise ValueError("请回答当前这些问题。")
    return [{"question": question["question"], "answer": _text(answer, 500, "回答", required=False)}
            for question, answer in zip(questions, value)]


def _text(value, limit, name, required=True):
    if not isinstance(value, str) or len(value) > limit or (required and not value.strip()):
        raise ValueError(f"AI 返回的{name}无效，请重新准备这一段。")
    return value.strip()


def validate_questions(value):
    if not isinstance(value, list) or len(value) > 3:
        raise ValueError("一次最多澄清三个问题，请重新准备。")
    result = []
    for question in value:
        if not isinstance(question, dict):
            raise ValueError("AI 返回的问题格式无效。")
        choices = question.get("choices", [])
        if not isinstance(choices, list) or len(choices) > 4:
            raise ValueError("AI 返回的问题选项过多。")
        result.append({"question": _text(question.get("question"), 150, "问题"),
                       "choices": [_text(choice, 80, "选项") for choice in choices]})
        if question.get("field") in ("subject", "paper", "section", "position"):
            result[-1]["field"] = question["field"]
    return result


def validate_guidance(value):
    from i18n_runtime import tr
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("AI 返回的引导格式无效。")
    steps = value.get("steps")
    if not isinstance(steps, list) or not 1 <= len(steps) <= 3:
        raise ValueError("引导一次只需准备一到三小段，避免内容过长。")
    result = {"goal": _text(value.get("goal"), 400, "目标"),
              "intro": _text(value.get("intro"), 240, "回应"),
              "style": value.get("style", "auto"), "steps": []}
    if result["style"] not in ("chunks", "whole", "auto"):
        raise ValueError("AI 返回的推进偏好无效。")
    for key, default in (("breakMinutes", 3), ("restAfterMinutes", 40)):
        number = value.get(key, default)
        maximum = 30 if key == "breakMinutes" else 90
        if isinstance(number, bool) or not isinstance(number, int) or not 1 <= number <= maximum:
            raise ValueError("AI 返回的休息建议无效。")
        result[key] = number
    for step in steps:
        if not isinstance(step, dict):
            raise ValueError("AI 返回的当前动作无效。")
        kind = step.get("type", "focus")
        minutes = step.get("minutes")
        if kind not in ("focus", "break") or isinstance(minutes, bool) or not isinstance(minutes, int) or not 1 <= minutes <= (30 if kind == "break" else 90):
            raise ValueError("AI 返回的时间建议无效。")
        result["steps"].append({"title": _text(step.get("title"), 100, "动作"),
                                "detail": _text(step.get("detail"), 240, "做法"),
                                "minutes": minutes, "type": kind,
                                "encouragement": _text(step.get("encouragement", tr("这一小段确实推进了。")), 160, "完成回应")})
    return result


def island_tasks(guidance):
    return [{"title": step["title"], "subtitle": step["detail"], "type": step["type"],
             "time": step["minutes"] * 60, "encouragement": step["encouragement"]}
            for step in validate_guidance(guidance)["steps"]]


def rest_task(guidance):
    from i18n_runtime import tr
    return {"title": tr("离开作业，缓一缓"), "subtitle": tr("可以喝口水、活动一下，或看看窗外。休息结束后，准备好了再继续。"),
            "type": "break", "time": guidance["breakMinutes"] * 60}


def continuation_context(source, current, state, feedback):
    guide = source.get("guidance") or {}
    return {"goal": guide.get("goal", ""), "style": guide.get("style", "auto"),
            "originalIntent": source.get("captureFacts", ""),
            "completedActions": list(source.get("completedActions", []))[-20:],
            "answers": [{"question": str(item.get("question", ""))[:150], "answer": str(item.get("answer", ""))[:250]}
                        for item in source.get("captureAnswers", [])[-9:]],
            "reportedProgress": copy.deepcopy(source.get("reportedProgress", {})),
            "recentProgress": [{key: str(value)[:160] for key, value in report.items()}
                               for report in source.get("progressReports", [])[-3:]],
            "tasks": [str(item.get("title", ""))[:160] for item in source.get("captureTasks", [])[:8]],
            "currentAction": current.get("title", ""), "currentDetail": current.get("subtitle", ""),
            "actualMinutes": max(0, int(state.get("taskSeconds", 0)) - int(state.get("remaining") or 0)) // 60,
            "workedMinutes": int(state.get("completedFocusSeconds", 0)) // 60,
            "feedback": str(feedback).strip()[:1000]}
