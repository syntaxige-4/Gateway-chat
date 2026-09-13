"""
test_api.py — automated tests for the Gateway Chat backend.

Runs against a real instance of the server (spun up on a throwaway port with
a throwaway database), using only the standard library (unittest + urllib).
No pytest, no requests library — consistent with the rest of this project's
zero-dependency design.

Run with:
    cd backend
    python3 -m unittest discover tests -v
"""
import json
import os
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

TEST_PORT = 8731
BASE_URL = f"http://127.0.0.1:{TEST_PORT}"

_server_thread = None
_server = None


def setUpModule():
    global _server_thread, _server
    # Use a throwaway DB file for the whole test run so tests don't touch
    # (or get confused by) whatever database a real dev server is using.
    tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp_db.close()
    from app import db as db_module
    db_module.DB_PATH = tmp_db.name

    from app.server import Handler
    from http.server import ThreadingHTTPServer
    _server = ThreadingHTTPServer(("127.0.0.1", TEST_PORT), Handler)
    db_module.init_db()
    _server_thread = threading.Thread(target=_server.serve_forever, daemon=True)
    _server_thread.start()
    time.sleep(0.3)


def tearDownModule():
    if _server:
        _server.shutdown()


def api(path, method="GET", body=None, token=None, api_key=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if api_key:
        headers["X-Api-Key"] = api_key
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE_URL + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())


def register(username, password="password123"):
    from app import rate_limit as rate_limit_module
    rate_limit_module._buckets.clear()  # test isolation: don't let one test's registrations trip another's
    status, data = api("/api/register", "POST", {
        "username": username, "display_name": username.title(), "password": password})
    assert status == 200, data
    return data["token"], data["user"]


class AuthTests(unittest.TestCase):
    def test_register_and_login(self):
        token, user = register("alice_t")
        self.assertEqual(user["username"], "alice_t")
        self.assertEqual(user["default_mode"], "gateway")
        status, data = api("/api/login", "POST", {"username": "alice_t", "password": "password123"})
        self.assertEqual(status, 200)
        self.assertIn("token", data)

    def test_login_wrong_password_rejected(self):
        register("bob_t")
        status, data = api("/api/login", "POST", {"username": "bob_t", "password": "wrongpass"})
        self.assertEqual(status, 401)

    def test_duplicate_username_rejected(self):
        register("carol_t")
        status, data = api("/api/register", "POST", {
            "username": "carol_t", "display_name": "Carol", "password": "password123"})
        self.assertEqual(status, 409)

    def test_unauthenticated_request_rejected(self):
        status, data = api("/api/me")
        self.assertEqual(status, 401)


class SettingsTests(unittest.TestCase):
    def test_theme_validation(self):
        token, _ = register("dave_t")
        status, _ = api("/api/me", "PATCH", {"theme": "sunset"}, token=token)
        self.assertEqual(status, 200)
        status, data = api("/api/me", "PATCH", {"theme": "not-a-theme"}, token=token)
        self.assertEqual(status, 400)

    def test_platform_settings_isolated_and_validated(self):
        token, _ = register("erin_t")
        status, data = api("/api/settings/gateway", "PATCH", {"read_receipts": False}, token=token)
        self.assertEqual(status, 200)
        self.assertFalse(data["settings"]["read_receipts"])
        # unrelated platform must be untouched
        status, data = api("/api/settings/beta", token=token)
        self.assertTrue(data["settings"]["show_like_counts"])
        # unknown key rejected
        status, _ = api("/api/settings/gateway", "PATCH", {"nope": True}, token=token)
        self.assertEqual(status, 400)
        # wrong type rejected
        status, _ = api("/api/settings/gateway", "PATCH", {"read_receipts": "yes"}, token=token)
        self.assertEqual(status, 400)

    def test_new_settings_have_correct_defaults(self):
        # These are the settings added in response to "there should be more
        # than just read receipts and enter-to-send" — confirming they
        # actually exist and default sensibly, not just that the old two do.
        token, _ = register("frank_settings_t")
        status, data = api("/api/settings/gateway", token=token)
        self.assertTrue(data["settings"]["typing_indicators"])
        self.assertTrue(data["settings"]["online_status_visible"])
        status, data = api("/api/settings/beta", token=token)
        self.assertTrue(data["settings"]["show_captions"])
        status, data = api("/api/settings/epsilon", token=token)
        self.assertTrue(data["settings"]["show_reply_counts"])
        status, data = api("/api/settings/alpha", token=token)
        self.assertTrue(data["settings"]["loop_videos"])

    def test_online_status_visible_setting_actually_hides_presence(self):
        # Real server-side enforcement, not just a stored preference: with
        # this off, ANY other user looking this person up sees is_online
        # forced False and last_seen forced None, regardless of their
        # actual connection state.
        token_a, user_a = register("privacy_a")
        token_b, _ = register("privacy_b")

        status, data = api(f"/api/users/{user_a['id']}", token=token_b)
        self.assertEqual(status, 200)
        # default: visible
        self.assertIn("is_online", data["user"])

        status, _ = api("/api/settings/gateway", "PATCH", {"online_status_visible": False}, token=token_a)
        self.assertEqual(status, 200)

        status, data = api(f"/api/users/{user_a['id']}", token=token_b)
        self.assertEqual(status, 200)
        self.assertFalse(data["user"]["is_online"])
        self.assertIsNone(data["user"]["last_seen"])

    def test_typing_indicators_setting_is_read_by_the_real_gate_function(self):
        # The WebSocket typing handler gates on get_user_platform_setting()
        # directly — this confirms that function returns the override once
        # set, which is the exact value the handler branches on.
        from app import server as server_module
        token, user = register("typer_t")
        val = server_module.get_user_platform_setting(user["id"], "gateway", "typing_indicators")
        self.assertTrue(val)
        api("/api/settings/gateway", "PATCH", {"typing_indicators": False}, token=token)
        val = server_module.get_user_platform_setting(user["id"], "gateway", "typing_indicators")
        self.assertFalse(val)


