import io
from unittest import TestCase, mock

from scripts.audit_hf_pinned_parquet_actions import BoundedRangeFile, compare_actions


class FakeResponse:
    def __init__(self, status, content_range, data):
        self.status = status
        self.headers = {"Content-Range": content_range}
        self.data = io.BytesIO(data)

    def read(self, n):
        return self.data.read(n)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class BoundedRangeFileTests(TestCase):
    def test_exact_range_and_seek(self):
        file = BoundedRangeFile("https://example.com/fixed.parquet", 10, budget=4)
        file.seek(5)
        with mock.patch("scripts.audit_hf_pinned_parquet_actions.request.urlopen", return_value=FakeResponse(206,"bytes 5-7/10",b"abc")) as fetched:
            self.assertEqual(file.read(3), b"abc")
            self.assertEqual(fetched.call_args.args[0].headers["Range"], "bytes=5-7")
        self.assertEqual((file.tell(), file.transferred, file.requests), (8, 3, 1))

    def test_budget_rejects_before_network(self):
        file = BoundedRangeFile("https://example.com/fixed.parquet", 100, budget=2)
        with mock.patch("scripts.audit_hf_pinned_parquet_actions.request.urlopen") as fetched:
            with self.assertRaisesRegex(OSError, "budget"):
                file.read(3)
            fetched.assert_not_called()

    def test_server_ignores_range_rejected(self):
        file = BoundedRangeFile("https://example.com/fixed.parquet", 10)
        with mock.patch("scripts.audit_hf_pinned_parquet_actions.request.urlopen", return_value=FakeResponse(200,"bytes 0-2/10",b"abc")):
            with self.assertRaisesRegex(OSError, "range"):
                file.read(3)
        self.assertEqual(file.transferred, 0)

    def test_wrong_content_range_rejected(self):
        file = BoundedRangeFile("https://example.com/fixed.parquet", 10)
        with mock.patch("scripts.audit_hf_pinned_parquet_actions.request.urlopen", return_value=FakeResponse(206,"bytes 0-3/10",b"abc")):
            with self.assertRaisesRegex(OSError, "range"):
                file.read(3)

    def test_short_range_read_rejected(self):
        file = BoundedRangeFile("https://example.com/fixed.parquet", 10)
        with mock.patch("scripts.audit_hf_pinned_parquet_actions.request.urlopen", return_value=FakeResponse(206,"bytes 0-2/10",b"ab")):
            with self.assertRaisesRegex(OSError, "length"):
                file.read(3)

    def test_invalid_seek_rejected(self):
        file = BoundedRangeFile("https://example.com/fixed.parquet", 10)
        for offset in (-1, 11):
            with self.assertRaises(OSError):
                file.seek(offset)


class ActionEquivalenceTests(TestCase):
    def setUp(self):
        self.identities = {"instance_id":"a", "repo":"b", "license":"Apache-2.0", "trajectory_id":"c", "hf_dataset_name":"d"}
        self.message = {"role":"assistant", "tool_calls":[{"type":"function", "function":{"name":"bash", "arguments":"{\"cmd\":\"echo ok\"}"}}]}
        self.saved = {**self.identities, "messages":[self.message]}

    def test_matches_only_recorded_actions(self):
        result = compare_actions({"messages":[self.message]}, self.saved, self.identities)
        self.assertEqual((result["message_count"], result["action_count"]), (1,1))

    def test_reject_different_arguments(self):
        modified = {"role":"assistant", "tool_calls":[{"type":"function", "function":{"name":"bash", "arguments":"{\"cmd\":\"echo nope\"}"}}]}
        with self.assertRaisesRegex(ValueError, "actions"):
            compare_actions({"messages":[modified]}, self.saved, self.identities)

    def test_reject_different_identity(self):
        with self.assertRaisesRegex(ValueError, "identity"):
            compare_actions({"messages":[self.message]}, self.saved, {**self.identities,"instance_id":"wrong"})

    def test_reject_different_roles(self):
        with self.assertRaisesRegex(ValueError, "roles"):
            compare_actions({"messages":[{"role":"tool", "tool_calls":[]}]}, self.saved, self.identities)
