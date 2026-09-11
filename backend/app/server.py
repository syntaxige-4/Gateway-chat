"""
server.py — Gateway Chat backend.

A full REST API + real-time WebSocket layer built entirely on the Python
standard library (http.server, sqlite3, socket). No pip install required.

Run with:  python3 run.py   (from the backend/ directory)
"""
import json
import os
import re
import time
import base64
import mimetypes
import threading
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, unquote

from . import db, auth, ai_providers, wsutil, logging_util, rate_limit
from .templates import icons
from .templates.page import render_page

BASE_DIR = os.path.dirname(os.path.dirname(__file__))  # backend/
MEDIA_DIR = os.path.join(BASE_DIR, "media")
UPLOAD_DIR = os.path.join(MEDIA_DIR, "uploads")

STORY_TTL_SECONDS = 24 * 60 * 60

# ---------------------------------------------------------------------------
# Live connection registry (for WebSocket fan-out)
# ---------------------------------------------------------------------------
_connections_lock = threading.Lock()
_connections = {}  # user_id -> set(WebSocketConnection)


def register_connection(user_id, conn):
    with _connections_lock:
        _connections.setdefault(user_id, set()).add(conn)
    _set_online(user_id, True)


def unregister_connection(user_id, conn):
    with _connections_lock:
        conns = _connections.get(user_id)
        if conns and conn in conns:
            conns.discard(conn)
            if not conns:
                del _connections[user_id]
    if user_id not in _connections:
        _set_online(user_id, False)


def _set_online(user_id, online):
    c = db.get_conn()
    c.execute("UPDATE users SET is_online=?, last_seen=? WHERE id=?",
              (1 if online else 0, time.time(), user_id))
    c.commit()
    broadcast_to_users(_chat_partner_ids(user_id),
                        {"type": "presence", "user_id": user_id, "is_online": online})


def _chat_partner_ids(user_id):
    c = db.get_conn()
    rows = c.execute(
        """SELECT DISTINCT cm2.user_id FROM chat_members cm1
           JOIN chat_members cm2 ON cm1.chat_id = cm2.chat_id
           WHERE cm1.user_id=? AND cm2.user_id != ?""",
        (user_id, user_id),
    ).fetchall()
    return [r["user_id"] for r in rows]


def send_to_user(user_id, event: dict):
    with _connections_lock:
        conns = list(_connections.get(user_id, []))
    payload = json.dumps(event)
    for conn in conns:
        conn.send_text(payload)


def broadcast_to_users(user_ids, event: dict):
    for uid in user_ids:
        send_to_user(uid, event)


def broadcast_to_chat(chat_id, event: dict, exclude_user_id=None):
    c = db.get_conn()
    rows = c.execute("SELECT user_id FROM chat_members WHERE chat_id=?", (chat_id,)).fetchall()
    for r in rows:
        if r["user_id"] != exclude_user_id:
            send_to_user(r["user_id"], event)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def public_user(u: dict):
    if u is None:
        return None
    keys = u.keys()
    try:
        perms = json.loads(u["permissions_state"]) if "permissions_state" in keys and u["permissions_state"] else {}
    except (ValueError, TypeError):
        perms = {}
    online_visible = get_user_platform_setting(u, "gateway", "online_status_visible") if "gateway_settings" in keys else True
    return {
        "id": u["id"], "username": u["username"], "display_name": u["display_name"],
        "avatar_url": u["avatar_url"], "bio": u["bio"], "status": u["status"],
        "is_bot": bool(u["is_bot"]),
        "is_online": bool(u["is_online"]) if online_visible else False,
        "last_seen": u["last_seen"] if online_visible else None,
        "default_mode": u["default_mode"] if "default_mode" in keys else "gateway",
        "theme": u["theme"] if "theme" in keys else "midnight",
        "is_premium": bool(u["is_premium"]) if "is_premium" in keys else False,
        "permissions": perms,
        "has_api_key": bool(u["api_key_hash"]) if "api_key_hash" in keys and u["api_key_hash"] else False,
        "is_admin": bool(u["is_admin"]) if "is_admin" in keys else False,
    }


VALID_MODES = {"gateway", "beta", "epsilon", "alpha"}
VALID_THEMES = {"midnight", "light", "amoled", "sunset", "ocean"}
VALID_WALLPAPERS = {"", "default", "dunes", "botanical", "circuit", "aurora", "noir"}
VALID_PERMISSION_KEYS = {"camera", "microphone"}
VALID_PERMISSION_VALUES = {"granted", "denied", "skipped", "unset"}

PLATFORM_SETTINGS_SCHEMA = {
    "gateway": {"read_receipts": True, "enter_to_send": True,
                "typing_indicators": True, "online_status_visible": True},
    "beta": {"show_like_counts": True, "autoplay_videos": True, "show_captions": True},
    "epsilon": {"compact_timeline": False, "autoplay_media": True, "show_reply_counts": True},
    "alpha": {"autoplay_sound": False, "data_saver": False, "loop_videos": True},
}


def get_user_platform_setting(user_row_or_id, platform, key):
    """Reads one merged (default + stored) platform-setting value, real
    enough to gate actual server behavior on — not just something the
    frontend reads back for display. Accepts either a raw user row/dict
    that already has the relevant *_settings column, or a bare user_id
    (fetched fresh in that case, e.g. from a WebSocket handler that only
    has an id, not a full row)."""
    col = f"{platform}_settings"
    if isinstance(user_row_or_id, int):
        c = db.get_conn()
        row = c.execute(f"SELECT {col} FROM users WHERE id=?", (user_row_or_id,)).fetchone()
        raw = row[col] if row else None
    else:
        keys = user_row_or_id.keys()
        raw = user_row_or_id[col] if col in keys else None
    try:
        stored = json.loads(raw) if raw else {}
    except (ValueError, TypeError):
        stored = {}
    return stored.get(key, PLATFORM_SETTINGS_SCHEMA[platform][key])


def get_or_create_direct_chat(user_a, user_b, enforce_block=False):
    c = db.get_conn()
    if enforce_block and is_blocked_either_way(c, user_a, user_b):
        raise ApiError(403, "Can't start a chat — one of you has blocked the other.")
    rows = c.execute(
        """SELECT cm1.chat_id FROM chat_members cm1
           JOIN chat_members cm2 ON cm1.chat_id = cm2.chat_id
           JOIN chats ch ON ch.id = cm1.chat_id
           WHERE cm1.user_id=? AND cm2.user_id=? AND ch.is_group=0""",
        (user_a, user_b),
    ).fetchall()
    if rows:
        return rows[0]["chat_id"]
    cur = c.execute("INSERT INTO chats (is_group, name, created_by, created_at) VALUES (0,'',?,?)",
                     (user_a, time.time()))
    chat_id = cur.lastrowid
    for uid in (user_a, user_b):
        c.execute("INSERT INTO chat_members (chat_id, user_id, joined_at) VALUES (?,?,?)",
                   (chat_id, uid, time.time()))
    c.commit()
    return chat_id


def save_upload(filename: str, data_b64: str) -> str:
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    safe_name = re.sub(r"[^A-Za-z0-9_.-]", "_", filename or "file")
    unique = f"{int(time.time()*1000)}_{safe_name}"
    raw = base64.b64decode(data_b64.split(",")[-1])  # tolerate data: URLs
    path = os.path.join(UPLOAD_DIR, unique)
    with open(path, "wb") as f:
        f.write(raw)
    return f"/media/uploads/{unique}"


