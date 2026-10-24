"""Audit application QML literals and translation-table coverage without loading UI."""
from __future__ import annotations

import ast
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
TOKENS = re.compile(r'//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'', re.S)
CJK = re.compile(r"[\u3400-\u9fff]")


def literals(source):
    for match in TOKENS.finditer(source):
        if match.group()[0] not in "\"'":
            continue
        try:
            value = ast.literal_eval(match.group())
        except (ValueError, SyntaxError):
            continue
        if CJK.search(value):
            yield match, value


def qml_keys():
    keys = set()
    raw = []
    for path in sorted((ROOT / "qml").rglob("*.qml")):
        source = path.read_text(encoding="utf-8-sig")
        for match, value in literals(source):
            if re.search(r"I18n\.t\(\s*$", source[:match.start()]):
                keys.add(value)
            else:
                raw.append((str(path.relative_to(ROOT)), source.count("\n", 0, match.start()) + 1, value))
    return keys, raw


def python_keys():
    keys = set()
    for path in ROOT.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "tr" and node.args:
                arg = node.args[0]
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    keys.add(arg.value)
    return keys


def untranslated_ui_literals():
    """Exclude canonical data values that must survive language changes unchanged."""
    _, raw = qml_keys()
    def is_data(path, value):
        name = Path(path).name
        return ((name == "QuickCapture.qml" and value in {"其他", "学习", "工作", "生活"})
                or (name == "AiSettings.qml" and value == "安静")
                or (name == "SupervisionWorkspace.qml" and value.startswith("抖音,")))
    return [row for row in raw if not is_data(row[0], row[2])]


if __name__ == "__main__":
    keys, raw = qml_keys()
    missing = {}
    for language in ("zh_TW", "en_US"):
        table = json.loads((ROOT / f"i18n/{language}.json").read_text(encoding="utf-8"))
        missing[language] = sorted((keys | python_keys()) - table.keys())
    raw = untranslated_ui_literals()
    print(json.dumps({"missing": missing, "untranslated_ui": raw}, ensure_ascii=False, indent=2))
    raise SystemExit(bool(any(missing.values()) or raw))
