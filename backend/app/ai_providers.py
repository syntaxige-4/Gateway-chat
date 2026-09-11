"""
ai_providers.py — "Gateway", the in-app AI assistant.

Gateway can be backed by 7 interchangeable providers. Every provider implements the
same `complete(messages, system) -> str` contract so the rest of the app never
needs to know which one is active. Switch the default with the GATEWAY_PROVIDER env
var, or per-request via the `provider` field the frontend sends.

Providers:
  - "gm"        : GM (Bittensor SN28)   -> https://api.saygm.com/v1   [DEFAULT]
  - "chutes"     : Chutes (Bittensor subnet, serverless AI compute)   -> https://llm.chutes.ai/v1
  - "lium"       : Lium (Bittensor SN51). Lium is primarily a decentralized GPU-rental
                    marketplace rather than a hosted LLM API, so there is no public,
                    documented chat-completions endpoint for it. This adapter is wired
                    as a generic OpenAI-compatible client pointed at LIUM_BASE_URL, so
                    if/when you deploy your own OpenAI-compatible server on a rented
                    Lium node (e.g. vLLM), Gateway can talk to it with zero code changes.
  - "anthropic"  : Anthropic Claude     -> https://api.anthropic.com/v1 (native Messages API)
  - "targon"     : Targon (Bittensor SN4)   -> https://api.targon.com/v1
  - "nineteen"   : Nineteen (Bittensor SN19, via Corcel) -> https://api.corcel.io/v1
  - "openrouter" : OpenRouter (free tier, via Free Models Router) -> https://openrouter.ai/api/v1

All requests use only the Python standard library (urllib), so there's nothing to
pip install.
"""
import json
import os
import re
import urllib.request
import urllib.error

from . import bittensor_data

GATEWAY_SYSTEM_PROMPT = (
    "You are Gateway, the built-in AI assistant inside Gateway Chat, a messaging app. "
    "You are friendly, concise, and helpful. You can discuss anything the user "
    "brings up in chat. Keep replies conversational and not overly long unless "
    "the user asks for depth.\n\n"
    "You also know this app well enough to guide a confused user through it. "
    "Gateway Chat has four spaces, switched via the hamburger menu (top-left):\n"
    "- Gateway (this one): 1:1 and group chats, voice notes (hold the mic button), "
    "photo/video sharing, and Status — tap the circle at the top of the status "
    "list to post a photo, video, text, or voice status that disappears after "
    "24 hours.\n"
    "- Beta: an Instagram-style feed. Tap + to post a photo or video with a "
    "caption; tap a post's heart to like it, the speech-bubble to comment.\n"
    "- Alpha: a TikTok-style vertical video feed called Pulses. Swipe through "
    "videos, tap the heart to like, the share icon to send it elsewhere.\n"
    "- Epsilon: an X/Twitter-style feed for short text posts (280 characters), "
    "with likes, reposts, and replies.\n"
    "To add someone, use + New chat (search their username, or use Add from "
    "Contacts if the browser supports it) — if they're not on Gateway yet, you can "
    "share an invite link with them instead.\n"
    "Settings (gear icon) has your profile (tap your avatar there to change your "
    "photo), a Sounds library for Alpha/Beta posts, Premium, and per-account "
    "switching.\n"
    "If someone asks how to do something in the app, answer from this directly "
    "and concretely — don't make up features that aren't listed here, and if "
    "you're not sure, say so plainly rather than guessing.\n\n"
    "Two things about your own limits, stated precisely so you don't guess "
    "wrong in either direction: (1) You do NOT have access to any tools, "
    "functions, web search, or the ability to invoke external actions of any "
    "kind — there is nothing wired up for you to call, so never attempt a "
    "function/tool call or emit any tool-call syntax; if someone asks for "
    "live external info you can't get (news, search results, video content), "
    "say plainly that you don't have that, in one sentence, and offer what "
    "you can actually do instead — don't invent an elaborate list of fake "
    "restrictions beyond that. (2) Outside of the app and Bittensor topics "
    "above, you are a normal, capable, general-purpose assistant — you can "
    "help with anything else the user brings up (writing, explaining things, "
    "general knowledge, coding, advice, whatever it is) exactly as you "
    "normally would. Being Gateway's assistant adds knowledge, it does not "
    "subtract any of your other ability — never tell the user you're limited "
    "to only app-related or Bittensor-related topics, because that isn't true.\n\n"
    "Formatting: reply in plain conversational text only. This chat does not "
    "render Markdown, so never use **asterisks**, *asterisks*, underscores, "
    "backticks, or '#' headers for emphasis or structure — they'll show up "
    "as literal stray characters instead of formatting. Write plainly the "
    "way you'd write a normal text message; use a dash and a line break for "
    "a list item if you need one, nothing fancier.\n\n"
    "You also have background on Bittensor, since several of your own possible "
    "providers (GM, Chutes, Targon, Nineteen) run on Bittensor subnets. Bittensor "
    "is a decentralized network of 'subnets,' each an open competition where "
    "'miners' provide some service (compute, storage, inference, data, etc.) and "
    "'validators' score that work; both are paid in the network's token, TAO. "
    "Subnet owners also receive a share of emissions. People can stake TAO to a "
    "subnet or a specific validator to back the work they think is valuable, and "
    "the network here uses this dynamic staking (dTAO) to influence which subnets "
    "get more of the emission pool. When someone asks about Bittensor, explain it "
    "at this level plainly. For anything that changes over time — a subnet's "
    "current number, its adoption or activity, TAO's price, specific emission "
    "percentages, or which project is 'the best' at something — say clearly that "
    "you're not certain of the current figures and that they should check a live "
    "source (like taostats.io or the project's own docs) rather than state a "
    "number with confidence."
)


