"""
rate_limit.py — a simple in-memory sliding-window rate limiter, stdlib only.

Not a substitute for a real edge/CDN rate limiter in production (this resets
if the process restarts, and doesn't share state across multiple processes),
but it's a real, working defense against basic spam/abuse/brute-force for a
single-process deployment — which is honestly what this app is.
"""
import time
import threading

_lock = threading.Lock()
_buckets = {}  # key -> list of request timestamps

# (max_requests, window_seconds) per limiter "class"
LIMITS = {
    "auth": (8, 60),         # register/login attempts
    "mutation": (90, 60),    # general POST/PATCH/DELETE
    "message": (40, 20),     # chat message sends (bursty but still bounded)
}


def _cleanup(key, window):
    now = time.time()
    _buckets[key] = [t for t in _buckets.get(key, []) if now - t < window]


def check(limiter_class: str, identity: str):
    """Returns (allowed: bool, retry_after_seconds: float)."""
    max_requests, window = LIMITS[limiter_class]
    key = f"{limiter_class}:{identity}"
    with _lock:
        _cleanup(key, window)
        bucket = _buckets.setdefault(key, [])
        if len(bucket) >= max_requests:
            oldest = bucket[0]
            retry_after = max(0.0, window - (time.time() - oldest))
            return False, retry_after
        bucket.append(time.time())
        return True, 0.0
