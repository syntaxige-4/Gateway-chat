<img src="assets/gateway-logo.svg" alt="Gateway" width="420">

One account, four separate spaces.

## Introduction

Gateway is a self-hosted, real-time messaging app that also folds in three
other social formats — an Instagram-style feed, a TikTok-style vertical
video feed, and an X-style short-text feed — all under one account, switched
from a single hamburger menu instead of four separate apps.

The entire backend and frontend are plain Python: standard library only, no
framework, no build step, no `npm install`. It ships with a real-time
WebSocket layer, SQLite storage, trust & safety tooling (block/report), rate
limiting, structured logging, and an optional in-app AI assistant that can
be backed by any of seven interchangeable providers — several of them
running on Bittensor subnets.

It's for anyone who wants a single small, inspectable, dependency-free
codebase that covers chat + social feeds, rather than standing up four
separate platforms — self-hosters, people learning how a real-time backend
is put together end to end, or anyone extending it into something of their
own.

## Features

- **Four spaces, one account** — DM/group chat, a photo feed, a short
  vertical-video feed, and a short-text feed, switched from one menu.
  Photo posts are shared data between two of the spaces by design.
- **Real-time messaging** over WebSockets, with online-status visibility
  that respects per-user privacy settings.
- **Ratings** (1–5 stars, upsert semantics) that respect blocks.
- **Block / Report**, reachable from the profile overflow menu, enforced
  server-side, not just hidden in the UI.
- **Rate limiting** and **structured logging** on the backend.
- **Per-platform settings**, isolated per space, applied consistently on
  load and on re-render — not just when a toggle is flipped.
- **Camera/mic permissions** for real media capture, plus a personal API
  key for programmatic access.
- **A user-uploaded sounds library** — bring your own audio, not a
  licensed catalog.
- **Optional AI assistant**, backed by any of seven interchangeable
  providers (see below), with an output sanitizer that strips leaked
  tool-call markup and raw Markdown before anything reaches the chat.
- **Optional live Bittensor context** for the assistant via the Taostats
  API — network issuance, market cap, subnet registration cost — with a
  static fallback when no key is configured.

## Running it

No dependencies, so a venv is optional — the app runs directly with the
system Python. If you'd rather keep it isolated:

```bash
cd backend
python3 -m venv venv
source venv/bin/activate      # on Windows: venv\Scripts\activate
pip install -r requirements.txt   # currently a no-op — stdlib only
python3 run.py
```

Or skip the venv entirely:

```bash
cd backend
python3 run.py
```

`ADMIN_USERNAME=yourusername python3 run.py` grants admin rights to an
*existing* account (register first, then restart with this set).

Optional: set `TAOSTATS_API_KEY` before starting to turn on live Bittensor
data for the in-app assistant (see "Bittensor integration" below). Without
it, everything else runs exactly the same.

## AI providers

Seven interchangeable chat-completion backends, selected per-request:

| id | Provider | Base URL | Env var |
|---|---|---|---|
| `gm` **(default)** | GM (SN28) | `https://api.saygm.com/v1` | `GM_API_KEY` |
| `chutes` | Chutes | `https://llm.chutes.ai/v1` | `CHUTES_API_KEY` |
| `targon` | Targon (SN4) | `https://api.targon.com/v1` | `TARGON_API_KEY` |
| `nineteen` | Nineteen (SN19, via Corcel) | `https://api.corcel.io/v1` (verify against current Corcel docs; override via `NINETEEN_BASE_URL`) | `NINETEEN_API_KEY` |
| `lium` | Lium (SN51) | generic OpenAI-compatible slot — Lium is a GPU marketplace, point this at whatever you deploy there | `LIUM_API_KEY` / `LIUM_BASE_URL` |
| `anthropic` | Anthropic | `https://api.anthropic.com/v1` | `ANTHROPIC_API_KEY` |
| `openrouter` | OpenRouter (free) | `https://openrouter.ai/api/v1`, defaults to the `openrouter/free` router model | `OPENROUTER_API_KEY` |

**OpenRouter** is a unified gateway in front of many hosted models (OpenAI,
Anthropic, Meta, Mistral, etc.), speaking the same OpenAI-compatible
`/chat/completions` shape as GM/Chutes. It defaults to OpenRouter's "Free
Models Router" (`openrouter/free`), which rotates among whichever `:free`
models are currently available rather than pinning one by name — override
with `OPENROUTER_MODEL` for a specific `<vendor>/<model>:free` slug. Free
tier: 20 requests/minute account-wide, 50/day until you've ever bought $10+
in credits (one-time, non-expiring), then 1,000/day after.