class DeveloperApiKeyTests(unittest.TestCase):
    def test_generate_use_revoke(self):
        token, _ = register("frank_t")
        status, data = api("/api/dev/api-key", "POST", token=token)
        self.assertEqual(status, 200)
        raw_key = data["api_key"]
        status, data = api("/api/me", api_key=raw_key)
        self.assertEqual(status, 200)
        self.assertEqual(data["user"]["username"], "frank_t")
        status, _ = api("/api/me", api_key="gateway_live_totally_bogus")
        self.assertEqual(status, 401)
        status, _ = api("/api/dev/api-key", "DELETE", token=token)
        self.assertEqual(status, 200)
        status, _ = api("/api/me", api_key=raw_key)
        self.assertEqual(status, 401)


class BlockingTests(unittest.TestCase):
    def test_block_prevents_chat_and_follow(self):
        token_a, user_a = register("gina_t")
        token_b, user_b = register("hank_t")
        status, _ = api("/api/block", "POST", {"user_id": user_b["id"]}, token=token_a)
        self.assertEqual(status, 200)
        status, _ = api("/api/chats", "POST", {"member_ids": [user_b["id"]]}, token=token_a)
        self.assertEqual(status, 403)
        status, _ = api("/api/follow", "POST", {"user_id": user_a["id"]}, token=token_b)
        self.assertEqual(status, 403)

    def test_unblock_restores_ability_to_interact(self):
        token_a, user_a = register("ivy_t")
        token_b, user_b = register("jack_t")
        api("/api/block", "POST", {"user_id": user_b["id"]}, token=token_a)
        api("/api/unblock", "POST", {"user_id": user_b["id"]}, token=token_a)
        status, _ = api("/api/chats", "POST", {"member_ids": [user_b["id"]]}, token=token_a)
        self.assertEqual(status, 200)

    def test_blocked_users_content_filtered_from_feed(self):
        token_a, user_a = register("kim_t")
        token_b, user_b = register("liam_t")
        api("/api/posts", "POST", {"content": "hello from liam"}, token=token_b)
        status, data = api("/api/posts", token=token_a)
        self.assertTrue(any(p["username"] == "liam_t" for p in data["posts"]))
        api("/api/block", "POST", {"user_id": user_b["id"]}, token=token_a)
        status, data = api("/api/posts", token=token_a)
        self.assertFalse(any(p["username"] == "liam_t" for p in data["posts"]))


