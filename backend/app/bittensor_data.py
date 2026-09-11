"""
bittensor_data.py — best-effort *live* snapshot of the Bittensor network,
pulled from the Taostats API, for Gateway's AI assistant to reference
instead of leaning entirely on the static description baked into its
system prompt.

This is intentionally optional and fails soft:
  - If TAOSTATS_API_KEY isn't set, this does nothing (no network call at
    all) and Gateway falls back to talking about Bittensor generically.
  - If the request fails for any reason (network, rate limit, a changed
    response schema), this returns None and Gateway falls back the same
    way — it does not guess at numbers or fabricate a snapshot.
  - Results are cached for CACHE_TTL_SECONDS so a burst of chat messages
    doesn't turn into a burst of API calls.

Endpoints used (per Taostats' own docs at docs.taostats.io/reference):
  - GET https://api.taostats.io/api/stats/latest/v1
        "Get the latest high level stats from the chain."
  - GET https://api.taostats.io/api/subnet/registration_cost/latest/v1
        current cost, in TAO, to register a new subnet

Auth: header `Authorization: <TAOSTATS_API_KEY>`. Taostats rate-limits
unauthenticated/unkeyed requests heavily, so this module treats a missing
key the same as "feature not configured" rather than trying anyway.

Honesty note, in the same spirit as the caveats already in this file's
sibling module (ai_providers.py) for Lium/Nineteen: I couldn't exercise
these endpoints against a live key while writing this (no network access
in the environment this was built in), so the exact response field names
below (`data`, `issuance`, `market_cap`, `registration_cost`) are taken
from Taostats' published docs and examples, not from a response I
inspected myself. Every field access below goes through .get() with a
fallback specifically because of that — if Taostats changes their shape,
this should degrade to "no snapshot available," not crash and not print
a wrong number. If you wire this up for real, it's worth a quick manual
check against https://docs.taostats.io/reference that these field names
still match, and adjusting them here if not.
"""
import json
import os
import time
import urllib.request
import urllib.error

TAOSTATS_BASE = os.environ.get("TAOSTATS_BASE_URL", "https://api.taostats.io/api")
TAOSTATS_API_KEY = os.environ.get("TAOSTATS_API_KEY", "")

CACHE_TTL_SECONDS = 5 * 60  # don't hit the API on every single chat message

_cache = {"snapshot": None, "fetched_at": 0.0}


def _get(path, timeout=5):
    req = urllib.request.Request(
        f"{TAOSTATS_BASE}{path}",
        headers={"Authorization": TAOSTATS_API_KEY, "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _first_row(payload):
    """Taostats' documented response shape wraps results in a top-level
    "data" list. Defensive because this wasn't verified against a live
    response — see the module honesty note above."""
    if isinstance(payload, dict):
        rows = payload.get("data")
        if isinstance(rows, list) and rows:
            return rows[0]
    return {}


def _fetch_snapshot():
    """Returns a short plain-English summary string, or None if the data
    genuinely isn't available (no key, request failed, or nothing usable
    came back)."""
    if not TAOSTATS_API_KEY:
        return None
    try:
        stats_row = _first_row(_get("/stats/latest/v1"))
        reg_row = _first_row(_get("/subnet/registration_cost/latest/v1"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, ValueError):
        return None

    parts = []
    issuance = stats_row.get("issuance")
    if issuance is not None:
        parts.append(f"total TAO issuance is around {issuance}")
    market_cap = stats_row.get("market_cap")
    if market_cap is not None:
        parts.append(f"network market cap is roughly {market_cap}")
    lock_cost = reg_row.get("registration_cost") or reg_row.get("lock_cost")
    if lock_cost is not None:
        parts.append(f"the current cost to register a new subnet is about {lock_cost} TAO")

    if not parts:
        return None
    return "As of the last check: " + "; ".join(parts) + "."


def get_snapshot(force=False):
    """Cached, rate-limited fetch. Returns a summary string, or None if
    unavailable (feature not configured, or the fetch failed)."""
    now = time.time()
    if not force and _cache["snapshot"] is not None and (now - _cache["fetched_at"]) < CACHE_TTL_SECONDS:
        return _cache["snapshot"]
    snapshot = _fetch_snapshot()
    _cache["snapshot"] = snapshot
    _cache["fetched_at"] = now
    return snapshot


def is_configured():
    return bool(TAOSTATS_API_KEY)