def _strip_markdown_emphasis(text):
    """The chat UI renders plain text, not Markdown, so any **bold**,
    *italic*, or stray asterisks a model outputs would otherwise show up
    literally in the bubble. This removes emphasis markers while keeping
    the wrapped text, then guarantees no asterisk survives at all."""
    text = re.sub(r"\*\*\*(.+?)\*\*\*", r"\1", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text, flags=re.DOTALL)
    text = re.sub(r"(?<!\*)\*(?!\*)([^\n*]+?)(?<!\*)\*(?!\*)", r"\1", text)
    text = re.sub(r"(?m)^(\s*)\*\s+", r"\1- ", text)  # "* item" bullets -> "- item"
    return text.replace("*", "")


_LEAKED_TOOL_CALL_RE = re.compile(
    r"<\s*(dots_function_call|function_calls?|tool_call|tool_use|invoke)\b.*",
    re.IGNORECASE | re.DOTALL,
)


def _strip_leaked_tool_calls(text):
    """Some providers' underlying models emit tool/function-call markup out
    of habit even though Gateway wires up no tools at all — nothing ever
    executes it, so left alone it just leaks raw broken XML into the chat
    (this is a real bug that showed up in testing). If the reply contains
    that markup, strip it; if nothing usable is left afterward, replace it
    with an honest one-line explanation instead of an empty or garbled
    bubble."""
    cleaned = _LEAKED_TOOL_CALL_RE.sub("", text).strip()
    if not cleaned:
        return (
            "I tried to look something up, but I don't actually have a "
            "search tool wired up — I can only work from what I already "
            "know. Want me to answer from that instead?"
        )
    return cleaned


def sanitize_reply(text):
    """Applied to every provider's raw output before it's ever stored or
    shown to a user. Two independent cleanup passes, order matters: strip
    leaked tool-call attempts first (they can contain literal asterisks or
    quotes that would confuse the Markdown pass), then strip Markdown."""
    if not text:
        return text
    text = _strip_leaked_tool_calls(text)
    text = _strip_markdown_emphasis(text)
    return text.strip()