def gateway_reply_async(chat_id, user_id, history, provider):
    def _run():
        try:
            reply_text = ai_providers.complete(history, provider=provider)
        except ai_providers.AIError as e:
            reply_text = f"[Gateway] I hit an error talking to the model: {e}"
        c = db.get_conn()
        gateway = db.get_gateway_user()
        cur = c.execute(
            """INSERT INTO messages (chat_id, sender_id, kind, content, status, created_at)
               VALUES (?,?, 'text', ?, 'sent', ?)""",
            (chat_id, gateway["id"], reply_text, time.time()),
        )
        c.commit()
        msg = db.row_to_dict(c.execute("SELECT * FROM messages WHERE id=?", (cur.lastrowid,)).fetchone())
        broadcast_to_chat(chat_id, {"type": "message", "message": msg})
    threading.Thread(target=_run, daemon=True).start()


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------
ROUTES = []  # list of (method, compiled_regex, func)


def route(method, pattern):
    regex = re.compile("^" + pattern + "$")

    def deco(func):
        ROUTES.append((method, regex, func))
        return func
    return deco


class ApiError(Exception):
    def __init__(self, status, message):
        self.status = status
        self.message = message


def safe_str(body, key, default=""):
    """Fetch a string field from a JSON body safely — a malformed client
    sending an int/list/dict where a string is expected should get a clean
    400, not crash the request with an AttributeError."""
    val = body.get(key, default)
    if val is None:
        return default
    if not isinstance(val, str):
        raise ApiError(400, f"'{key}' must be a string")
    return val


def require_auth(handler):
    c = db.get_conn()
    api_key = handler.headers.get("X-Api-Key", "")
    if api_key:
        key_hash = auth.hash_api_key(api_key)
        user = c.execute("SELECT * FROM users WHERE api_key_hash=? AND api_key_hash!=''", (key_hash,)).fetchone()
        if user:
            user = db.row_to_dict(user)
        else:
            raise ApiError(401, "Invalid API key")
    else:
        auth_header = handler.headers.get("Authorization", "")
        token = auth_header[7:] if auth_header.startswith("Bearer ") else None
        if not token:
            qs = parse_qs(urlparse(handler.path).query)
            token = qs.get("token", [None])[0]
        payload = auth.decode_token(token) if token else None
        if not payload:
            raise ApiError(401, "Unauthorized")
        user_row = c.execute("SELECT * FROM users WHERE id=?", (payload["sub"],)).fetchone()
        if not user_row:
            raise ApiError(401, "Unauthorized")
        user = db.row_to_dict(user_row)
    if user.get("is_suspended"):
        raise ApiError(403, "This account has been suspended.")
    return user


def require_admin(handler):
    user = require_auth(handler)
    if not user.get("is_admin"):
        raise ApiError(403, "Admin access required")
    return user


# ---- Auth ----
@route("POST", r"/api/register")
def register(handler, m, body):
    username = safe_str(body, "username").strip().lower()
    display_name = safe_str(body, "display_name", username).strip()
    password = safe_str(body, "password")
    if not re.match(r"^[a-z0-9_.]{3,20}$", username):
        raise ApiError(400, "Username must be 3-20 chars: letters, numbers, _ .")
    if len(password) < 6:
        raise ApiError(400, "Password must be at least 6 characters.")
    c = db.get_conn()
    if c.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone():
        raise ApiError(409, "Username already taken.")
    pw_hash, salt = auth.hash_password(password)
    cur = c.execute(
        """INSERT INTO users (username, display_name, password_hash, salt, avatar_url,
           created_at) VALUES (?,?,?,?,?,?)""",
        (username, display_name, pw_hash, salt,
         f"https://api.dicebear.com/7.x/thumbs/svg?seed={username}", time.time()),
    )
    c.commit()
    user_id = cur.lastrowid
    gateway = db.get_gateway_user()
    get_or_create_direct_chat(user_id, gateway["id"])
    user = db.row_to_dict(c.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone())
    token = auth.create_token(user_id, username)
    return 200, {"token": token, "user": public_user(user)}


@route("POST", r"/api/login")
def login(handler, m, body):
    username = safe_str(body, "username").strip().lower()
    password = safe_str(body, "password")
    c = db.get_conn()
    user = c.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    if not user or not auth.verify_password(password, user["password_hash"], user["salt"]):
        raise ApiError(401, "Invalid username or password.")
    token = auth.create_token(user["id"], user["username"])
    return 200, {"token": token, "user": public_user(db.row_to_dict(user))}


@route("GET", r"/api/me")
def me(handler, m, body):
    user = require_auth(handler)
    return 200, {"user": public_user(user)}


@route("PATCH", r"/api/me")
def update_me(handler, m, body):
    user = require_auth(handler)
    fields, values = [], []
    for key in ("display_name", "bio", "status", "avatar_url"):
        if key in body:
            fields.append(f"{key}=?")
            values.append(safe_str(body, key))
    if "default_mode" in body:
        if body["default_mode"] not in VALID_MODES:
            raise ApiError(400, "Invalid mode")
        fields.append("default_mode=?")
        values.append(body["default_mode"])
    if "theme" in body:
        if body["theme"] not in VALID_THEMES:
            raise ApiError(400, "Invalid theme")
        fields.append("theme=?")
        values.append(body["theme"])
    if "is_premium" in body:
        fields.append("is_premium=?")
        values.append(1 if body["is_premium"] else 0)
    if fields:
        values.append(user["id"])
        db.get_conn().execute(f"UPDATE users SET {','.join(fields)} WHERE id=?", values)
        db.get_conn().commit()
    updated = db.row_to_dict(db.get_conn().execute("SELECT * FROM users WHERE id=?", (user["id"],)).fetchone())
    return 200, {"user": public_user(updated)}


@route("PATCH", r"/api/me/permissions")
def update_permissions(handler, m, body):
    """Records the outcome of a real browser getUserMedia() prompt the client
    already ran — this endpoint never grants anything itself, it just persists
    what the browser told us, so we don't re-prompt every session."""
    user = require_auth(handler)
    c = db.get_conn()
    try:
        current = json.loads(user["permissions_state"]) if user["permissions_state"] else {}
    except (ValueError, TypeError):
        current = {}
    for key, value in body.items():
        if key not in VALID_PERMISSION_KEYS or value not in VALID_PERMISSION_VALUES:
            raise ApiError(400, f"Invalid permission key/value: {key}={value}")
        current[key] = value
    c.execute("UPDATE users SET permissions_state=? WHERE id=?", (json.dumps(current), user["id"]))
    c.commit()
    return 200, {"permissions": current}


# ---- Per-platform settings (each platform isolated; general settings live on /api/me) ----
@route("GET", r"/api/settings/(?P<platform>gateway|beta|epsilon|alpha)")
def get_platform_settings(handler, m, body):
    user = require_auth(handler)
    platform = m.group("platform")
    col = f"{platform}_settings"
    defaults = PLATFORM_SETTINGS_SCHEMA[platform]
    try:
        stored = json.loads(user[col]) if user[col] else {}
    except (ValueError, TypeError):
        stored = {}
    merged = {**defaults, **stored}
    return 200, {"platform": platform, "settings": merged}


@route("PATCH", r"/api/settings/(?P<platform>gateway|beta|epsilon|alpha)")
def update_platform_settings(handler, m, body):
    user = require_auth(handler)
    platform = m.group("platform")
    col = f"{platform}_settings"
    defaults = PLATFORM_SETTINGS_SCHEMA[platform]
    c = db.get_conn()
    try:
        stored = json.loads(user[col]) if user[col] else {}
    except (ValueError, TypeError):
        stored = {}
    for key, value in body.items():
        if key not in defaults:
            raise ApiError(400, f"Unknown setting for {platform}: {key}")
        if not isinstance(value, type(defaults[key])):
            raise ApiError(400, f"Wrong type for {key}")
        stored[key] = value
    c.execute(f"UPDATE users SET {col}=? WHERE id=?", (json.dumps(stored), user["id"]))
    c.commit()
    merged = {**defaults, **stored}
    return 200, {"platform": platform, "settings": merged}


