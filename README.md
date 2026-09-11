<img src="assets/gateway-logo.svg" alt="Gateway" width="420">

One account, four separate spaces.

## Introduction

Gateway is a self-hosted, real-time messaging app that also folds in three
other social formats — an Instagram-style feed, a TikTok-style vertical
video feed, and an X-style short-text feed — all under one account, switched
from a single hamburger menu instead of four separate apps. The entire
backend and frontend are plain Python (standard library only, no framework,
no build step), with a real-time WebSocket layer, SQLite storage, trust &
safety tooling (block/report), rate limiting, structured logging, and an
optional in-app AI assistant that can be backed by any of seven
interchangeable providers — several of them running on Bittensor subnets.

It's meant for anyone who wants a single small, inspectable, dependency-free
codebase that covers chat + social feeds, rather than standing up four
separate platforms — self-hosters, people learning how a real-time backend
is put together end to end, or anyone extending it into something of their
own. **35 automated tests, deliberately 100% Python source, no build step.**

## What changed this pass — three real bugs, fixed with evidence

1. **Share/invite links silently did nothing.** `navigator.clipboard` is
   `undefined` outside a secure context (e.g. opening the app via a LAN IP on
   your phone instead of `localhost`) — the old code checked for it, found
   nothing, and did absolutely nothing, with zero visible feedback. Fixed:
   a real fallback (`execCommand('copy')` via a hidden textarea) and a
   visible toast confirming success — or, if copying truly isn't possible,
   a `prompt()` showing the link so it can be copied by hand. Verified live:
   registered an account, clicked a real share button through a simulated
   click, confirmed the toast appeared and the correct link was captured.

2. **No invite-link fallback when a contact search came up empty.** Fixed:
   searching for someone who isn't on Gateway now shows "no one found — share an
   invite link" instead of a dead-end empty list. Verified live: searched for
   a nonexistent username, confirmed the fallback rendered, clicked it,
   confirmed a real invite link landed in the clipboard with a visible
   confirmation. Also verified the happy path still works: searching for a
   real user shows them, clicking adds the contact and opens the chat
   directly — the invite fallback correctly does *not* appear when a match
   exists.

3. **Navigation was a persistent bottom bar; now each platform is a genuinely
   separate space.** Replaced with a hamburger icon (☰, top-left) that opens
   a dropdown listing the other three spaces plus **General Settings** —
   clicking one switches into that space entirely. The redundant "message"
   shortcut icon that lived in Beta/Epsilon/Alpha's headers is gone (its job
   is now covered by the space switcher). Verified live end-to-end: opened
   the menu, confirmed the current space is marked, clicked into Beta,
   confirmed the mode actually switched (not just the label — the underlying
   view visibility too), reopened the menu and confirmed Beta was now marked
   current, and confirmed clicking Settings both opens it and closes the menu.

None of these three were "trust me, I checked the code" — each was run
against a real server instance with simulated real clicks, and in the
process this uncovered **five bugs in my own test harness** (a `.className`
sync gap, a `.focus()`/`.click()` gap, a missing `.id` property, no support
for compound `"#id .class"` selectors, and — the deepest one — the harness
never actually parsed dynamically-assigned `innerHTML` into real queryable
child elements, which is the exact pattern this app uses for post/pulse
cards and the new invite-fallback UI). I'm listing my own tooling bugs
because the standard I'm holding this app to should apply to how I verify
it too.

## AI providers — now 7, with two explicitly and honestly left out

Requested were Lium, Chutes, GM, Targon, Desearch, Nineteen.ai, and Bitmind
(SN34). Added the four that are genuine chat-completion backends, plus
Anthropic and a free-tier OpenRouter option:

| id | Provider | Base URL | Env var |
|---|---|---|---|
| `gm` **(default)** | GM (SN28) | `https://api.saygm.com/v1` | `GM_API_KEY` |
| `chutes` | Chutes | `https://llm.chutes.ai/v1` | `CHUTES_API_KEY` |
| `targon` | Targon (SN4) | `https://api.targon.com/v1` (confirmed) | `TARGON_API_KEY` |
| `nineteen` | Nineteen (SN19, via Corcel) | `https://api.corcel.io/v1` (best-effort — see note below) | `NINETEEN_API_KEY` |
| `lium` | Lium (SN51) | generic OpenAI-compat slot — Lium is a GPU marketplace with no public hosted LLM endpoint | `LIUM_API_KEY` / `LIUM_BASE_URL` |
| `anthropic` | Anthropic | `https://api.anthropic.com/v1` | `ANTHROPIC_API_KEY` |
| `openrouter` | OpenRouter (free) | `https://openrouter.ai/api/v1`, defaults to the `openrouter/free` router model | `OPENROUTER_API_KEY` |