def build_system_prompt():
    """Assembles the system prompt fresh on every call — not a module-level
    constant — specifically so a live Bittensor snapshot (see
    bittensor_data.py) can be folded in when it's available, instead of
    Gateway only ever working from the static paragraph above."""
    prompt = GATEWAY_SYSTEM_PROMPT
    snapshot = bittensor_data.get_snapshot()
    if snapshot:
        prompt += (
            "\n\nLive Bittensor snapshot (pulled from Taostats, cached for a few "
            "minutes so it may be slightly stale): " + snapshot + " Prefer these "
            "numbers over the generic language above when they're relevant, but "
            "still say this is a snapshot rather than the current instant if the "
            "user needs precision."
        )
    return prompt

PROVIDERS = {
    "gm": {
        "label": "GM (SN28)",
        "kind": "openai_compat",
        "base_url": os.environ.get("GM_BASE_URL", "https://api.saygm.com/v1"),
        "api_key_env": "GM_API_KEY",
        "model": os.environ.get("GM_MODEL", "default"),
    },
    "chutes": {
        "label": "Chutes",
        "kind": "openai_compat",
        "base_url": os.environ.get("CHUTES_BASE_URL", "https://llm.chutes.ai/v1"),
        "api_key_env": "CHUTES_API_KEY",
        "model": os.environ.get("CHUTES_MODEL", "Qwen/Qwen3-32B-TEE"),
    },
    "lium": {
        "label": "Lium (SN51)",
        "kind": "openai_compat",
        # No public hosted LLM endpoint is documented for Lium (it's a GPU rental
        # marketplace). Point this at your own OpenAI-compatible server running on
        # a rented Lium node once you have one.
        "base_url": os.environ.get("LIUM_BASE_URL", "https://api.lium.io/v1"),
        "api_key_env": "LIUM_API_KEY",
        "model": os.environ.get("LIUM_MODEL", "default"),
    },
    "anthropic": {
        "label": "Anthropic",
        "kind": "anthropic",
        "base_url": os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com/v1"),
        "api_key_env": "ANTHROPIC_API_KEY",
        "model": os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
    },
    "targon": {
        "label": "Targon (SN4)",
        "kind": "openai_compat",
        # Confirmed: Targon (Bittensor SN4, run by Manifold Labs) exposes a real
        # OpenAI-compatible /chat/completions endpoint.
        "base_url": os.environ.get("TARGON_BASE_URL", "https://api.targon.com/v1"),
        "api_key_env": "TARGON_API_KEY",
        "model": os.environ.get("TARGON_MODEL", "default"),
    },
    "nineteen": {
        "label": "Nineteen (SN19)",
        "kind": "openai_compat",
        # Nineteen (Bittensor SN19) is fronted by Corcel's consumer API. I could not
        # fully confirm Corcel's exact base URL/path from public docs at the time
        # this was written (same caveat as Lium below) — verify and override via
        # env var if this doesn't match Corcel's current documented endpoint.
        "base_url": os.environ.get("NINETEEN_BASE_URL", "https://api.corcel.io/v1"),
        "api_key_env": "NINETEEN_API_KEY",
        "model": os.environ.get("NINETEEN_MODEL", "default"),
    },
    "openrouter": {
        "label": "OpenRouter (free)",
        "kind": "openai_compat",
        # OpenRouter is a unified gateway in front of many hosted models (OpenAI,
        # Anthropic, Meta, Mistral, etc.), speaking the standard OpenAI-compatible
        # /chat/completions shape, so it slots into the same adapter as GM/Chutes.
        #
        # Defaulted to OpenRouter's own "Free Models Router" (model id
        # "openrouter/free"), which randomly selects among whichever individual
        # :free models are currently available rather than pinning one by name —
        # individual free models rotate in/out with little notice, so pinning e.g.
        # "meta-llama/llama-3.2-3b-instruct:free" directly can silently 404 later.
        # Override OPENROUTER_MODEL with any other "<vendor>/<model>:free" slug if
        # you want a specific model instead of the router.
        #
        # Free-tier requirements/limits (no card needed, just an account + API key):
        #   - 20 requests/minute, account-wide (not per model)
        #   - 50 requests/day until you've ever bought $10+ in credits (one-time,
        #     credits don't expire), then 1,000 requests/day permanently after
        #   - a 429 here means you've hit one of the above, not a bug
        "base_url": os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        "api_key_env": "OPENROUTER_API_KEY",
        "model": os.environ.get("OPENROUTER_MODEL", "openrouter/free"),
    },
}