# ---- Developer options: personal API key ----
@route("POST", r"/api/dev/api-key")
def generate_dev_api_key(handler, m, body):
    user = require_auth(handler)
    raw_key = auth.generate_api_key()
    key_hash = auth.hash_api_key(raw_key)
    c = db.get_conn()
    c.execute("UPDATE users SET api_key_hash=?, api_key_created_at=? WHERE id=?",
              (key_hash, time.time(), user["id"]))
    c.commit()
    return 200, {"api_key": raw_key, "note": "This is shown once — store it now. Use it as an 'X-Api-Key' header."}


@route("DELETE", r"/api/dev/api-key")
def revoke_dev_api_key(handler, m, body):
    user = require_auth(handler)
    c = db.get_conn()
    c.execute("UPDATE users SET api_key_hash='', api_key_created_at=0 WHERE id=?", (user["id"],))
    c.commit()
    return 200, {"ok": True}


# ---- Sounds library (original / user-uploaded audio — not a licensed music catalog) ----
@route("GET", r"/api/sounds")
def list_sounds(handler, m, body):
    user = require_auth(handler)
    c = db.get_conn()
    rows = c.execute(
        """SELECT s.*, u.username, u.display_name FROM sounds s JOIN users u ON u.id=s.user_id
           ORDER BY s.id DESC LIMIT 100""").fetchall()
    sounds = []
    for r in rows:
        r = db.row_to_dict(r)
        r["rating"] = _rating_summary(c, "sound", r["id"], user["id"])
        sounds.append(r)
    return 200, {"sounds": sounds}


@route("POST", r"/api/sounds")
def create_sound(handler, m, body):
    user = require_auth(handler)
    title = safe_str(body, "title").strip()
    file_url = body.get("file_url") or ""
    if not title or not file_url:
        raise ApiError(400, "title and file_url are required")
    c = db.get_conn()
    cur = c.execute(
        "INSERT INTO sounds (user_id, title, artist, file_url, duration, created_at) VALUES (?,?,?,?,?,?)",
        (user["id"], title, body.get("artist", ""), file_url, body.get("duration", 0), time.time()))
    c.commit()
    return 200, {"id": cur.lastrowid}


# ---- Blocking (real trust & safety enforcement, not decorative) ----
def is_blocked_either_way(c, user_a, user_b):
    return c.execute(
        """SELECT 1 FROM blocks WHERE (blocker_id=? AND blocked_id=?) OR (blocker_id=? AND blocked_id=?)""",
        (user_a, user_b, user_b, user_a)).fetchone() is not None


@route("POST", r"/api/block")
def block_user(handler, m, body):
    user = require_auth(handler)
    target_id = body.get("user_id")
    if target_id == user["id"]:
        raise ApiError(400, "Can't block yourself")
    c = db.get_conn()
    if not c.execute("SELECT id FROM users WHERE id=?", (target_id,)).fetchone():
        raise ApiError(404, "User not found")
    c.execute("INSERT OR IGNORE INTO blocks (blocker_id, blocked_id, created_at) VALUES (?,?,?)",
              (user["id"], target_id, time.time()))
    # blocking severs any existing follow relationship in both directions
    c.execute("DELETE FROM follows WHERE (follower_id=? AND followee_id=?) OR (follower_id=? AND followee_id=?)",
              (user["id"], target_id, target_id, user["id"]))
    c.commit()
    return 200, {"ok": True}


@route("POST", r"/api/unblock")
def unblock_user(handler, m, body):
    user = require_auth(handler)
    target_id = body.get("user_id")
    c = db.get_conn()
    c.execute("DELETE FROM blocks WHERE blocker_id=? AND blocked_id=?", (user["id"], target_id))
    c.commit()
    return 200, {"ok": True}


@route("GET", r"/api/blocks")
def list_blocks(handler, m, body):
    user = require_auth(handler)
    c = db.get_conn()
    rows = c.execute(
        """SELECT u.* FROM blocks b JOIN users u ON u.id=b.blocked_id
           WHERE b.blocker_id=? ORDER BY b.created_at DESC""", (user["id"],)).fetchall()
    return 200, {"blocked": [public_user(db.row_to_dict(r)) for r in rows]}


# ---- Reporting + admin moderation ----
VALID_REPORT_TARGETS = {"user", "post", "pulse", "message", "story"}


@route("POST", r"/api/report")
def report_content(handler, m, body):
    user = require_auth(handler)
    target_type = body.get("target_type")
    target_id = body.get("target_id")
    reason = safe_str(body, "reason").strip()
    if target_type not in VALID_REPORT_TARGETS:
        raise ApiError(400, "Invalid target_type")
    if not reason:
        raise ApiError(400, "A reason is required")
    if not isinstance(target_id, int):
        raise ApiError(400, "target_id must be an integer")
    c = db.get_conn()
    cur = c.execute(
        """INSERT INTO reports (reporter_id, target_type, target_id, reason, detail, status, created_at)
           VALUES (?,?,?,?,?, 'open', ?)""",
        (user["id"], target_type, target_id, reason, body.get("detail", ""), time.time()))
    c.commit()
    return 200, {"id": cur.lastrowid, "status": "open"}


@route("GET", r"/api/admin/reports")
def admin_list_reports(handler, m, body):
    require_admin(handler)
    qs = parse_qs(urlparse(handler.path).query)
    status = qs.get("status", ["open"])[0]
    c = db.get_conn()
    if status == "all":
        rows = c.execute(
            """SELECT r.*, u.username AS reporter_username FROM reports r
               JOIN users u ON u.id=r.reporter_id ORDER BY r.created_at DESC LIMIT 200""").fetchall()
    else:
        rows = c.execute(
            """SELECT r.*, u.username AS reporter_username FROM reports r
               JOIN users u ON u.id=r.reporter_id WHERE r.status=? ORDER BY r.created_at DESC LIMIT 200""",
            (status,)).fetchall()
    return 200, {"reports": db.rows_to_list(rows)}


@route("POST", r"/api/admin/reports/(?P<report_id>\d+)/resolve")
def admin_resolve_report(handler, m, body):
    require_admin(handler)
    report_id = int(m.group("report_id"))
    c = db.get_conn()
    c.execute("UPDATE reports SET status='resolved', resolved_at=? WHERE id=?", (time.time(), report_id))
    c.commit()
    return 200, {"ok": True}


@route("POST", r"/api/admin/users/(?P<user_id>\d+)/suspend")
def admin_suspend_user(handler, m, body):
    admin = require_admin(handler)
    target_id = int(m.group("user_id"))
    if target_id == admin["id"]:
        raise ApiError(400, "Can't suspend your own account")
    c = db.get_conn()
    if not c.execute("SELECT id FROM users WHERE id=?", (target_id,)).fetchone():
        raise ApiError(404, "User not found")
    c.execute("UPDATE users SET is_suspended=1 WHERE id=?", (target_id,))
    c.commit()
    return 200, {"ok": True}


@route("POST", r"/api/admin/users/(?P<user_id>\d+)/unsuspend")
def admin_unsuspend_user(handler, m, body):
    require_admin(handler)
    target_id = int(m.group("user_id"))
    c = db.get_conn()
    c.execute("UPDATE users SET is_suspended=0 WHERE id=?", (target_id,))
    c.commit()
    return 200, {"ok": True}


# ---- Ratings (1-5 stars, one per rater per target, upsert on re-rate) ----
VALID_RATING_TARGETS = {"user", "sound", "post", "pulse"}


def _rating_summary(c, target_type, target_id, requester_id):
    row = c.execute(
        "SELECT COUNT(*) n, AVG(stars) avg_stars FROM ratings WHERE target_type=? AND target_id=?",
        (target_type, target_id)).fetchone()
    mine = c.execute(
        "SELECT stars, review FROM ratings WHERE rater_id=? AND target_type=? AND target_id=?",
        (requester_id, target_type, target_id)).fetchone()
    return {
        "count": row["n"] or 0,
        "average": round(row["avg_stars"], 2) if row["avg_stars"] is not None else None,
        "my_rating": {"stars": mine["stars"], "review": mine["review"]} if mine else None,
    }