class ReportingAndAdminTests(unittest.TestCase):
    def test_report_requires_valid_target_and_reason(self):
        token, _ = register("mia_t")
        status, _ = api("/api/report", "POST", {"target_type": "bogus", "target_id": 1, "reason": "spam"}, token=token)
        self.assertEqual(status, 400)
        status, _ = api("/api/report", "POST", {"target_type": "user", "target_id": 1, "reason": ""}, token=token)
        self.assertEqual(status, 400)
        status, data = api("/api/report", "POST", {"target_type": "user", "target_id": 1, "reason": "spam"}, token=token)
        self.assertEqual(status, 200)

    def test_non_admin_cannot_access_admin_routes(self):
        token, _ = register("noah_t")
        status, _ = api("/api/admin/reports", token=token)
        self.assertEqual(status, 403)

    def test_admin_can_suspend_and_suspended_user_blocked(self):
        # Promote via the same mechanism the real server uses (env-var-driven,
        # applied at init_db time) — simulate by setting the flag directly
        # through the same code path the app itself exposes for this test.
        from app import db as db_module
        admin_token, admin_user = register("owen_admin_t")
        conn = db_module.get_conn()
        conn.execute("UPDATE users SET is_admin=1 WHERE id=?", (admin_user["id"],))
        conn.commit()

        victim_token, victim_user = register("percy_t")
        status, _ = api("/api/admin/users/%d/suspend" % victim_user["id"], "POST", token=admin_token)
        self.assertEqual(status, 200)
        status, _ = api("/api/me", token=victim_token)
        self.assertEqual(status, 403)
        status, _ = api("/api/admin/users/%d/unsuspend" % victim_user["id"], "POST", token=admin_token)
        self.assertEqual(status, 200)
        status, _ = api("/api/me", token=victim_token)
        self.assertEqual(status, 200)


class ChatAndPulseTests(unittest.TestCase):
    def test_send_and_read_message(self):
        token_a, user_a = register("quinn_t")
        token_b, user_b = register("ruth_t")
        status, data = api("/api/chats", "POST", {"member_ids": [user_b["id"]]}, token=token_a)
        chat_id = data["chat_id"]
        status, data = api(f"/api/chats/{chat_id}/messages", "POST", {"content": "hi there"}, token=token_a)
        self.assertEqual(status, 200)
        status, data = api(f"/api/chats/{chat_id}/messages", token=token_b)
        self.assertEqual(len(data["messages"]), 1)
        self.assertEqual(data["messages"][0]["content"], "hi there")

    def test_pulse_like_toggle(self):
        token, _ = register("sara_t")
        status, data = api("/api/pulse", "POST", {"caption": "test pulse", "kind": "image"}, token=token)
        pulse_id = data["id"]
        status, data = api(f"/api/pulse/{pulse_id}/like", "POST", token=token)
        self.assertTrue(data["liked"])
        status, data = api(f"/api/pulse/{pulse_id}/like", "POST", token=token)
        self.assertFalse(data["liked"])


class NotificationTests(unittest.TestCase):
    def test_notifications_ordered_by_real_event_time_not_fetch_time(self):
        token_a, user_a = register("nadia_t")
        token_b, user_b = register("owen_t")

        status, data = api("/api/posts", "POST", {"content": "first post"}, token=token_a)
        post_id = data["id"]

        # Owen likes the post first (older event)...
        status, data = api(f"/api/posts/{post_id}/like", "POST", token=token_b)
        self.assertTrue(data["liked"])

        time.sleep(1.1)

        # ...then replies to it (newer event). The reply must outrank the
        # like in the notification feed. Before the fix, likes were always
        # stamped with time.time() at *read* time, so they always sorted
        # first regardless of when they actually happened.
        status, data = api("/api/posts", "POST",
                            {"content": "a reply", "reply_to_id": post_id}, token=token_b)
        self.assertEqual(status, 200)

        status, data = api("/api/notifications", token=token_a)
        self.assertEqual(status, 200)
        kinds = [n["kind"] for n in data["notifications"]]
        self.assertIn("like", kinds)
        self.assertIn("reply", kinds)
        self.assertLess(kinds.index("reply"), kinds.index("like"),
                         "newer reply should sort before older like")


class RateLimitTests(unittest.TestCase):
    def test_auth_rate_limit_triggers(self):
        # the "auth" limiter allows 8 requests / 60s per source IP; since all
        # test requests come from 127.0.0.1, hammering /api/login should trip it.
        tripped = False
        for i in range(15):
            status, _ = api("/api/login", "POST", {"username": "nobody", "password": "x"})
            if status == 429:
                tripped = True
                break
        self.assertTrue(tripped, "expected the auth rate limiter to eventually return 429")