**Not included, on purpose:** Desearch (SN22) is a real-time search API,
not a chat-completions endpoint, and Bitmind (SN34) is a deepfake/synthetic-
media detector with no conversational interface — neither fits the "chat
with Gateway" provider slot as-is. Both would make sense as separate
features later (Desearch as a web-search tool the assistant calls, Bitmind
as an "is this image AI-generated?" check on uploads).

All provider replies pass through `sanitize_reply()` in `ai_providers.py`
before being stored — it strips leaked tool-call markup some models emit
out of habit (Gateway wires up no tools) and removes Markdown emphasis
characters, since the chat UI renders plain text.

## Bittensor integration

Since several of Gateway's own AI providers (GM, Chutes, Targon, Nineteen)
are themselves Bittensor subnets, the assistant carries Bittensor context
at two levels:

1. **Always on, static** — a plain-English explanation of subnets, miners,
   validators, TAO, and dTAO staking, baked into the system prompt
   (`GATEWAY_SYSTEM_PROMPT` in `ai_providers.py`). Zero configuration.
2. **Optional, live** — set `TAOSTATS_API_KEY` and `bittensor_data.py`
   pulls a real snapshot from the [Taostats API](https://docs.taostats.io)
   (TAO issuance, network market cap, current subnet registration cost),
   cached for five minutes. No key, or a failed request, falls back to the
   static explanation rather than guessing at a number. `python3 run.py`
   prints which mode is active on startup.

This is a working reference for two things other Bittensor builders run
into: routing one feature through several interchangeable subnet-hosted
LLM providers behind a single interface, and folding a live on-chain/API
data source into an LLM's context without it becoming a source of
confidently wrong numbers when that source is unavailable. Both
`ai_providers.py` and `bittensor_data.py` are written to be read, not just
run.

Currently read-only context for the chat assistant — not yet a Model
Context Protocol (MCP) tool the assistant can call mid-conversation to look
something up on demand. Wiring an MCP client in is the natural next step.

## Standalone endpoint checker (for miners)

`backend/scripts/check_provider.py` sends one minimal chat-completion
request to an endpoint and checks the response comes back in the shape a
downstream client actually expects (`choices[0].message.content` for
OpenAI-compatible servers, `content[].text` for the native Anthropic
Messages shape) — the same contract `ai_providers.py` relies on.

It has no dependency on the rest of Gateway beyond that shape check. If
you've stood up your own OpenAI-compatible server — vLLM on a rented Lium
node, for instance — point this at it before depending on it for anything
real:

```bash
cd backend
python3 scripts/check_provider.py \
    --base-url https://your-endpoint.example.com/v1 \
    --api-key sk-... \
    --model your-model-name
```

It reports PASS/FAIL, latency, and *why* it failed (unreachable, wrong HTTP
status, or a 200 response in a shape nothing downstream could parse), and
exits non-zero on failure, so it's safe to drop into a deploy script as a
gate. `--all` runs the same check against every provider that currently has
an API key configured.

## Tests

```bash
cd backend
python3 -m unittest discover tests -v
```

35 tests, stdlib only, run against real server instances — including two
fake local HTTP servers spun up specifically to verify the provider checker
distinguishes a correct response from a wrong one.

## Project layout

```
gateway_chat/
├── assets/
│   └── gateway-logo.svg
├── CONTRIBUTING.md
├── CODE_OF_CONDUCT.md
├── SECURITY.md
├── LICENSE
└── backend/
    ├── run.py
    ├── app/
    │   ├── server.py, db.py, auth.py, wsutil.py
    │   ├── ai_providers.py     # 7 interchangeable LLM providers
    │   ├── bittensor_data.py   # optional live Taostats snapshot
    │   ├── provider_check.py   # endpoint diagnostics (used by scripts/ + admins)
    │   ├── logging_util.py, rate_limit.py
    │   └── templates/   # the entire frontend — all Python
    ├── scripts/
    │   └── check_provider.py   # standalone CLI — useful outside Gateway too
    └── tests/
        └── test_api.py
```

## Known limitations

No payment processing, no native mobile apps, no horizontal scaling beyond
a single SQLite-backed process, no group-chat admin controls, no message
edit/delete, no push notifications. Share links copy correctly but don't
yet deep-link into the app on open. The Bittensor data feed is a periodic
snapshot, not an on-demand MCP tool the assistant can query.

## Contributing

Issues and PRs are welcome — see `CONTRIBUTING.md` for the workflow and
`CODE_OF_CONDUCT.md` for community expectations. `SECURITY.md` has the
process for reporting vulnerabilities privately.

## License

MIT — see `LICENSE`.