@route("GET", r"/api/ratings")
def get_ratings(handler, m, body):
    user = require_auth(handler)
    qs = parse_qs(urlparse(handler.path).query)
    target_type = qs.get("target_type", [""])[0]
    target_id = qs.get("target_id", [""])[0]
    if target_type not in VALID_RATING_TARGETS:
        raise ApiError(400, "Invalid target_type")
    if not target_id.isdigit():
        raise ApiError(400, "target_id must be numeric")
    c = db.get_conn()
    return 200, _rating_summary(c, target_type, int(target_id), user["id"])


@route("POST", r"/api/ratings")
def submit_rating(handler, m, body):
    user = require_auth(handler)
    target_type = body.get("target_type")
    target_id = body.get("target_id")
    stars = body.get("stars")
    if target_type not in VALID_RATING_TARGETS:
        raise ApiError(400, "Invalid target_type")
    if not isinstance(target_id, int):
        raise ApiError(400, "target_id must be an integer")
    if not isinstance(stars, int) or not (1 <= stars <= 5):
        raise ApiError(400, "stars must be an integer from 1 to 5")
    if target_type == "user" and target_id == user["id"]:
        raise ApiError(400, "Can't rate yourself")
    review = safe_str(body, "review")[:500]
    c = db.get_conn()
    if target_type == "user" and not c.execute("SELECT id FROM users WHERE id=?", (target_id,)).fetchone():
        raise ApiError(404, "User not found")
    if target_type == "user" and is_blocked_either_way(c, user["id"], target_id):
        raise ApiError(403, "Can't rate this account — one of you has blocked the other.")
    now = time.time()
    c.execute(
        """INSERT INTO ratings (rater_id, target_type, target_id, stars, review, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?)
           ON CONFLICT(rater_id, target_type, target_id)
           DO UPDATE SET stars=excluded.stars, review=excluded.review, updated_at=excluded.updated_at""",
        (user["id"], target_type, target_id, stars, review, now, now))
    c.commit()
    return 200, _rating_summary(c, target_type, target_id, user["id"])


@route("DELETE", r"/api/ratings")
def delete_rating(handler, m, body):
    user = require_auth(handler)
    target_type = body.get("target_type")
    target_id = body.get("target_id")
    if target_type not in VALID_RATING_TARGETS or not isinstance(target_id, int):
        raise ApiError(400, "Invalid target_type/target_id")
    c = db.get_conn()
    c.execute("DELETE FROM ratings WHERE rater_id=? AND target_type=? AND target_id=?",
              (user["id"], target_type, target_id))
    c.commit()
    return 200, _rating_summary(c, target_type, target_id, user["id"])


# ---- Users / contacts ----
@route("GET", r"/api/users")
def search_users(handler, m, body):
    user = require_auth(handler)
    qs = parse_qs(urlparse(handler.path).query)
    q = (qs.get("q", [""])[0]).strip().lower()
    c = db.get_conn()
    if q:
        rows = c.execute(
            "SELECT * FROM users WHERE (username LIKE ? OR display_name LIKE ?) AND id != ? LIMIT 25",
            (f"%{q}%", f"%{q}%", user["id"]),
        ).fetchall()
    else:
        rows = c.execute("SELECT * FROM users WHERE id != ? ORDER BY is_bot DESC, username LIMIT 25",
                          (user["id"],)).fetchall()
    return 200, {"users": [public_user(db.row_to_dict(r)) for r in rows]}


@route("POST", r"/api/contacts")
def add_contact(handler, m, body):
    user = require_auth(handler)
    contact_id = body.get("contact_id")
    c = db.get_conn()
    if not c.execute("SELECT id FROM users WHERE id=?", (contact_id,)).fetchone():
        raise ApiError(404, "User not found")
    if is_blocked_either_way(c, user["id"], contact_id):
        raise ApiError(403, "Can't add this contact — one of you has blocked the other.")
    c.execute("INSERT OR IGNORE INTO contacts (owner_id, contact_id, created_at) VALUES (?,?,?)",
              (user["id"], contact_id, time.time()))
    c.execute("INSERT OR IGNORE INTO contacts (owner_id, contact_id, created_at) VALUES (?,?,?)",
              (contact_id, user["id"], time.time()))
    c.commit()
    get_or_create_direct_chat(user["id"], contact_id)
    return 200, {"ok": True}


@route("GET", r"/api/contacts")
def list_contacts(handler, m, body):
    user = require_auth(handler)
    c = db.get_conn()
    rows = c.execute(
        """SELECT u.* FROM contacts co JOIN users u ON u.id = co.contact_id
           WHERE co.owner_id=? ORDER BY u.display_name""",
        (user["id"],),
    ).fetchall()
    return 200, {"contacts": [public_user(db.row_to_dict(r)) for r in rows]}


@route("GET", r"/api/users/(?P<user_id>\d+)")
def get_user_profile(handler, m, body):
    me_user = require_auth(handler)
    uid = int(m.group("user_id"))
    c = db.get_conn()
    row = c.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    if not row:
        raise ApiError(404, "User not found")
    followers = c.execute("SELECT COUNT(*) n FROM follows WHERE followee_id=?", (uid,)).fetchone()["n"]
    following = c.execute("SELECT COUNT(*) n FROM follows WHERE follower_id=?", (uid,)).fetchone()["n"]
    is_following_row = c.execute("SELECT notify FROM follows WHERE follower_id=? AND followee_id=?",
                                  (me_user["id"], uid)).fetchone()
    is_following = is_following_row is not None
    is_subscribed = bool(is_following_row["notify"]) if is_following_row else False
    pulse_count = c.execute("SELECT COUNT(*) n FROM pulses WHERE user_id=?", (uid,)).fetchone()["n"]
    post_count = c.execute("SELECT COUNT(*) n FROM posts WHERE user_id=?", (uid,)).fetchone()["n"]
    rating = _rating_summary(c, "user", uid, me_user["id"])
    profile = public_user(db.row_to_dict(row))
    profile.update({"followers": followers, "following": following, "is_following": is_following,
                     "is_subscribed": is_subscribed, "pulse_count": pulse_count, "post_count": post_count,
                     "rating": rating})
    return 200, {"user": profile}


@route("GET", r"/api/users/(?P<user_id>\d+)/pulses")
def get_user_pulses(handler, m, body):
    require_auth(handler)
    uid = int(m.group("user_id"))
    c = db.get_conn()
    rows = c.execute("SELECT * FROM pulses WHERE user_id=? ORDER BY id DESC", (uid,)).fetchall()
    return 200, {"pulses": db.rows_to_list(rows)}


@route("GET", r"/api/users/(?P<user_id>\d+)/posts")
def get_user_posts(handler, m, body):
    require_auth(handler)
    uid = int(m.group("user_id"))
    c = db.get_conn()
    rows = c.execute(
        """SELECT p.*, u.username, u.display_name, u.avatar_url FROM posts p
           JOIN users u ON u.id=p.user_id WHERE p.user_id=? ORDER BY p.id DESC""", (uid,)).fetchall()
    return 200, {"posts": db.rows_to_list(rows)}


@route("POST", r"/api/follow")
def follow_user(handler, m, body):
    user = require_auth(handler)
    target_id = body.get("user_id")
    if target_id == user["id"]:
        raise ApiError(400, "Can't follow yourself")
    c = db.get_conn()
    if not c.execute("SELECT id FROM users WHERE id=?", (target_id,)).fetchone():
        raise ApiError(404, "User not found")
    if is_blocked_either_way(c, user["id"], target_id):
        raise ApiError(403, "Can't follow this account — one of you has blocked the other.")
    c.execute("INSERT OR IGNORE INTO follows (follower_id, followee_id, notify, created_at) VALUES (?,?,?,?)",
              (user["id"], target_id, 1 if body.get("notify", True) else 0, time.time()))
    c.commit()
    send_to_user(target_id, {"type": "notification", "kind": "follow", "actor": public_user(user)})
    return 200, {"ok": True}