**On OpenRouter:** it's a unified gateway in front of many hosted models
(OpenAI, Anthropic, Meta, Mistral, etc.), speaking the same OpenAI-compatible
`/chat/completions` shape as GM/Chutes, so it slots into the same adapter.
It defaults to OpenRouter's "Free Models Router" (`openrouter/free`), which
rotates among whichever `:free` models are currently available rather than
pinning one by name — individual free models can 404 with little notice, so
the router is the safer default. Override with `OPENROUTER_MODEL` for a
specific `<vendor>/<model>:free` slug instead. Free-tier limits: 20
requests/minute account-wide, 50 requests/day until you've ever bought $10+
in credits (one-time, non-expiring), then 1,000/day permanently after — a
429 here means you've hit one of those, not a bug.

**Not wired in, on purpose:**
- **Desearch (SN22)** is a real-time search API (X/Reddit/Arxiv/web results)
  — not a chat-completions endpoint. There's nothing for "send it a chat
  message" to do.
- **Bitmind (SN34)** is a deepfake/synthetic-media *detector* — given an
  image, it returns whether it's AI-generated and a confidence score. It has
  no conversational interface at all.

Putting either into the "chat with Gateway" provider dropdown would silently do
nothing useful when selected. Both would make sense as *different* features
later (Desearch as a web-search tool for Gateway to call, Bitmind as an
"is this image AI-generated?" check on uploads) — not as another entry in
this list.

**Honesty note on Nineteen/Corcel:** I could not fully confirm the exact
documented base URL/path from public sources — same caveat as Lium had
before. Verify and override via `NINETEEN_BASE_URL` if it doesn't match
Corcel's current docs.

## Bug found from actual live testing — raw junk leaking into the chat

Running this for real (not just unit tests) surfaced two genuine bugs in
how the AI assistant's replies made it to the screen, both now fixed in
`ai_providers.py`:

1. **Leaked tool-call syntax.** Some providers' underlying models emit
   tool/function-call markup out of habit (e.g. `<dots_function_call>
   <invoke name="search">`), even though Gateway wires up no tools at all.
   Nothing ever executed that markup — it just got saved and broadcast to
   the chat as raw broken text, because nothing was checking the
   provider's output before storing it.
2. **Literal Markdown in a plain-text chat bubble.** Providers naturally
   write `**bold**` and `*italic*`; the chat UI has no Markdown renderer,
   so those asterisks showed up as literal characters. One instance of
   this bug was even hardcoded into Gateway's own code — the "no API key
   configured" fallback message used `**{label}**`.

Both are now handled by `sanitize_reply()`, applied to every reply before
it's ever stored: leaked tool-call markup is stripped (falling back to an
honest one-line explanation if nothing else was said), and all Markdown
emphasis is removed. The system prompt was also tightened to explicitly
tell the model it has no tools to call and shouldn't self-impose
restrictions beyond what's actually true — smaller/free-tier models don't
always follow instructions faithfully, which is exactly why the code-level
fix matters more than the prompt wording alone. 6 new tests pin down both
exact failure modes so they can't silently regress.

## Settings expanded, and audited whether buttons actually do anything

Two real things came out of testing this live:

1. **Every button was checked against the backend.** I cross-referenced
   all 39 distinct API calls the frontend makes against every route the
   backend defines — all 39 matched. No orphaned buttons, no dead
   endpoints. (I'd suspected the Beta feed's comment button was hitting
   the wrong endpoint; it wasn't — Beta and Alpha deliberately share the
   same underlying `pulses` data, so a photo posted in Beta shows up in
   Alpha too, and the comment button is correctly wired to that shared
   backend.)