# Two Bittensor services were explicitly requested but are NOT wired in above,
# on purpose, with the reason stated plainly rather than silently ignored:
#
#   - Desearch (SN22): a real-time search API (X/Reddit/Arxiv/web results with
#     sentiment/metadata analysis) — not a chat-completions endpoint. Sending a
#     chat message to it wouldn't do anything meaningful; it answers "search
#     queries," not "have a conversation." Would fit as a future *search* tool
#     for Gateway to call, not as another entry in this chat-provider dropdown.
#   - Bitmind (SN34): a deepfake/synthetic-media *detector* — given an image, it
#     returns whether it's AI-generated plus a confidence score. It has no
#     conversational interface at all. Would fit as a future "check this image"
#     feature (e.g. on media uploads), not as a chat provider.
#
# Wiring either into this dropdown as if they were interchangeable with
# GM/Chutes/Targon would silently do nothing useful when selected — worse than
# not including them.

DEFAULT_PROVIDER = os.environ.get("GATEWAY_PROVIDER", "gm")


class AIError(Exception):
    pass


def list_providers():
    return [
        {"id": pid, "label": cfg["label"], "model": cfg["model"]}
        for pid, cfg in PROVIDERS.items()
    ]


def _post_json(url, headers, body, timeout=30):
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise AIError(f"{e.code} from provider: {detail[:400]}")
    except urllib.error.URLError as e:
        raise AIError(f"could not reach provider: {e.reason}")


def _complete_openai_compat(cfg, messages, system):
    api_key = os.environ.get(cfg["api_key_env"], "")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    full_messages = [{"role": "system", "content": system}] + messages
    body = {"model": cfg["model"], "messages": full_messages, "temperature": 0.7}
    result = _post_json(f"{cfg['base_url'].rstrip('/')}/chat/completions", headers, body)
    try:
        return result["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise AIError(f"unexpected response shape from provider: {json.dumps(result)[:300]}")


def _complete_anthropic(cfg, messages, system):
    api_key = os.environ.get(cfg["api_key_env"], "")
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
    }
    body = {
        "model": cfg["model"],
        "max_tokens": 1024,
        "system": system,
        "messages": messages,
    }
    result = _post_json(f"{cfg['base_url'].rstrip('/')}/messages", headers, body)
    try:
        parts = result.get("content", [])
        return "".join(p.get("text", "") for p in parts if p.get("type") == "text")
    except (KeyError, TypeError):
        raise AIError(f"unexpected response shape from provider: {json.dumps(result)[:300]}")


def complete(messages, provider=None, system=None):
    """messages: list of {"role": "user"|"assistant", "content": str}"""
    if system is None:
        system = build_system_prompt()
    provider = provider or DEFAULT_PROVIDER
    cfg = PROVIDERS.get(provider)
    if cfg is None:
        raise AIError(f"unknown provider '{provider}'")
    api_key = os.environ.get(cfg["api_key_env"], "")
    if not api_key:
        return (
            f"[Gateway] I'm configured to use {cfg['label']} right now, but no "
            f"{cfg['api_key_env']} is set on the server, so I can't reach the model yet. "
            f"Export {cfg['api_key_env']} and restart the backend to bring me online."
        )
    if cfg["kind"] == "anthropic":
        reply = _complete_anthropic(cfg, messages, system)
    else:
        reply = _complete_openai_compat(cfg, messages, system)
    return sanitize_reply(reply)