@route("PATCH", r"/api/follow/notify")
def toggle_follow_notify(handler, m, body):
    """The 'Subscribe' bell: toggles notification-on-new-post for someone you already follow."""
    user = require_auth(handler)
    target_id = body.get("user_id")
    c = db.get_conn()
    existing = c.execute("SELECT notify FROM follows WHERE follower_id=? AND followee_id=?",
                          (user["id"], target_id)).fetchone()
    if not existing:
        raise ApiError(400, "You must follow this user before subscribing to notifications")
    new_val = 0 if existing["notify"] else 1
    c.execute("UPDATE follows SET notify=? WHERE follower_id=? AND followee_id=?",
              (new_val, user["id"], target_id))
    c.commit()
    return 200, {"notify": bool(new_val)}


@route("POST", r"/api/unfollow")
def unfollow_user(handler, m, body):
    user = require_auth(handler)
    target_id = body.get("user_id")
    c = db.get_conn()
    c.execute("DELETE FROM follows WHERE follower_id=? AND followee_id=?", (user["id"], target_id))
    c.commit()
    return 200, {"ok": True}


@route("GET", r"/api/notifications")
def get_notifications(handler, m, body):
    user = require_auth(handler)
    c = db.get_conn()
    uid = user["id"]
    events = []

    def actor_stub(r):
        return {"id": r["id"], "username": r["username"], "display_name": r["display_name"],
                "avatar_url": r["avatar_url"]}

    for r in c.execute(
        """SELECT pl.post_id, u.id AS id, u.username, u.display_name, u.avatar_url
           FROM post_likes pl JOIN posts p ON p.id=pl.post_id JOIN users u ON u.id=pl.user_id
           WHERE p.user_id=? AND pl.user_id!=?""", (uid, uid)).fetchall():
        events.append({"kind": "like", "ts": time.time(), "actor": actor_stub(r), "target": "your post"})
    for r in c.execute(
        """SELECT pr.post_id, pr.created_at AS event_ts, u.id AS id, u.username, u.display_name, u.avatar_url
           FROM post_reposts pr JOIN posts p ON p.id=pr.post_id JOIN users u ON u.id=pr.user_id
           WHERE p.user_id=? AND pr.user_id!=?""", (uid, uid)).fetchall():
        events.append({"kind": "repost", "ts": r["event_ts"], "actor": actor_stub(r), "target": "your post"})
    for r in c.execute(
        """SELECT rp.created_at AS event_ts, u.id AS id, u.username, u.display_name, u.avatar_url, rp.content
           FROM posts rp JOIN posts op ON op.id=rp.reply_to_id JOIN users u ON u.id=rp.user_id
           WHERE op.user_id=? AND rp.user_id!=?""", (uid, uid)).fetchall():
        events.append({"kind": "reply", "ts": r["event_ts"], "actor": actor_stub(r), "target": r["content"][:80]})
    for r in c.execute(
        """SELECT pl.pulse_id, u.id AS id, u.username, u.display_name, u.avatar_url
           FROM pulse_likes pl JOIN pulses p ON p.id=pl.pulse_id JOIN users u ON u.id=pl.user_id
           WHERE p.user_id=? AND pl.user_id!=?""", (uid, uid)).fetchall():
        events.append({"kind": "pulse_like", "ts": time.time(), "actor": actor_stub(r), "target": "your Pulse"})
    for r in c.execute(
        """SELECT pc.created_at AS event_ts, pc.content, u.id AS id, u.username, u.display_name, u.avatar_url
           FROM pulse_comments pc JOIN pulses p ON p.id=pc.pulse_id JOIN users u ON u.id=pc.user_id
           WHERE p.user_id=? AND pc.user_id!=?""", (uid, uid)).fetchall():
        events.append({"kind": "pulse_comment", "ts": r["event_ts"], "actor": actor_stub(r), "target": r["content"][:80]})
    for r in c.execute(
        """SELECT f.created_at AS event_ts, u.id AS id, u.username, u.display_name, u.avatar_url
           FROM follows f JOIN users u ON u.id=f.follower_id WHERE f.followee_id=?""", (uid,)).fetchall():
        events.append({"kind": "follow", "ts": r["event_ts"], "actor": actor_stub(r), "target": "started following you"})
    events.sort(key=lambda e: e["ts"], reverse=True)
    return 200, {"notifications": events[:50]}


@route("GET", r"/api/search")
def global_search(handler, m, body):
    user = require_auth(handler)
    qs = parse_qs(urlparse(handler.path).query)
    q = (qs.get("q", [""])[0]).strip().lower()
    c = db.get_conn()
    users, posts = [], []
    if q:
        users = db.rows_to_list(c.execute(
            "SELECT * FROM users WHERE (username LIKE ? OR display_name LIKE ?) AND id!=? LIMIT 15",
            (f"%{q}%", f"%{q}%", user["id"])).fetchall())
        posts = db.rows_to_list(c.execute(
            """SELECT p.*, u.username, u.display_name, u.avatar_url FROM posts p
               JOIN users u ON u.id=p.user_id WHERE p.content LIKE ? ORDER BY p.id DESC LIMIT 20""",
            (f"%{q}%",)).fetchall())
    return 200, {"users": [public_user(u) for u in users], "posts": posts}


# ---- Chats ----
@route("GET", r"/api/chats")
def list_chats(handler, m, body):
    user = require_auth(handler)
    c = db.get_conn()
    chat_rows = c.execute(
        """SELECT ch.* FROM chats ch JOIN chat_members cm ON cm.chat_id = ch.id
           WHERE cm.user_id=? ORDER BY ch.id DESC""",
        (user["id"],),
    ).fetchall()
    result = []
    for ch in chat_rows:
        ch = db.row_to_dict(ch)
        members = db.rows_to_list(c.execute(
            "SELECT u.* FROM chat_members cm JOIN users u ON u.id=cm.user_id WHERE cm.chat_id=?",
            (ch["id"],)).fetchall())
        last_msg = c.execute(
            "SELECT * FROM messages WHERE chat_id=? AND deleted=0 ORDER BY id DESC LIMIT 1",
            (ch["id"],)).fetchone()
        my_membership = c.execute(
            "SELECT last_read_message_id, wallpaper FROM chat_members WHERE chat_id=? AND user_id=?",
            (ch["id"], user["id"])).fetchone()
        last_read = my_membership["last_read_message_id"] if my_membership else 0
        wallpaper = my_membership["wallpaper"] if my_membership else ""
        unread = c.execute(
            "SELECT COUNT(*) AS n FROM messages WHERE chat_id=? AND id>? AND sender_id!=? AND deleted=0",
            (ch["id"], last_read, user["id"])).fetchone()["n"]
        other = next((mm for mm in members if mm["id"] != user["id"]), None)
        display_name = ch["name"] if ch["is_group"] else (other["display_name"] if other else "Chat")
        avatar = ch["avatar_url"] if ch["is_group"] else (other["avatar_url"] if other else "")
        result.append({
            "id": ch["id"], "is_group": bool(ch["is_group"]), "name": display_name,
            "avatar_url": avatar, "members": [public_user(mm) for mm in members],
            "last_message": db.row_to_dict(last_msg), "unread_count": unread,
            "other_user": public_user(other) if other else None, "wallpaper": wallpaper,
        })
    return 200, {"chats": result}


