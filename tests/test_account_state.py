import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from account_state import AccountState, token_count


class AccountTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "account.json"
        self.store = AccountState(self.path)
        self.now = datetime(2026, 10, 10, 12, tzinfo=timezone.utc)

    def test_free_counts_requests_even_without_token_metadata(self):
        self.store.record(None, "default", self.now)
        view = self.store.snapshot(now=self.now)
        self.assertEqual(view["unreportedRequests"], 1)
        self.assertEqual(view["usage"]["remaining"], 4)
        self.assertEqual(view["usage"]["limit"], 5)
        self.assertEqual(view["usage"]["remainingFraction"], 0.8)
        self.assertNotIn("windows", view)
        self.assertIsNone(token_count({"total_tokens": -1}))
        self.assertIsNone(token_count({"total_tokens": True}))

    def test_free_is_lifetime_and_custom_api_does_not_consume_it(self):
        self.store.record({"total_tokens": 20}, "default", self.now - timedelta(days=8))
        self.store.record({"total_tokens": 30}, "default", self.now - timedelta(hours=6))
        self.store.record({"prompt_tokens": 5, "completion_tokens": 6}, "default", self.now)
        self.store.record({"total_tokens": 100}, "custom", self.now)
        view = self.store.snapshot(now=self.now)
        self.assertEqual(view["totalTokens"], 161)
        self.assertEqual(view["usage"]["used"], 3)
        self.assertEqual(view["usage"]["remaining"], 2)
        self.assertEqual(AccountState(self.path).snapshot(now=self.now)["usage"]["remaining"], 2)
        self.assertEqual(self.store.snapshot("custom", self.now)["usage"]["status"], "provider")
        self.assertEqual(self.store.snapshot("custom", self.now)["usage"]["used"], 1)
        self.assertIsNone(self.store.snapshot("custom", self.now)["usage"]["remaining"])

    def test_identity_and_usage_survive_restart(self):
        handle = self.store.snapshot()["handle"]
        self.store.rename("林同学")
        self.store.record({"total_tokens": 10}, "default", self.now)
        restored = AccountState(self.path).snapshot(now=self.now)
        self.assertEqual(restored["name"], "林同学")
        self.assertEqual(restored["handle"], handle)
        self.assertEqual(restored["totalTokens"], 10)
        self.assertNotIn("apiKey", json.dumps(restored))
        with self.assertRaises(ValueError):
            self.store.rename(" ")

    def test_legacy_total_is_marked_incomplete_without_inventing_usage(self):
        self.path.write_text(json.dumps({"version": 1, "totalRequests": 8, "totalTokens": 999,
            "events": [{"at": self.now.isoformat(), "tokens": 15, "service": "default"},
                       {"at": self.now.isoformat(), "tokens": 25, "service": "custom"}]}), encoding="utf-8")
        restored = AccountState(self.path)
        usage = restored.snapshot(now=self.now)["usage"]
        self.assertTrue(usage["historyIncomplete"])
        self.assertEqual(usage["used"], 1)
        restored.record({"total_tokens": 20}, "default", self.now)
        self.assertEqual(AccountState(self.path).snapshot(now=self.now)["usage"]["used"], 2)

    def test_exhaustion_persists_and_does_not_reset_with_time(self):
        for _ in range(5):
            self.store.begin_request("default")
            self.store.record(None, "default", self.now)
            self.store.end_request("default")
        restored = AccountState(self.path)
        self.assertEqual(restored.snapshot(now=self.now + timedelta(days=100))["usage"]["remaining"], 0)
        self.assertEqual(restored.snapshot()["usage"]["status"], "exhausted")
        with self.assertRaisesRegex(RuntimeError, "5 次"):
            restored.begin_request("default")
        restored.begin_request("custom")
        restored.end_request("custom")

    def test_pending_slots_prevent_overrun_and_failed_calls_release_slot(self):
        for _ in range(5):
            self.store.begin_request("default")
        with self.assertRaises(RuntimeError):
            self.store.begin_request("default")
        self.store.end_request("default")  # Failed transport is not recorded.
        self.assertEqual(self.store.snapshot()["usage"]["remaining"], 5)
        self.store.begin_request("default")
        self.store.record(None, "default", self.now)
        self.store.end_request("default")
        self.assertEqual(self.store.snapshot()["usage"]["remaining"], 4)


if __name__ == "__main__":
    unittest.main()
