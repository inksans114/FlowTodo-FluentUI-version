"""AI output locale reaches every transport and survives planning recovery."""
import copy
import io
import json
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from ai_output_language import language_instruction, localized_messages, output_language
from ai_planning import AIContextLimit, AIOutputLimit, request_plan, system_prompt


class OutputLanguageTests(unittest.TestCase):
    def test_localization_is_idempotent_and_never_changes_user_history(self):
        messages = [{"role":"system", "content":"Keep the JSON schema."},
                    {"role":"user", "content":"下周二交李明的 Python 报告，别改截止日期。"}]
        original = copy.deepcopy(messages)
        for language in ("en_US", "zh_TW", "zh_CN"):
            sent = localized_messages(messages, language)
            self.assertEqual(output_language(sent), language)
            self.assertEqual(sent[-1], original[-1])
            self.assertEqual(localized_messages(sent, language), sent)
            self.assertIn("JSON keys", sent[0]["content"])
            self.assertIn("category MUST remain exactly", sent[0]["content"])
            self.assertEqual(messages, original)

    def test_system_prompt_for_every_planning_mode_uses_selected_language(self):
        from main import BackendBridge
        for language in ("en_US", "zh_TW", "zh_CN"):
            backend = SimpleNamespace(settings_database={"language":language})
            for long_mode, capture in ((False,False),(True,False),(False,True)):
                for phase in ("intake", "answers", "continue"):
                    prompt = BackendBridge._ai_system_prompt(backend, long_mode, capture, phase)
                    self.assertIn(f"[FLOWTODO_OUTPUT_LANGUAGE={language}]", prompt)

    def test_context_recovery_preserves_the_requested_language(self):
        messages = localized_messages([{"role":"system", "content":system_prompt(capture=True)},
                                       {"role":"user", "content":"先完成物理报告，别安排化学。"}], "en_US")
        sent = []
        def call(current, **kwargs):
            sent.append(copy.deepcopy(current))
            if len(sent) == 1:
                raise AIContextLimit("retry")
            return json.dumps({"tasks":[], "summary":"What would you like to do first?"})
        result = request_plan(call, messages, json.loads, capture=True)
        self.assertEqual(len(sent), 2)
        self.assertTrue(all(output_language(items)=="en_US" for items in sent))
        self.assertEqual(sent[1][-2]["content"], messages[-1]["content"])
        self.assertEqual(result["summary"], "What would you like to do first?")

    def test_truncated_json_continues_in_the_same_language(self):
        messages = localized_messages([{"role":"system", "content":"JSON tasks"}, {"role":"user", "content":"写报告"}], "zh_TW")
        calls=[]
        def call(current, **kwargs):
            calls.append(current)
            if len(calls)==1:
                raise AIOutputLimit("limit", '{"tasks":[{"title":"完成')
            return '報告"}]}'
        result=request_plan(call,messages,json.loads)
        self.assertEqual(result["tasks"][0]["title"], "完成報告")
        self.assertTrue(all(output_language(items)=="zh_TW" for items in calls))

    def test_inflight_request_keeps_its_locale_when_ui_changes(self):
        messages=localized_messages([{"role":"user","content":"写报告"}],"en_US")
        self.assertEqual(output_language(localized_messages(messages,"zh_TW")),"en_US")


class TransportLanguageTests(unittest.TestCase):
    def test_official_transport_receives_language_without_an_extra_request(self):
        from compat_backend import RinUIBackend
        for language in ("en_US", "zh_TW", "zh_CN"):
            content='{"tasks":[{"title":"Submit report"}]}'
            client=SimpleNamespace(ai_chat=Mock(return_value={"choices":[{"message":{"content":content}}]}))
            backend=SimpleNamespace(settings_database={"language":language,"aiServiceMode":"official"},
                _cloud=SimpleNamespace(logged_in=lambda:True,client=client),
                _record_ai_usage=Mock(),cloudAIRefreshRequested=SimpleNamespace(emit=Mock()))
            messages=[{"role":"user","content":"交报告"}]
            result=RinUIBackend._call_ai_chat(backend,messages)
            client.ai_chat.assert_called_once()
            sent=client.ai_chat.call_args.args[0]
            self.assertEqual(output_language(sent),language)
            self.assertEqual(sent[-1]["content"],"交报告")
            self.assertEqual(result,content)
            self.assertEqual(len(messages),1)

    def test_custom_transport_receives_language_and_preserves_schema(self):
        from main import BackendBridge
        class Bridge:
            _call_ai_chat=BackendBridge._call_ai_chat
            _ai_request_temperature=BackendBridge._ai_request_temperature
            _ai_chat_endpoint=BackendBridge._ai_chat_endpoint
            _safe_int=BackendBridge._safe_int
            _safe_float=BackendBridge._safe_float
        for language in ("en_US", "zh_TW"):
            backend=Bridge()
            backend.settings_database={"language":language,"aiApiKey":"test-only","aiServiceMode":"custom"}
            sent=[]
            content=json.dumps({"tasks":[{"title":"Submit report","scheduledDate":"2026-10-27","done":False}]})
            def respond(request,timeout):
                sent.append(json.loads(request.data))
                return io.BytesIO(json.dumps({"choices":[{"message":{"content":content}}]}).encode())
            with patch("urllib.request.urlopen",respond):
                result=backend._call_ai_chat([{"role":"user","content":"周二交报告"}])
            self.assertEqual(len(sent),1)
            self.assertEqual(output_language(sent[0]["messages"]),language)
            self.assertEqual(json.loads(result)["tasks"][0]["scheduledDate"],"2026-10-27")

    def test_quick_entry_uses_one_request_and_keeps_stored_category_identifiers(self):
        from quick_capture import ai_tasks
        calls=[]
        def call(messages,**kwargs):
            sent=localized_messages(messages,"en_US")
            calls.append(sent)
            return '{"tasks":[{"title":"Submit report","category":"工作"}]}'
        result=ai_tasks(call,"交报告")
        self.assertEqual(len(calls),1)
        self.assertEqual(output_language(calls[0]),"en_US")
        self.assertEqual(result,[{"title":"Submit report","category":"工作"}])


if __name__ == "__main__":
    unittest.main()
