"""Coverage and persistence checks for the application's Traditional Chinese UI."""
import json
import re
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from check_i18n import qml_keys, python_keys, untranslated_ui_literals
from i18n_runtime import Translator, normalize_language


class TraditionalChineseTests(unittest.TestCase):
    def test_all_referenced_qml_and_python_translations_exist(self):
        keys, _ = qml_keys()
        for language in ("zh_TW", "en_US"):
            with self.subTest(language=language):
                pairs = json.loads((ROOT / f"i18n/{language}.json").read_text(encoding="utf-8"), object_pairs_hook=list)
                table = dict(pairs)
                self.assertEqual(len(table), len(pairs), "Duplicate translation keys")
                self.assertEqual(sorted((keys | python_keys()) - table.keys()), [])
                # English uses a prefix ("Week ") and intentionally drops the Chinese suffix.
                self.assertTrue(all(isinstance(table[key], str) and
                                    (table[key] or (language == "en_US" and key == " 周")) for key in keys))

    def test_english_values_and_format_placeholders(self):
        table = json.loads((ROOT / "i18n/en_US.json").read_text(encoding="utf-8"))
        for key, value in table.items():
            with self.subTest(key=key):
                if key not in {"简体中文", "繁體中文"}:
                    self.assertIsNone(re.search(r"[\u3400-\u9fff]", value))
                self.assertEqual(set(re.findall(r"\{([a-zA-Z_][a-zA-Z_0-9]*)\}", key)),
                                 set(re.findall(r"\{([a-zA-Z_][a-zA-Z_0-9]*)\}", value)))
        translator = Translator("en_US")
        self.assertEqual(translator.t("AI 助手"), "AI assistant")
        self.assertEqual(translator.t("工具"), "Tools")
        self.assertEqual(translator.t("设置"), "Settings")

    def test_no_untranslated_qml_ui_literals(self):
        self.assertEqual(untranslated_ui_literals(), [])

    def test_hong_kong_locale_and_new_assistant_strings(self):
        self.assertEqual(normalize_language("zh_HK"), "zh_TW")
        translator = Translator("zh_HK")
        self.assertEqual(translator.t("想从哪件事开始？"), "想從哪件事開始？")
        self.assertEqual(translator.t("已保存"), "已儲存")
        self.assertEqual(translator.t("语音"), "語音")
        self.assertEqual(translator.t(" · 剩余 "), " · 剩餘 ")
        self.assertEqual(translator.t("管理云端存储"), "管理雲端儲存")
        # Content entered by the user falls through unchanged.
        self.assertEqual(translator.t("我的任务原文 2026-10-24"), "我的任务原文 2026-10-24")
        translator.setLanguage("zh_CN")
        self.assertEqual(translator.t("已保存"), "已保存")

    def test_language_control_is_in_appearance(self):
        appearance = (ROOT / "qml/pages/AppAppearanceSettings.qml").read_text(encoding="utf-8")
        app = (ROOT / "qml/pages/AppSettings.qml").read_text(encoding="utf-8")
        self.assertIn('objectName: "languageBox"', appearance)
        self.assertNotIn("languageBox", app)


if __name__ == "__main__":
    unittest.main()