2. **Settings were genuinely thin, and even the two that existed had a
   real bug.** Each space had exactly two toggles, and — separately —
   `applyPlatformSettingEffects()` was only ever called when a user
   manually flipped a toggle, never on initial page load or when a feed
   re-rendered. So a setting could be off and still visibly not apply
   until you touched it once. Both are fixed:
   - Gateway gained **typing indicators** (server-enforced — turning it
     off stops the backend from ever broadcasting your typing event to
     others, not just a client-side label) and **online status
     visibility** (server-enforced — `public_user()` now forces
     `is_online`/`last_seen` to false/null for anyone whose setting is
     off, regardless of who's asking).
   - Beta gained **show captions**, Epsilon gained **show reply counts**,
     Alpha gained **loop videos** — all real, client-enforced toggles.
   - `loadIgFeed()`, `loadPosts()`, and `loadAlpha()` now call
     `applyPlatformSettingEffects()` after every render, so settings
     apply the moment a feed loads, not just after you touch a toggle.

3 new tests cover the two server-enforced settings specifically — one
confirms another user's client genuinely can't see online status once
it's turned off, the other confirms the same gate function the WebSocket
handler calls returns the override correctly.

## Bittensor integration — live network data, not just a static blurb

Since several of Gateway's own AI providers (GM, Chutes, Targon, Nineteen)
are themselves Bittensor subnets, Gateway's assistant knows about Bittensor
at two levels:

1. **Always on, static:** a plain-English explanation of subnets, miners,
   validators, TAO, and dTAO staking, baked into the system prompt
   (`GATEWAY_SYSTEM_PROMPT` in `ai_providers.py`). This works with zero
   configuration.
2. **Optional, live:** if you set `TAOSTATS_API_KEY`, `bittensor_data.py`
   pulls a real snapshot from the [Taostats API](https://docs.taostats.io)
   (current TAO issuance, network market cap, current subnet registration
   cost) and folds it into the system prompt for that request, cached for
   five minutes. No key set, or the request fails for any reason → Gateway
   silently falls back to the static explanation instead of guessing at a
   number. `python3 run.py` prints which mode is active on startup.

This exists as a working example of two things other builders on Bittensor
run into: how to route one chat feature through several interchangeable
subnet-hosted LLM providers behind a single interface, and how to fold a
live on-chain/API data source into an LLM's context without it becoming
a source of confidently wrong numbers when that data source is unavailable.
Both `ai_providers.py` and `bittensor_data.py` are intentionally written to
be read, not just run.

**What this doesn't do yet:** it's read-only network context for the chat
assistant, not a Model Context Protocol (MCP) tool the assistant can call
mid-conversation to look something up on demand (the way something like
Metagraphed exposes Bittensor as an agent-navigable API). Wiring an actual
MCP client in is the natural next step if this needs to go further than a
periodically-refreshed snapshot.

## For miners: a standalone endpoint checker, independent of the rest of this app

`backend/scripts/check_provider.py` sends one minimal chat-completion
request to an endpoint and checks the response comes back in the shape a
downstream client actually expects (`choices[0].message.content` for
OpenAI-compatible servers, `content[].text` for the native Anthropic
Messages shape) — the exact contract Gateway's own `ai_providers.py`
relies on.

This has no dependency on Gateway beyond that one shared shape check. If
you're a miner who just stood up your own OpenAI-compatible server —
vLLM on a rented Lium node is the case this project already had in mind —
you can point this at it before depending on it for anything real:

```bash
cd backend
python3 scripts/check_provider.py \
    --base-url https://your-endpoint.example.com/v1 \
    --api-key sk-... \
    --model your-model-name
```

It reports PASS/FAIL, latency, and — critically — *why* it failed
(unreachable, wrong HTTP status, or a 200 response in a shape nothing
would actually be able to parse), and exits non-zero on failure so it's
safe to drop into a deploy script as a gate. `--all` runs the same check
against every Gateway provider that currently has an API key configured —
which is also how the "best-effort, unconfirmed" caveats on Lium and
Nineteen above can actually get resolved, against real keys, instead of
staying caveats forever.

## Everything from previous passes, still here

Ratings (1-5 stars, upsert semantics, block-aware), Block/Report with a real
UI (profile overflow menu), trust & safety enforcement, rate limiting,
structured logging, per-platform isolated settings, real camera/mic
permissions, a personal API key for programmatic access, an honest
user-uploaded sounds library (not a licensed music catalog), and four
genuinely distinct animated backgrounds per space.

## Running it

No dependencies, so a venv is optional — the app runs directly with the
system Python. If you'd rather keep it isolated (recommended if you have
other Python projects on the same machine):

```bash
cd backend
python3 -m venv venv
source venv/bin/activate      # on Windows: venv\Scripts\activate
pip install -r requirements.txt   # no-op — confirmed nothing to install
python3 run.py
```

Or skip the venv entirely:

```bash
cd backend
python3 run.py
```
`ADMIN_USERNAME=yourusername python3 run.py` grants admin rights to an
*existing* account (register first, then restart with this set).

A `.gitignore` at the repo root already excludes `venv/`, `__pycache__/`,
the SQLite db, and logs, so none of that ends up committed.

Optional: set `TAOSTATS_API_KEY` before starting to turn on live Bittensor
data for the in-app assistant (see "Bittensor integration" above). Without
it, everything else runs exactly the same.

## Tests

```bash
cd backend
python3 -m unittest discover tests -v
```
35 tests, stdlib only, run against real server instances (including two
fake local HTTP servers spun up specifically to prove the provider
checker actually distinguishes a correct response from a wrong one,
rather than assuming its own logic works).

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
    │   └── templates/   # the ENTIRE frontend — all Python
    ├── scripts/
    │   └── check_provider.py   # standalone CLI — for miners, not just Gateway
    └── tests/
        └── test_api.py
```

## What's genuinely still missing

Real payment processing, native mobile apps, horizontal scaling beyond a
single SQLite-backed process, a deep-link router so share-link URLs actually
load the linked content on open (they copy correctly now — opening them
doesn't yet do anything), group-chat admin controls, message edit/delete,
push notifications, an actual MCP tool interface for the Bittensor data
(currently a periodic snapshot, not something the assistant can query
on demand) — and, still the biggest one, actual users and revenue.