class RatingsTests(unittest.TestCase):
    def test_rate_and_aggregate(self):
        token_a, user_a = register("tina_t")
        token_b, user_b = register("umar_t")
        token_c, user_c = register("vera_t")
        status, data = api("/api/ratings", "POST",
                            {"target_type": "user", "target_id": user_c["id"], "stars": 4, "review": "great"},
                            token=token_a)
        self.assertEqual(status, 200)
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["average"], 4.0)
        status, data = api("/api/ratings", "POST",
                            {"target_type": "user", "target_id": user_c["id"], "stars": 2}, token=token_b)
        self.assertEqual(status, 200)
        self.assertEqual(data["count"], 2)
        self.assertEqual(data["average"], 3.0)

    def test_rerating_updates_not_duplicates(self):
        token_a, user_a = register("will_t")
        token_b, user_b = register("xena_t")
        api("/api/ratings", "POST", {"target_type": "user", "target_id": user_b["id"], "stars": 1}, token=token_a)
        status, data = api("/api/ratings", "POST",
                            {"target_type": "user", "target_id": user_b["id"], "stars": 5}, token=token_a)
        self.assertEqual(status, 200)
        self.assertEqual(data["count"], 1)  # still 1, not 2 — this was an update, not a new rating
        self.assertEqual(data["average"], 5.0)

    def test_validation(self):
        token_a, user_a = register("yuki_t")
        token_b, user_b = register("zane_t")
        status, _ = api("/api/ratings", "POST",
                         {"target_type": "user", "target_id": user_b["id"], "stars": 6}, token=token_a)
        self.assertEqual(status, 400)
        status, _ = api("/api/ratings", "POST",
                         {"target_type": "spaceship", "target_id": user_b["id"], "stars": 3}, token=token_a)
        self.assertEqual(status, 400)
        status, _ = api("/api/ratings", "POST",
                         {"target_type": "user", "target_id": user_a["id"], "stars": 5}, token=token_a)
        self.assertEqual(status, 400)  # can't rate yourself

    def test_blocking_prevents_rating(self):
        token_a, user_a = register("abel_t")
        token_b, user_b = register("bree_t")
        api("/api/block", "POST", {"user_id": user_b["id"]}, token=token_a)
        status, _ = api("/api/ratings", "POST",
                         {"target_type": "user", "target_id": user_b["id"], "stars": 3}, token=token_a)
        self.assertEqual(status, 403)

    def test_delete_rating_via_delete_method_with_body(self):
        # Regression test: DELETE requests weren't having their JSON body
        # parsed at all (only POST/PATCH/PUT were), which silently broke any
        # DELETE endpoint that needs body data. This confirms the fix holds.
        token_a, user_a = register("cleo_t")
        token_b, user_b = register("drew_t")
        api("/api/ratings", "POST", {"target_type": "user", "target_id": user_b["id"], "stars": 4}, token=token_a)
        status, data = api("/api/ratings", "DELETE",
                            {"target_type": "user", "target_id": user_b["id"]}, token=token_a)
        self.assertEqual(status, 200)
        self.assertEqual(data["count"], 0)
        self.assertIsNone(data["my_rating"])


class BittensorDataTests(unittest.TestCase):
    """These deliberately don't hit the real network — Taostats requires an
    API key, and CI shouldn't depend on an external service being up. What's
    tested is the fail-soft contract: no key configured means no snapshot
    and no crash, which is the behavior the rest of the app relies on."""

    def test_no_api_key_returns_none_without_network_call(self):
        from app import bittensor_data
        old_key = bittensor_data.TAOSTATS_API_KEY
        bittensor_data.TAOSTATS_API_KEY = ""
        bittensor_data._cache = {"snapshot": None, "fetched_at": 0.0}
        try:
            self.assertIsNone(bittensor_data.get_snapshot(force=True))
            self.assertFalse(bittensor_data.is_configured())
        finally:
            bittensor_data.TAOSTATS_API_KEY = old_key

    def test_system_prompt_falls_back_cleanly_when_no_snapshot(self):
        # build_system_prompt() must never raise just because live data is
        # unavailable — the static paragraph is always a valid fallback.
        from app import ai_providers, bittensor_data
        old_key = bittensor_data.TAOSTATS_API_KEY
        bittensor_data.TAOSTATS_API_KEY = ""
        bittensor_data._cache = {"snapshot": None, "fetched_at": 0.0}
        try:
            prompt = ai_providers.build_system_prompt()
            self.assertIn("Gateway", prompt)
            self.assertNotIn("Live Bittensor snapshot", prompt)
        finally:
            bittensor_data.TAOSTATS_API_KEY = old_key


