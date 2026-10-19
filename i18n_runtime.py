"""Runtime translation tables shared by the Python and QML layers.

FlowTodo keeps Simplified Chinese as the source language: every UI string in
the code base is written in ``zh_CN`` and used as the lookup key.  A language
pack is therefore a plain ``source -> translation`` JSON map, which keeps the
QML side free of ``qsTr`` bookkeeping and lets the same table serve Python
strings such as tray menus and notifications.
"""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Property, QObject, Signal, Slot


BASE_DIR = Path(__file__).resolve().parent
TABLE_DIR = BASE_DIR / "i18n"
SOURCE_LANGUAGE = "zh_CN"
LANGUAGES = (
    ("zh_CN", "简体中文"),
    ("zh_TW", "繁體中文"),
    ("en_US", "English"),
)
LANGUAGE_CODES = tuple(code for code, _label in LANGUAGES)
WEEKDAY_NAMES = {
    "zh_CN": ("星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"),
    "zh_TW": ("星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"),
    "en_US": (
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    ),
}
MONTH_NAMES_EN = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)


def normalize_language(value) -> str:
    """Map stored settings or system locales onto a supported language code."""
    text = str(value or "").strip().replace("-", "_")
    if not text:
        return SOURCE_LANGUAGE
    for code in LANGUAGE_CODES:
        if text.lower() == code.lower():
            return code
    lowered = text.lower()
    if lowered.startswith("zh"):
        if any(marker in lowered for marker in ("tw", "hk", "mo", "hant")):
            return "zh_TW"
        return "zh_CN"
    if lowered.startswith("en"):
        return "en_US"
    return SOURCE_LANGUAGE


def load_table(language: str) -> dict:
    """Read one language pack, tolerating a missing or damaged file."""
    if language == SOURCE_LANGUAGE:
        return {}
    path = TABLE_DIR / f"{language}.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(payload, dict):
        return {}
    return {
        str(key): value
        for key, value in payload.items()
        if isinstance(value, str)
    }


class Translator(QObject):
    """Expose the active language pack to Python callers and QML bindings."""

    languageChanged = Signal()

    def __init__(self, language: str = SOURCE_LANGUAGE, parent=None):
        super().__init__(parent)
        self._language = SOURCE_LANGUAGE
        self._table = {}
        self.setLanguage(language)

    @Property(str, notify=languageChanged)
    def language(self) -> str:
        return self._language

    @Property("QVariantMap", notify=languageChanged)
    def table(self) -> dict:
        return dict(self._table)

    @Property("QVariantList", constant=True)
    def languages(self) -> list:
        return [{"code": code, "label": label} for code, label in LANGUAGES]

    @Slot(str, result=str)
    def t(self, source: str) -> str:
        """Translate one source string, falling back to the original text."""
        if not self._table:
            return source
        return self._table.get(source, source)

    @Slot(str)
    def setLanguage(self, language: str) -> None:
        normalized = normalize_language(language)
        if normalized == self._language and (self._table or normalized == SOURCE_LANGUAGE):
            return
        self._language = normalized
        self._table = load_table(normalized)
        self.languageChanged.emit()


_translator: Translator | None = None


def translator() -> Translator:
    """Return the process-wide translator, creating it on first use."""
    global _translator
    if _translator is None:
        _translator = Translator()
    return _translator


def tr(source: str) -> str:
    """Translate a Python-side string with the active language pack."""
    return translator().t(source)


def format_long_date(moment, language: str | None = None, separator: str = " · ") -> str:
    """Render a month/day/weekday label in the active language."""
    code = normalize_language(language or translator().language)
    weekday = WEEKDAY_NAMES.get(code, WEEKDAY_NAMES[SOURCE_LANGUAGE])[moment.weekday()]
    if code == "en_US":
        return f"{MONTH_NAMES_EN[moment.month - 1]} {moment.day}{separator}{weekday}"
    return f"{moment.month}月{moment.day}日{separator}{weekday}"
