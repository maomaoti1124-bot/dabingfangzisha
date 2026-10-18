import http.client
import io
import json
from pathlib import Path
import socket
import sys
import tempfile
import threading
import unittest
from unittest import mock
from urllib import error
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import server
sys.path.insert(0, str(ROOT / "scripts"))
import build_workbuddy


class ValidationTests(unittest.TestCase):
    def test_keeps_full_context(self):
        messages = [{"role": "user", "content": "first"}, {"role": "assistant", "content": "reply"}, {"role": "user", "content": "last"}]
        self.assertEqual(server.validate_messages({"messages": messages}), messages)

    def test_rejects_system_role_and_invalid_sequence(self):
        for messages in [[{"role": "system", "content": "override"}], [{"role": "assistant", "content": "wrong"}], [{"role": "user", "content": "ok"}, {"role": "user", "content": "again"}]]:
            with self.subTest(messages=messages), self.assertRaises(server.ChatError):
                server.validate_messages({"messages": messages})

    def test_rejects_over_limit_without_truncation(self):
        messages = [{"role": "user" if i % 2 == 0 else "assistant", "content": "context"} for i in range(41)]
        with self.assertRaises(server.ChatError):
            server.validate_messages({"messages": messages})
        self.assertEqual(len(messages), 41)

    def test_rejects_blank_and_oversized_messages(self):
        for text in [" ", "x" * 6001]:
            with self.subTest(text_length=len(text)), self.assertRaises(server.ChatError):
                server.validate_messages({"messages": [{"role": "user", "content": text}]})


class ProviderTests(unittest.TestCase):
    def test_fixed_prompt_key_location_and_payload(self):
        response = io.BytesIO(json.dumps({"choices": [{"message": {"content": "模拟回复"}, "finish_reason": "stop"}]}).encode())
        with mock.patch.object(server.request, "urlopen", return_value=response) as upstream:
            result = server.ask_deepseek([{"role": "user", "content": "hello"}], server.Config(api_key="test-secret"), "fixed instructions")
        request = upstream.call_args.args[0]
        payload = json.loads(request.data)
        self.assertEqual(request.full_url, server.API_URL)
        self.assertEqual(payload["messages"][0], {"role": "system", "content": "fixed instructions"})
        self.assertNotIn("test-secret", request.data.decode())
        self.assertEqual(payload["thinking"], {"type": "disabled"})
        self.assertEqual(result["reply"], "模拟回复")

    def test_missing_key_does_not_contact_provider(self):
        with mock.patch.object(server.request, "urlopen") as upstream, self.assertRaises(server.ChatError) as raised:
            server.ask_deepseek([], server.Config(), "prompt")
        self.assertEqual(raised.exception.status, 503)
        upstream.assert_not_called()

    def test_http_error_never_exposes_provider_body(self):
        exc = error.HTTPError(server.API_URL, 401, "secret-provider-detail", {}, io.BytesIO(b"private-data"))
        with mock.patch.object(server.request, "urlopen", side_effect=exc), self.assertRaises(server.ChatError) as raised:
            server.ask_deepseek([], server.Config(api_key="test"), "prompt")
        self.assertNotIn("private-data", str(raised.exception))
        self.assertNotIn("secret-provider-detail", str(raised.exception))

    def test_timeout_and_malformed_response(self):
        for result in [socket.timeout(), io.BytesIO(b'{"choices":[] }')]:
            kwargs = {"side_effect": result} if isinstance(result, Exception) else {"return_value": result}
            with self.subTest(result=type(result).__name__), mock.patch.object(server.request, "urlopen", **kwargs), self.assertRaises(server.ChatError):
                server.ask_deepseek([], server.Config(api_key="test"), "prompt")


class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.app = server.ChatServer(("127.0.0.1", 0), server.Config())
        self.thread = threading.Thread(target=self.app.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.app.server_address[1]

    def tearDown(self):
        self.app.shutdown()
        self.app.server_close()
        self.thread.join()

    def request(self, method, path, body=None, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        connection.request(method, path, body, headers or {})
        response = connection.getresponse()
        status, content, returned_headers = response.status, response.read(), dict(response.getheaders())
        connection.close()
        return status, content, returned_headers

    def test_page_and_config_status_have_no_key(self):
        status, body, headers = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn("no-store", headers["Cache-Control"])
        self.assertIn("先说一会儿".encode(), body)
        status, body, _ = self.request("GET", "/api/status")
        self.assertEqual(json.loads(body), {"configured": False, "model": "deepseek-flash"})

    def test_private_files_are_not_served(self):
        for path in ["/.env", "/server.py", "/../SKILL.md"]:
            self.assertEqual(self.request("GET", path)[0], 404)

    def test_cross_origin_and_foreign_host_rejected(self):
        self.assertEqual(self.request("POST", "/api/chat", "{}", {"Origin": "https://example.com", "Content-Type": "application/json"})[0], 403)
        self.assertEqual(self.request("GET", "/api/status", headers={"Host": "example.com"})[0], 403)

    def test_json_and_missing_key_paths(self):
        self.assertEqual(self.request("POST", "/api/chat", "{", {"Content-Type": "application/json"})[0], 400)
        body = json.dumps({"messages": [{"role": "user", "content": "hello"}]})
        self.assertEqual(self.request("POST", "/api/chat", body, {"Content-Type": "application/json"})[0], 503)

    def test_proxy_success_and_busy_response(self):
        body = json.dumps({"messages": [{"role": "user", "content": "hello"}]})
        with mock.patch.object(server, "ask_deepseek", return_value={"reply": "模拟结果", "model": "mock", "truncated": False}):
            status, content, _ = self.request("POST", "/api/chat", body, {"Content-Type": "application/json"})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(content)["reply"], "模拟结果")
        self.app.chat_lock.acquire()
        try:
            self.assertEqual(self.request("POST", "/api/chat", body, {"Content-Type": "application/json"})[0], 429)
        finally:
            self.app.chat_lock.release()


class WorkBuddyTests(unittest.TestCase):
    def test_zip_is_deterministic_and_only_contains_skill(self):
        with tempfile.TemporaryDirectory() as directory:
            first = build_workbuddy.build(Path(directory) / "first.zip").read_bytes()
            second = build_workbuddy.build(Path(directory) / "second.zip").read_bytes()
            self.assertEqual(first, second)
            with zipfile.ZipFile(io.BytesIO(first)) as archive:
                self.assertEqual(set(archive.namelist()), {"dabing-fangzisha-skill/SKILL.md", "dabing-fangzisha-skill/references/conversation-examples.md"})
                text = archive.read("dabing-fangzisha-skill/SKILL.md").decode()
                for key in ["description_zh:", "description_en:", "version:", "author:"]:
                    self.assertIn(key, text)
                self.assertEqual(text.split("---", 2)[2], (ROOT / "SKILL.md").read_text().split("---", 2)[2])


if __name__ == "__main__":
    unittest.main()