@route("PATCH", r"/api/chats/(?P<chat_id>\d+)/wallpaper")
def set_chat_wallpaper(handler, m, body):
    user = require_auth(handler)
    chat_id = int(m.group("chat_id"))
    c = db.get_conn()
    _require_membership(c, chat_id, user["id"])
    wallpaper = body.get("wallpaper", "")
    if wallpaper not in VALID_WALLPAPERS and not wallpaper.startswith("/media/"):
        raise ApiError(400, "Invalid wallpaper")
    c.execute("UPDATE chat_members SET wallpaper=? WHERE chat_id=? AND user_id=?",
              (wallpaper, chat_id, user["id"]))
    c.commit()
    return 200, {"ok": True, "wallpaper": wallpaper}


@route("POST", r"/api/chats")
def create_chat(handler, m, body):
    user = require_auth(handler)
    member_ids = body.get("member_ids") or []
    is_group = bool(body.get("is_group")) or len(member_ids) > 1
    c = db.get_conn()
    if not is_group and len(member_ids) == 1:
        chat_id = get_or_create_direct_chat(user["id"], member_ids[0], enforce_block=True)
        return 200, {"chat_id": chat_id}
    cur = c.execute("INSERT INTO chats (is_group, name, created_by, created_at) VALUES (1,?,?,?)",
                     (body.get("name", "New Group"), user["id"], time.time()))
    chat_id = cur.lastrowid
    all_members = set(member_ids) | {user["id"]}
    for uid in all_members:
        c.execute("INSERT OR IGNORE INTO chat_members (chat_id, user_id, joined_at) VALUES (?,?,?)",
                   (chat_id, uid, time.time()))
    c.commit()
    return 200, {"chat_id": chat_id}


def _require_membership(c, chat_id, user_id):
    if not c.execute("SELECT 1 FROM chat_members WHERE chat_id=? AND user_id=?",
                      (chat_id, user_id)).fetchone():
        raise ApiError(403, "Not a member of this chat")


@route("GET", r"/api/chats/(?P<chat_id>\d+)/messages")
def get_messages(handler, m, body):
    user = require_auth(handler)
    chat_id = int(m.group("chat_id"))
    c = db.get_conn()
    _require_membership(c, chat_id, user["id"])
    qs = parse_qs(urlparse(handler.path).query)
    before = int(qs.get("before", [0])[0])
    limit = min(int(qs.get("limit", [50])[0]), 100)
    if before:
        rows = c.execute(
            "SELECT * FROM messages WHERE chat_id=? AND id<? AND deleted=0 ORDER BY id DESC LIMIT ?",
            (chat_id, before, limit)).fetchall()
    else:
        rows = c.execute(
            "SELECT * FROM messages WHERE chat_id=? AND deleted=0 ORDER BY id DESC LIMIT ?",
            (chat_id, limit)).fetchall()
    messages = list(reversed(db.rows_to_list(rows)))
    return 200, {"messages": messages}


@route("POST", r"/api/chats/(?P<chat_id>\d+)/messages")
def post_message(handler, m, body):
    user = require_auth(handler)
    chat_id = int(m.group("chat_id"))
    c = db.get_conn()
    _require_membership(c, chat_id, user["id"])
    chat_row = c.execute("SELECT is_group FROM chats WHERE id=?", (chat_id,)).fetchone()
    if chat_row and not chat_row["is_group"]:
        other_member = c.execute(
            """SELECT user_id FROM chat_members WHERE chat_id=? AND user_id!=?""", (chat_id, user["id"])).fetchone()
        if other_member and is_blocked_either_way(c, user["id"], other_member["user_id"]):
            raise ApiError(403, "Can't send messages in this chat — one of you has blocked the other.")
    content = body.get("content", "")
    kind = body.get("kind", "text")
    media_url = body.get("media_url", "")
    reply_to_id = body.get("reply_to_id")
    if not content and not media_url:
        raise ApiError(400, "Empty message")
    cur = c.execute(
        """INSERT INTO messages (chat_id, sender_id, kind, content, media_url, reply_to_id,
           status, created_at) VALUES (?,?,?,?,?,?,'sent',?)""",
        (chat_id, user["id"], kind, content, media_url, reply_to_id, time.time()),
    )
    c.commit()
    msg = db.row_to_dict(c.execute("SELECT * FROM messages WHERE id=?", (cur.lastrowid,)).fetchone())
    broadcast_to_chat(chat_id, {"type": "message", "message": msg}, exclude_user_id=None)

    # If Gateway is a member of this chat, generate an AI reply asynchronously.
    gateway = db.get_gateway_user()
    is_gateway_chat = c.execute("SELECT 1 FROM chat_members WHERE chat_id=? AND user_id=?",
                             (chat_id, gateway["id"])).fetchone()
    if is_gateway_chat and kind == "text":
        history_rows = c.execute(
            "SELECT sender_id, content FROM messages WHERE chat_id=? AND kind='text' "
            "AND deleted=0 ORDER BY id DESC LIMIT 20", (chat_id,)).fetchall()
        history = [
            {"role": "assistant" if r["sender_id"] == gateway["id"] else "user", "content": r["content"]}
            for r in reversed(history_rows)
        ]
        provider = body.get("provider") or ai_providers.DEFAULT_PROVIDER
        gateway_reply_async(chat_id, user["id"], history, provider)
    return 200, {"message": msg}


@route("POST", r"/api/chats/(?P<chat_id>\d+)/read")
def mark_read(handler, m, body):
    user = require_auth(handler)
    chat_id = int(m.group("chat_id"))
    c = db.get_conn()
    _require_membership(c, chat_id, user["id"])
    last = c.execute("SELECT MAX(id) AS mx FROM messages WHERE chat_id=?", (chat_id,)).fetchone()["mx"] or 0
    c.execute("UPDATE chat_members SET last_read_message_id=? WHERE chat_id=? AND user_id=?",
              (last, chat_id, user["id"]))
    c.commit()
    try:
        gateway_prefs = json.loads(user["gateway_settings"]) if user["gateway_settings"] else {}
    except (ValueError, TypeError):
        gateway_prefs = {}
    read_receipts_on = gateway_prefs.get("read_receipts", PLATFORM_SETTINGS_SCHEMA["gateway"]["read_receipts"])
    if read_receipts_on:
        broadcast_to_chat(chat_id, {"type": "read", "chat_id": chat_id, "user_id": user["id"],
                                     "last_read_message_id": last}, exclude_user_id=user["id"])
    return 200, {"ok": True}


# ---- AI ----
@route("GET", r"/api/ai/providers")
def ai_list_providers(handler, m, body):
    require_auth(handler)
    return 200, {"providers": ai_providers.list_providers(), "default": ai_providers.DEFAULT_PROVIDER}


# ---- Stories (IG-style, 24h ephemeral) ----
@route("GET", r"/api/stories")
def get_stories(handler, m, body):
    user = require_auth(handler)
    c = db.get_conn()
    now = time.time()
    rows = c.execute(
        """SELECT s.*, u.username, u.display_name, u.avatar_url FROM stories s
           JOIN users u ON u.id = s.user_id
           WHERE s.expires_at > ? AND (s.user_id=? OR s.user_id IN
             (SELECT contact_id FROM contacts WHERE owner_id=?))
           ORDER BY s.created_at DESC""",
        (now, user["id"], user["id"]),
    ).fetchall()
    grouped = {}
    for r in rows:
        r = db.row_to_dict(r)
        uid = r["user_id"]
        if uid not in grouped:
            grouped[uid] = {"user_id": uid, "username": r["username"],
                             "display_name": r["display_name"], "avatar_url": r["avatar_url"],
                             "stories": []}
        viewed = c.execute("SELECT 1 FROM story_views WHERE story_id=? AND user_id=?",
                            (r["id"], user["id"])).fetchone() is not None
        grouped[uid]["stories"].append({**r, "viewed": viewed})
    return 200, {"story_groups": list(grouped.values())}


