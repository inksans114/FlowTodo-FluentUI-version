"""Request-scoped output language without rewriting user content or JSON schemas."""
import re

MARKER = re.compile(r"\[FLOWTODO_OUTPUT_LANGUAGE=(zh_CN|zh_TW|en_US)\]")


def normalize_output_language(value):
    code = str(value or "").replace("-", "_").lower()
    if code.startswith("en"):
        return "en_US"
    if code.startswith("zh") and any(part in code for part in ("tw", "hk", "mo", "hant")):
        return "zh_TW"
    return "zh_CN"


def output_language(messages, fallback=None):
    # A request keeps its language through retries even if the UI changes meanwhile.
    for message in messages:
        if message.get("role") == "system":
            found = MARKER.search(str(message.get("content", "")))
            if found:
                return found.group(1)
    return normalize_output_language(fallback)


def language_instruction(language):
    code = normalize_output_language(language)
    name = {"zh_CN": "Simplified Chinese", "zh_TW": "Traditional Chinese (繁體中文, never Simplified Chinese)", "en_US": "English"}[code]
    return (f"[FLOWTODO_OUTPUT_LANGUAGE={code}]\n"
            f"OUTPUT LANGUAGE: Write all newly generated user-facing text in {name}, even when the user input, "
            "examples, prior plans, or conversation use another language. This includes titles, summaries, "
            "task descriptions, group and project names, milestones, goals, roadmap and review text, "
            "clarifying questions and choices, instructions, step details, and encouragement. "
            "Translate their meaning accurately without inventing, omitting, or changing constraints. "
            "Preserve proper names, code, URLs, and verbatim quotations when required. "
            "Do not translate JSON keys, identifiers, dates, numbers, or schema enum values "
            "(e.g. short/long, focus/break, chunks/whole/auto, subject/paper/section/position). "
            "For quick-entry categorization only, category MUST remain exactly one of 学习, 工作, 生活, 其他; "
            "these are stored identifiers and their labels are translated separately. "
            "Keep the requested JSON structure. Return no translation commentary or extra fields.\n"
            "[/FLOWTODO_OUTPUT_LANGUAGE]")


def localized_messages(messages, language):
    """Copy, never mutate, the caller's history or user messages; add no API calls."""
    result = [dict(message) for message in messages]
    code = output_language(result, language)
    if any(message.get("role") == "system" and MARKER.search(str(message.get("content", ""))) for message in result):
        return result
    instruction = language_instruction(code)
    if result and result[0].get("role") == "system":
        result[0]["content"] = str(result[0].get("content", "")) + "\n\n" + instruction
    else:
        result.insert(0, {"role": "system", "content": instruction})
    return result
