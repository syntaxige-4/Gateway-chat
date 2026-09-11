"""
logging_util.py — structured logging, stdlib only (json + a plain rotating-ish
file writer). Two logs:
  - logs/access.log  : one JSON line per HTTP request (method, path, status,
                        user id if known, duration, remote address)
  - logs/error.log   : one JSON line per unhandled exception, with traceback

This exists because "no logging" was one of the concrete, honest gaps between
a working prototype and something with real operational visibility.
"""
import json
import os
import time
import threading
import traceback

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
_lock = threading.Lock()

MAX_LOG_BYTES = 5 * 1024 * 1024  # rotate a log once it crosses ~5MB


def _ensure_dir():
    os.makedirs(LOG_DIR, exist_ok=True)


def _rotate_if_needed(path):
    try:
        if os.path.exists(path) and os.path.getsize(path) > MAX_LOG_BYTES:
            rotated = path + f".{int(time.time())}"
            os.rename(path, rotated)
    except OSError:
        pass  # best-effort; logging must never crash the request


def _write_line(filename, record):
    _ensure_dir()
    path = os.path.join(LOG_DIR, filename)
    line = json.dumps(record, default=str) + "\n"
    with _lock:
        _rotate_if_needed(path)
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(line)
        except OSError:
            pass


def log_access(method, path, status, duration_ms, user_id=None, remote_addr=None):
    _write_line("access.log", {
        "ts": time.time(), "method": method, "path": path, "status": status,
        "duration_ms": round(duration_ms, 2), "user_id": user_id, "remote_addr": remote_addr,
    })


def log_error(method, path, exc: Exception, user_id=None):
    _write_line("error.log", {
        "ts": time.time(), "method": method, "path": path, "user_id": user_id,
        "error": str(exc), "type": type(exc).__name__,
        "traceback": traceback.format_exc(),
    })