@route("POST", r"/api/stories")
def post_story(handler, m, body):
    user = require_auth(handler)
    now = time.time()
    c = db.get_conn()
    cur = c.execute(
        """INSERT INTO stories (user_id, kind, media_url, caption, bg_color, created_at, expires_at)
           VALUES (?,?,?,?,?,?,?)""",
        (user["id"], body.get("kind", "image"), body.get("media_url", ""), body.get("caption", ""),
         body.get("bg_color", "#25D366"), now, now + STORY_TTL_SECONDS),
    )
    c.commit()
    story = db.row_to_dict(c.execute("SELECT * FROM stories WHERE id=?", (cur.lastrowid,)).fetchone())
    broadcast_to_users(_chat_partner_ids(user["id"]), {"type": "new_story", "story": story,
                                                        "user": public_user(user)})
    return 200, {"story": story}


@route("POST", r"/api/stories/(?P<story_id>\d+)/view")
def view_story(handler, m, body):
    user = require_auth(handler)
    story_id = int(m.group("story_id"))
    c = db.get_conn()
    c.execute("INSERT OR IGNORE INTO story_views (story_id, user_id, viewed_at) VALUES (?,?,?)",
              (story_id, user["id"], time.time()))
    c.commit()
    return 200, {"ok": True}


# ---- Pulse (TikTok-style vertical feed) ----
@route("GET", r"/api/pulse")
def get_pulse(handler, m, body):
    user = require_auth(handler)
    c = db.get_conn()
    qs = parse_qs(urlparse(handler.path).query)
    limit = min(int(qs.get("limit", [20])[0]), 50)
    scope = qs.get("scope", ["foryou"])[0]
    block_clause = """AND p.user_id NOT IN (
        SELECT blocked_id FROM blocks WHERE blocker_id=?
        UNION SELECT blocker_id FROM blocks WHERE blocked_id=?)"""
    if scope == "following":
        rows = c.execute(
            f"""SELECT p.*, u.username, u.display_name, u.avatar_url FROM pulses p
               JOIN users u ON u.id=p.user_id
               WHERE (p.user_id IN (SELECT followee_id FROM follows WHERE follower_id=?) OR p.user_id=?)
               {block_clause}
               ORDER BY p.id DESC LIMIT ?""", (user["id"], user["id"], user["id"], user["id"], limit)).fetchall()
    else:
        rows = c.execute(
            f"""SELECT p.*, u.username, u.display_name, u.avatar_url FROM pulses p
               JOIN users u ON u.id=p.user_id WHERE 1=1 {block_clause}
               ORDER BY p.id DESC LIMIT ?""", (user["id"], user["id"], limit)).fetchall()
    items = []
    for r in rows:
        r = db.row_to_dict(r)
        likes = c.execute("SELECT COUNT(*) n FROM pulse_likes WHERE pulse_id=?", (r["id"],)).fetchone()["n"]
        liked = c.execute("SELECT 1 FROM pulse_likes WHERE pulse_id=? AND user_id=?",
                           (r["id"], user["id"])).fetchone() is not None
        comments = c.execute("SELECT COUNT(*) n FROM pulse_comments WHERE pulse_id=?", (r["id"],)).fetchone()["n"]
        items.append({**r, "likes": likes, "liked_by_me": liked, "comment_count": comments})
    return 200, {"pulses": items}


@route("POST", r"/api/pulse")
def post_pulse(handler, m, body):
    user = require_auth(handler)
    c = db.get_conn()
    cur = c.execute(
        """INSERT INTO pulses (user_id, media_url, kind, caption, sound_name, created_at)
           VALUES (?,?,?,?,?,?)""",
        (user["id"], body.get("media_url", ""), body.get("kind", "video"),
         body.get("caption", ""), body.get("sound_name", "original sound"), time.time()),
    )
    c.commit()
    return 200, {"id": cur.lastrowid}


@route("POST", r"/api/pulse/(?P<pulse_id>\d+)/like")
def like_pulse(handler, m, body):
    user = require_auth(handler)
    pulse_id = int(m.group("pulse_id"))
    c = db.get_conn()
    existing = c.execute("SELECT 1 FROM pulse_likes WHERE pulse_id=? AND user_id=?",
                          (pulse_id, user["id"])).fetchone()
    if existing:
        c.execute("DELETE FROM pulse_likes WHERE pulse_id=? AND user_id=?", (pulse_id, user["id"]))
        liked = False
    else:
        c.execute("INSERT INTO pulse_likes (pulse_id, user_id) VALUES (?,?)", (pulse_id, user["id"]))
        liked = True
    c.commit()
    return 200, {"liked": liked}


@route("GET", r"/api/pulse/(?P<pulse_id>\d+)/comments")
def get_pulse_comments(handler, m, body):
    require_auth(handler)
    pulse_id = int(m.group("pulse_id"))
    c = db.get_conn()
    rows = c.execute(
        """SELECT pc.*, u.username, u.display_name, u.avatar_url FROM pulse_comments pc
           JOIN users u ON u.id=pc.user_id WHERE pc.pulse_id=? ORDER BY pc.id ASC""",
        (pulse_id,)).fetchall()
    return 200, {"comments": db.rows_to_list(rows)}


@route("POST", r"/api/pulse/(?P<pulse_id>\d+)/comments")
def post_pulse_comment(handler, m, body):
    user = require_auth(handler)
    pulse_id = int(m.group("pulse_id"))
    content = safe_str(body, "content").strip()
    if not content:
        raise ApiError(400, "Empty comment")
    c = db.get_conn()
    c.execute("INSERT INTO pulse_comments (pulse_id, user_id, content, created_at) VALUES (?,?,?,?)",
              (pulse_id, user["id"], content, time.time()))
    c.commit()
    return 200, {"ok": True}


# ---- Posts (X-style micro-feed) ----
@route("GET", r"/api/posts")
def get_posts(handler, m, body):
    user = require_auth(handler)
    c = db.get_conn()
    rows = c.execute(
        """SELECT p.*, u.username, u.display_name, u.avatar_url FROM posts p
           JOIN users u ON u.id=p.user_id
           WHERE p.user_id NOT IN (
             SELECT blocked_id FROM blocks WHERE blocker_id=?
             UNION SELECT blocker_id FROM blocks WHERE blocked_id=?)
           ORDER BY p.id DESC LIMIT 50""", (user["id"], user["id"])).fetchall()
    items = []
    for r in rows:
        r = db.row_to_dict(r)
        likes = c.execute("SELECT COUNT(*) n FROM post_likes WHERE post_id=?", (r["id"],)).fetchone()["n"]
        liked = c.execute("SELECT 1 FROM post_likes WHERE post_id=? AND user_id=?",
                           (r["id"], user["id"])).fetchone() is not None
        reposts = c.execute("SELECT COUNT(*) n FROM post_reposts WHERE post_id=?", (r["id"],)).fetchone()["n"]
        replies = c.execute("SELECT COUNT(*) n FROM posts WHERE reply_to_id=?", (r["id"],)).fetchone()["n"]
        reposted = c.execute("SELECT 1 FROM post_reposts WHERE post_id=? AND user_id=?",
                              (r["id"], user["id"])).fetchone() is not None
        items.append({**r, "likes": likes, "liked_by_me": liked, "reposts": reposts, "replies": replies,
                      "reposted_by_me": reposted})
    return 200, {"posts": items}


@route("POST", r"/api/posts")
def create_post(handler, m, body):
    user = require_auth(handler)
    content = safe_str(body, "content").strip()
    if not content:
        raise ApiError(400, "Empty post")
    if len(content) > 280:
        raise ApiError(400, "Posts are capped at 280 characters")
    c = db.get_conn()
    cur = c.execute("INSERT INTO posts (user_id, content, media_url, media_kind, reply_to_id, created_at) VALUES (?,?,?,?,?,?)",
                     (user["id"], content, body.get("media_url", ""), body.get("media_kind", ""),
                      body.get("reply_to_id"), time.time()))
    c.commit()
    return 200, {"id": cur.lastrowid}


