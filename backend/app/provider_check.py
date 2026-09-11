"""
provider_check.py — diagnostics for OpenAI-compatible and Anthropic-shaped
chat-completion endpoints.

This exists for two audiences:

  1. Gateway's own maintainers: two of the seven configured providers
     (Lium, Nineteen) are marked "best-effort / unconfirmed" in
     ai_providers.py because their exact endpoint shape couldn't be
     verified from public docs alone. check_configured_providers() lets
     you settle that for real, against whatever keys you actually have.

  2. Anyone else, independent of Gateway entirely: if you're a miner who
     just stood up your own OpenAI-compatible server (e.g. vLLM on a
     rented Lium node — the exact scenario ai_providers.py's Lium comment
     describes), you can point check_openai_compat() at it before you
     depend on it in production. This has no dependency on the rest of
     this app — it's a standalone request/response contract check.

What "pass" means here is narrow and deliberate: does the endpoint accept
a minimal chat-completions request and return a response in the shape
Gateway (and most OpenAI-compatible clients) actually parse
(`choices[0].message.content`)? It is not a quality, safety, or
performance benchmark — just "will this integration work at all."
"""
import json
import time
import urllib.request
import urllib.error


def _post_json(url, headers, body, timeout):
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    started = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            elapsed_ms = round((time.monotonic() - started) * 1000, 1)
            return resp.status, json.loads(resp.read().decode("utf-8")), elapsed_ms, None
    except urllib.error.HTTPError as e:
        elapsed_ms = round((time.monotonic() - started) * 1000, 1)
        detail = e.read().decode("utf-8", errors="replace")[:400]
        return e.code, None, elapsed_ms, f"HTTP {e.code}: {detail}"
    except urllib.error.URLError as e:
        elapsed_ms = round((time.monotonic() - started) * 1000, 1)
        return None, None, elapsed_ms, f"could not reach endpoint: {e.reason}"
    except (TimeoutError, OSError) as e:
        elapsed_ms = round((time.monotonic() - started) * 1000, 1)
        return None, None, elapsed_ms, f"timed out or connection error: {e}"
    except ValueError as e:
        elapsed_ms = round((time.monotonic() - started) * 1000, 1)
        return None, None, elapsed_ms, f"response wasn't valid JSON: {e}"


def check_openai_compat(base_url, api_key=None, model="default", timeout=10):
    """Sends one minimal request to {base_url}/chat/completions and checks
    the response has the shape Gateway's adapter actually reads."""
    result = {
        "kind": "openai_compat", "base_url": base_url, "model": model,
        "ok": False, "http_status": None, "latency_ms": None,
        "sample_reply": None, "error": None,
    }
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    body = {
        "model": model,
        "messages": [{"role": "user", "content": "Reply with exactly one word: pong"}],
        "max_tokens": 10,
        "temperature": 0,
    }
    status, payload, elapsed_ms, error = _post_json(
        f"{base_url.rstrip('/')}/chat/completions", headers, body, timeout
    )
    result["http_status"] = status
    result["latency_ms"] = elapsed_ms
    if error:
        result["error"] = error
        return result
    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        result["error"] = (
            "endpoint responded, but not in the expected shape "
            "(choices[0].message.content) — got: " + json.dumps(payload)[:300]
        )
        return result
    result["ok"] = True
    result["sample_reply"] = content[:200]
    return result


def check_anthropic_compat(base_url, api_key, model, timeout=10):
    """Same idea, for the native Anthropic Messages API shape."""
    result = {
        "kind": "anthropic", "base_url": base_url, "model": model,
        "ok": False, "http_status": None, "latency_ms": None,
        "sample_reply": None, "error": None,
    }
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key or "",
        "anthropic-version": "2023-06-01",
    }
    body = {
        "model": model,
        "max_tokens": 10,
        "messages": [{"role": "user", "content": "Reply with exactly one word: pong"}],
    }
    status, payload, elapsed_ms, error = _post_json(
        f"{base_url.rstrip('/')}/messages", headers, body, timeout
    )
    result["http_status"] = status
    result["latency_ms"] = elapsed_ms
    if error:
        result["error"] = error
        return result
    try:
        parts = payload.get("content", [])
        content = "".join(p.get("text", "") for p in parts if p.get("type") == "text")
        if not content:
            raise ValueError("empty content")
    except (KeyError, TypeError, ValueError):
        result["error"] = (
            "endpoint responded, but not in the expected shape "
            "(content[].text) — got: " + json.dumps(payload)[:300]
        )
        return result
    result["ok"] = True
    result["sample_reply"] = content[:200]
    return result


def check_configured_providers(timeout=10):
    """Runs the appropriate check against every provider in
    ai_providers.PROVIDERS that currently has its API key env var set.
    Providers with no key configured are reported as skipped, not failed —
    there's nothing to test yet."""
    import os
    from . import ai_providers  # local import: avoids a circular import at module load

    results = []
    for provider_id, cfg in ai_providers.PROVIDERS.items():
        api_key = os.environ.get(cfg["api_key_env"], "")
        if not api_key and cfg["kind"] != "openai_compat":
            results.append({
                "provider": provider_id, "label": cfg["label"], "skipped": True,
                "reason": f"{cfg['api_key_env']} not set",
            })
            continue
        if not api_key:
            results.append({
                "provider": provider_id, "label": cfg["label"], "skipped": True,
                "reason": f"{cfg['api_key_env']} not set",
            })
            continue
        if cfg["kind"] == "anthropic":
            check = check_anthropic_compat(cfg["base_url"], api_key, cfg["model"], timeout)
        else:
            check = check_openai_compat(cfg["base_url"], api_key, cfg["model"], timeout)
        check["provider"] = provider_id
        check["label"] = cfg["label"]
        check["skipped"] = False
        results.append(check)
    return results
