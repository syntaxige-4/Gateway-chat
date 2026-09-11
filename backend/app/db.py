"""
db.py — SQLite persistence layer for Gateway Chat.
Zero external dependencies: uses the Python standard library `sqlite3` module only.
"""
import sqlite3
import os
import time
import json
import threading

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "gatewaychat.db")

_local = threading.local()


def get_conn():
    """Thread-local SQLite connection (SQLite connections aren't thread-safe to share)."""
    if not hasattr(_local, "conn"):
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        _local.conn = conn
    return _local.conn


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    display_name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    salt TEXT NOT NULL,
    avatar_url TEXT DEFAULT '',
    bio TEXT DEFAULT '',
    status TEXT DEFAULT 'Hey there! I am using Gateway Chat.',
    is_bot INTEGER DEFAULT 0,
    is_online INTEGER DEFAULT 0,
    last_seen REAL DEFAULT 0,
    default_mode TEXT DEFAULT 'gateway',
    theme TEXT DEFAULT 'midnight',
    is_premium INTEGER DEFAULT 0,
    permissions_state TEXT DEFAULT '{}',
    api_key_hash TEXT DEFAULT '',
    api_key_created_at REAL DEFAULT 0,
    gateway_settings TEXT DEFAULT '{}',
    beta_settings TEXT DEFAULT '{}',
    epsilon_settings TEXT DEFAULT '{}',
    alpha_settings TEXT DEFAULT '{}',
    is_admin INTEGER DEFAULT 0,
    is_suspended INTEGER DEFAULT 0,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS contacts (
    owner_id INTEGER NOT NULL,
    contact_id INTEGER NOT NULL,
    created_at REAL NOT NULL,
    PRIMARY KEY (owner_id, contact_id),
    FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (contact_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS chats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    is_group INTEGER DEFAULT 0,
    name TEXT DEFAULT '',
    avatar_url TEXT DEFAULT '',
    created_by INTEGER,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS chat_members (
    chat_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    role TEXT DEFAULT 'member',
    joined_at REAL NOT NULL,
    last_read_message_id INTEGER DEFAULT 0,
    wallpaper TEXT DEFAULT '',
    PRIMARY KEY (chat_id, user_id),
    FOREIGN KEY (chat_id) REFERENCES chats(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    sender_id INTEGER NOT NULL,
    kind TEXT DEFAULT 'text',
    content TEXT DEFAULT '',
    media_url TEXT DEFAULT '',
    reply_to_id INTEGER,
    status TEXT DEFAULT 'sent',
    created_at REAL NOT NULL,
    edited INTEGER DEFAULT 0,
    deleted INTEGER DEFAULT 0,
    FOREIGN KEY (chat_id) REFERENCES chats(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS message_reactions (
    message_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    emoji TEXT NOT NULL,
    PRIMARY KEY (message_id, user_id, emoji)
);

CREATE TABLE IF NOT EXISTS stories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    kind TEXT DEFAULT 'image',
    media_url TEXT DEFAULT '',
    caption TEXT DEFAULT '',
    bg_color TEXT DEFAULT '#25D366',
    created_at REAL NOT NULL,
    expires_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS story_views (
    story_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    viewed_at REAL NOT NULL,
    PRIMARY KEY (story_id, user_id)
);

CREATE TABLE IF NOT EXISTS pulses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    media_url TEXT DEFAULT '',
    kind TEXT DEFAULT 'video',
    caption TEXT DEFAULT '',
    sound_name TEXT DEFAULT 'original sound',
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS pulse_likes (
    pulse_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    PRIMARY KEY (pulse_id, user_id)
);

CREATE TABLE IF NOT EXISTS pulse_comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pulse_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    content TEXT NOT NULL,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    content TEXT NOT NULL,
    media_url TEXT DEFAULT '',
    media_kind TEXT DEFAULT '',
    reply_to_id INTEGER,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS post_likes (
    post_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    PRIMARY KEY (post_id, user_id)
);

CREATE TABLE IF NOT EXISTS post_reposts (
    post_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    created_at REAL NOT NULL,
    PRIMARY KEY (post_id, user_id)
);

CREATE TABLE IF NOT EXISTS follows (
    follower_id INTEGER NOT NULL,
    followee_id INTEGER NOT NULL,
    notify INTEGER DEFAULT 1,
    created_at REAL NOT NULL,
    PRIMARY KEY (follower_id, followee_id)
);

CREATE TABLE IF NOT EXISTS sounds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    artist TEXT DEFAULT '',
    file_url TEXT NOT NULL,
    duration REAL DEFAULT 0,
    use_count INTEGER DEFAULT 0,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS blocks (
    blocker_id INTEGER NOT NULL,
    blocked_id INTEGER NOT NULL,
    created_at REAL NOT NULL,
    PRIMARY KEY (blocker_id, blocked_id)
);

CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reporter_id INTEGER NOT NULL,
    target_type TEXT NOT NULL,
    target_id INTEGER NOT NULL,
    reason TEXT NOT NULL,
    detail TEXT DEFAULT '',
    status TEXT DEFAULT 'open',
    created_at REAL NOT NULL,
    resolved_at REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS ratings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rater_id INTEGER NOT NULL,
    target_type TEXT NOT NULL,
    target_id INTEGER NOT NULL,
    stars INTEGER NOT NULL,
    review TEXT DEFAULT '',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    UNIQUE(rater_id, target_type, target_id)
);

CREATE INDEX IF NOT EXISTS idx_ratings_target ON ratings(target_type, target_id);
CREATE INDEX IF NOT EXISTS idx_reports_status ON reports(status, created_at);
CREATE INDEX IF NOT EXISTS idx_messages_chat ON messages(chat_id, created_at);
CREATE INDEX IF NOT EXISTS idx_stories_user ON stories(user_id, expires_at);
CREATE INDEX IF NOT EXISTS idx_pulses_created ON pulses(created_at);
CREATE INDEX IF NOT EXISTS idx_posts_created ON posts(created_at);
CREATE INDEX IF NOT EXISTS idx_sounds_created ON sounds(created_at);
"""


def init_db():
    conn = get_conn()
    conn.executescript(SCHEMA)
    conn.commit()
    _migrate(conn)
    _seed_gateway_bot(conn)


def _migrate(conn):
    """Idempotent, additive migrations for databases created by older versions of this app."""
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
    if "default_mode" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN default_mode TEXT DEFAULT 'gateway'")
    if "theme" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN theme TEXT DEFAULT 'midnight'")
    if "is_premium" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN is_premium INTEGER DEFAULT 0")
    if "permissions_state" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN permissions_state TEXT DEFAULT '{}'")
    if "api_key_hash" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN api_key_hash TEXT DEFAULT ''")
    if "api_key_created_at" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN api_key_created_at REAL DEFAULT 0")
    for platform in ("gateway", "beta", "epsilon", "alpha"):
        col = f"{platform}_settings"
        if col not in cols:
            conn.execute(f"ALTER TABLE users ADD COLUMN {col} TEXT DEFAULT '{{}}'")
    cm_cols = {row["name"] for row in conn.execute("PRAGMA table_info(chat_members)").fetchall()}
    if "wallpaper" not in cm_cols:
        conn.execute("ALTER TABLE chat_members ADD COLUMN wallpaper TEXT DEFAULT ''")
    f_cols = {row["name"] for row in conn.execute("PRAGMA table_info(follows)").fetchall()}
    if "notify" not in f_cols:
        conn.execute("ALTER TABLE follows ADD COLUMN notify INTEGER DEFAULT 1")
    if "is_admin" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0")
    if "is_suspended" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN is_suspended INTEGER DEFAULT 0")
    p_cols = {row["name"] for row in conn.execute("PRAGMA table_info(posts)").fetchall()}
    if "media_kind" not in p_cols:
        conn.execute("ALTER TABLE posts ADD COLUMN media_kind TEXT DEFAULT ''")
    conn.execute("""CREATE TABLE IF NOT EXISTS sounds (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, title TEXT NOT NULL,
        artist TEXT DEFAULT '', file_url TEXT NOT NULL, duration REAL DEFAULT 0,
        use_count INTEGER DEFAULT 0, created_at REAL NOT NULL)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS blocks (
        blocker_id INTEGER NOT NULL, blocked_id INTEGER NOT NULL, created_at REAL NOT NULL,
        PRIMARY KEY (blocker_id, blocked_id))""")
    conn.execute("""CREATE TABLE IF NOT EXISTS reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT, reporter_id INTEGER NOT NULL, target_type TEXT NOT NULL,
        target_id INTEGER NOT NULL, reason TEXT NOT NULL, detail TEXT DEFAULT '',
        status TEXT DEFAULT 'open', created_at REAL NOT NULL, resolved_at REAL DEFAULT 0)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS ratings (
        id INTEGER PRIMARY KEY AUTOINCREMENT, rater_id INTEGER NOT NULL, target_type TEXT NOT NULL,
        target_id INTEGER NOT NULL, stars INTEGER NOT NULL, review TEXT DEFAULT '',
        created_at REAL NOT NULL, updated_at REAL NOT NULL,
        UNIQUE(rater_id, target_type, target_id))""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ratings_target ON ratings(target_type, target_id)")
    conn.commit()
    _promote_admin_from_env(conn)


def _promote_admin_from_env(conn):
    """If ADMIN_USERNAME is set, ensure that account has moderation rights.
    This is deliberately the only way to grant admin — there is no API route
    that can do it, so it can't be abused by a compromised session token."""
    username = os.environ.get("ADMIN_USERNAME", "").strip().lower()
    if not username:
        return
    conn.execute("UPDATE users SET is_admin=1 WHERE username=?", (username,))
    conn.commit()


def _seed_gateway_bot(conn):
    """Ensure the 'Gateway' AI assistant exists as user id reserved, username 'gateway'."""
    row = conn.execute("SELECT id FROM users WHERE username = 'gateway'").fetchone()
    if row is None:
        from .auth import hash_password
        pw_hash, salt = hash_password("gateway-is-not-a-real-password")
        conn.execute(
            """INSERT INTO users (username, display_name, password_hash, salt,
               avatar_url, bio, status, is_bot, is_online, last_seen, created_at)
               VALUES (?,?,?,?,?,?,?,1,1,?,?)""",
            ("gateway", "Gateway", pw_hash, salt, "/media/avatars/gateway.svg",
             "I'm Gateway — your AI copilot. Ask me anything.",
             "Always online", time.time(), time.time()),
        )
        conn.commit()


def get_gateway_user():
    conn = get_conn()
    return conn.execute("SELECT * FROM users WHERE username = 'gateway'").fetchone()


def row_to_dict(row):
    if row is None:
        return None
    return {k: row[k] for k in row.keys()}


def rows_to_list(rows):
    return [row_to_dict(r) for r in rows]