@route("POST", r"/api/posts/(?P<post_id>\d+)/like")
def like_post(handler, m, body):
    user = require_auth(handler)
    post_id = int(m.group("post_id"))
    c = db.get_conn()
    existing = c.execute("SELECT 1 FROM post_likes WHERE post_id=? AND user_id=?",
                          (post_id, user["id"])).fetchone()
    if existing:
        c.execute("DELETE FROM post_likes WHERE post_id=? AND user_id=?", (post_id, user["id"]))
        liked = False
    else:
        c.execute("INSERT INTO post_likes (post_id, user_id) VALUES (?,?)", (post_id, user["id"]))
        liked = True
    c.commit()
    return 200, {"liked": liked}


@route("POST", r"/api/posts/(?P<post_id>\d+)/repost")
def repost_post(handler, m, body):
    user = require_auth(handler)
    post_id = int(m.group("post_id"))
    c = db.get_conn()
    c.execute("INSERT OR IGNORE INTO post_reposts (post_id, user_id, created_at) VALUES (?,?,?)",
              (post_id, user["id"], time.time()))
    c.commit()
    return 200, {"ok": True}


# ---- Upload ----
@route("POST", r"/api/upload")
def upload(handler, m, body):
    require_auth(handler)
    filename = body.get("filename", "file")
    data = body.get("data")
    if not data:
        raise ApiError(400, "Missing file data")
    url = save_upload(filename, data)
    return 200, {"url": url}


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------
MEDIA_TYPES = {
    ".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".gif": "image/gif", ".mp4": "video/mp4", ".webm": "video/webm", ".mp3": "audio/mpeg",
}


class Handler(BaseHTTPRequestHandler):
    server_version = "GatewayChat/1.0"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass  # keep console clean; flip on for debugging

    def _send_json(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html: str):
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_svg(self, svg: str):
        body = svg.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "image/svg+xml")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "public, max-age=86400")
        self.end_headers()
        self.wfile.write(body)

    def _cors_preflight(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,PATCH,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type,Authorization")
        self.end_headers()

    def do_OPTIONS(self):
        self._cors_preflight()

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return {}

    def _serve_media(self, path):
        """Only user-uploaded files live on disk under media/uploads/. Everything
        else the app shows (the app shell, all icons, the bot avatar) is Python-
        generated — see /app/templates/."""
        if path == "/media/avatars/gateway.svg":
            self._send_svg(icons.bot_avatar_svg())
            return
        fs_path = os.path.normpath(os.path.join(MEDIA_DIR, path[len("/media/"):]))
        if not fs_path.startswith(os.path.normpath(MEDIA_DIR)):
            self._send_json(403, {"error": "Forbidden"})
            return
        if not os.path.isfile(fs_path):
            self._send_json(404, {"error": "Not found"})
            return
        ext = os.path.splitext(fs_path)[1]
        ctype = MEDIA_TYPES.get(ext) or mimetypes.guess_type(fs_path)[0] or "application/octet-stream"
        with open(fs_path, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _dispatch(self, method):
        start_time = time.time()
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        remote_addr = self.client_address[0] if self.client_address else "unknown"

        if path == "/ws":
            self._handle_websocket()
            return

        if path.startswith("/media/"):
            self._serve_media(path)
            return

        if not path.startswith("/api/"):
            self._send_html(render_page())
            return

        # ---- rate limiting (before we even parse the body or match a route) ----
        if method in ("POST", "PATCH", "PUT", "DELETE"):
            limiter_class = "auth" if path in ("/api/register", "/api/login") else \
                             "message" if re.match(r"^/api/chats/\d+/messages$", path) else "mutation"
            allowed, retry_after = rate_limit.check(limiter_class, remote_addr)
            if not allowed:
                self.send_response(429)
                self.send_header("Content-Type", "application/json")
                self.send_header("Retry-After", str(int(retry_after) + 1))
                body_bytes = json.dumps({"error": "Rate limit exceeded. Try again shortly."}).encode()
                self.send_header("Content-Length", str(len(body_bytes)))
                self.end_headers()
                self.wfile.write(body_bytes)
                logging_util.log_access(method, path, 429, (time.time() - start_time) * 1000, remote_addr=remote_addr)
                return

        body = self._read_body() if method in ("POST", "PATCH", "PUT", "DELETE") else {}
        for route_method, regex, func in ROUTES:
            if route_method != method:
                continue
            match = regex.match(path)
            if match:
                status = 500
                try:
                    status, payload = func(self, match, body)
                    self._send_json(status, payload)
                except ApiError as e:
                    status = e.status
                    self._send_json(e.status, {"error": e.message})
                except Exception as e:  # keep the server alive on unexpected errors
                    status = 500
                    logging_util.log_error(method, path, e)
                    self._send_json(500, {"error": "Internal server error. This has been logged."})
                finally:
                    logging_util.log_access(method, path, status, (time.time() - start_time) * 1000,
                                             remote_addr=remote_addr)
                return
        self._send_json(404, {"error": "No such route"})
        logging_util.log_access(method, path, 404, (time.time() - start_time) * 1000, remote_addr=remote_addr)

    def do_GET(self):
        self._dispatch("GET")

    def do_POST(self):
        self._dispatch("POST")

    def do_PATCH(self):
        self._dispatch("PATCH")

    def do_DELETE(self):
        self._dispatch("DELETE")

    # ---- WebSocket upgrade ----
    def _handle_websocket(self):
        qs = parse_qs(urlparse(self.path).query)
        token = qs.get("token", [None])[0]
        payload = auth.decode_token(token) if token else None
        if not payload:
            self.send_response(401)
            self.end_headers()
            return
        user_id = payload["sub"]
        client_key = self.headers.get("Sec-WebSocket-Key")
        if not client_key:
            self.send_response(400)
            self.end_headers()
            return
        response = wsutil.build_handshake_response(client_key)
        self.connection.sendall(response)

        conn = wsutil.WebSocketConnection(self.connection, user_id)
        register_connection(user_id, conn)
        try:
            while conn.alive:
                text = conn.recv()
                if text is None:
                    break
                if not text:
                    continue
                self._handle_ws_message(user_id, text)
        finally:
            unregister_connection(user_id, conn)

    def _handle_ws_message(self, user_id, text):
        try:
            event = json.loads(text)
        except Exception:
            return
        etype = event.get("type")
        if etype == "typing":
            chat_id = event.get("chat_id")
            if chat_id and get_user_platform_setting(user_id, "gateway", "typing_indicators"):
                broadcast_to_chat(chat_id, {"type": "typing", "chat_id": chat_id, "user_id": user_id},
                                   exclude_user_id=user_id)
        elif etype == "ping":
            send_to_user(user_id, {"type": "pong"})


def run(host="0.0.0.0", port=8000):
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    db.init_db()
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Gateway Chat backend listening on http://{host}:{port}")
    print(f"Default AI provider: {ai_providers.DEFAULT_PROVIDER}  "
          f"(set GATEWAY_PROVIDER env var to change; options: {list(ai_providers.PROVIDERS)})")
    if ai_providers.bittensor_data.is_configured():
        print("Live Bittensor data: ON (TAOSTATS_API_KEY set) — Gateway's assistant "
              "will fold in a live network snapshot when it answers Bittensor questions.")
    else:
        print("Live Bittensor data: OFF (no TAOSTATS_API_KEY set) — Gateway's "
              "assistant will talk about Bittensor generically instead of citing "
              "current numbers. Set TAOSTATS_API_KEY to enable this.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.shutdown()