class ProviderCheckTests(unittest.TestCase):
    """Verifies the miner-facing endpoint checker actually distinguishes a
    correct response from the specific ways a real deployment can be wrong
    — right shape, wrong shape, server error, and unreachable — against
    real local HTTP servers rather than mocks, matching how the rest of
    this suite works."""

    @classmethod
    def setUpClass(cls):
        from http.server import BaseHTTPRequestHandler, HTTPServer
        import threading

        class GoodHandler(BaseHTTPRequestHandler):
            def do_POST(self):
                n = int(self.headers.get("Content-Length", 0))
                self.rfile.read(n)
                body = json.dumps({"choices": [{"message": {"content": "pong"}}]}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *a):
                pass

        class BadShapeHandler(BaseHTTPRequestHandler):
            def do_POST(self):
                n = int(self.headers.get("Content-Length", 0))
                self.rfile.read(n)
                body = json.dumps({"unexpected": "shape"}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *a):
                pass

        cls._good_server = HTTPServer(("127.0.0.1", 0), GoodHandler)
        cls._good_port = cls._good_server.server_port
        threading.Thread(target=cls._good_server.serve_forever, daemon=True).start()

        cls._bad_server = HTTPServer(("127.0.0.1", 0), BadShapeHandler)
        cls._bad_port = cls._bad_server.server_port
        threading.Thread(target=cls._bad_server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls._good_server.shutdown()
        cls._bad_server.shutdown()

    def test_detects_correctly_shaped_endpoint(self):
        from app import provider_check
        result = provider_check.check_openai_compat(
            f"http://127.0.0.1:{self._good_port}", model="test-model", timeout=5
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["sample_reply"], "pong")

    def test_detects_wrong_response_shape(self):
        from app import provider_check
        result = provider_check.check_openai_compat(
            f"http://127.0.0.1:{self._bad_port}", model="test-model", timeout=5
        )
        self.assertFalse(result["ok"])
        self.assertIn("expected shape", result["error"])

    def test_detects_unreachable_endpoint_without_hanging(self):
        from app import provider_check
        result = provider_check.check_openai_compat(
            "http://127.0.0.1:1", model="test-model", timeout=3
        )
        self.assertFalse(result["ok"])
        self.assertIsNotNone(result["error"])


class ReplySanitizationTests(unittest.TestCase):
    """These exist because of a real bug: a provider's underlying model
    leaked raw tool-call markup and Markdown asterisks straight into a
    live chat, unfiltered. sanitize_reply() is the fix; these tests pin
    down the exact failure modes so they can't silently come back."""

    def test_strips_bold_asterisks(self):
        from app import ai_providers
        out = ai_providers.sanitize_reply("Head to the **Epsilon** space.")
        self.assertNotIn("*", out)
        self.assertIn("Epsilon", out)

    def test_strips_italic_asterisks(self):
        from app import ai_providers
        out = ai_providers.sanitize_reply("Here's what I *can* do for you.")
        self.assertNotIn("*", out)
        self.assertIn("can", out)

    def test_strips_leaked_tool_call_with_no_other_content(self):
        from app import ai_providers
        out = ai_providers.sanitize_reply('<dots_function_call> <invoke name="search">')
        self.assertNotIn("<", out)
        self.assertNotIn(">", out)
        self.assertTrue(len(out) > 0)

    def test_strips_leaked_tool_call_keeping_real_content_before_it(self):
        from app import ai_providers
        out = ai_providers.sanitize_reply(
            'Sure, let me check. <tool_call>{"name": "search"}</tool_call>'
        )
        self.assertIn("Sure, let me check.", out)
        self.assertNotIn("<", out)

    def test_ordinary_reply_passes_through_unchanged(self):
        from app import ai_providers
        out = ai_providers.sanitize_reply("Hey! How can I help today?")
        self.assertEqual(out, "Hey! How can I help today?")

    def test_no_api_key_fallback_message_has_no_asterisks(self):
        # Regression: this exact hardcoded string used to contain **bold**.
        from app import ai_providers
        old_key = os.environ.pop("GM_API_KEY", None)
        try:
            reply = ai_providers.complete([{"role": "user", "content": "hi"}], provider="gm")
            self.assertNotIn("*", reply)
        finally:
            if old_key is not None:
                os.environ["GM_API_KEY"] = old_key


if __name__ == "__main__":
    unittest.main()
