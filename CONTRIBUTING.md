# Contributing to Gateway

Gateway's backend has zero external dependencies — it's stdlib-only Python
(`http.server`, `sqlite3`, `socket`, `hashlib`, `urllib`). The frontend is
also plain Python, rendered as HTML/CSS/JS strings in `backend/app/templates/`.
There's no build step, no npm, and a venv is optional (there's nothing to
install either way) — use one if you want isolation from other Python
projects on your machine, skip it if you don't.

## Getting set up

```bash
git clone <your fork URL>
cd gateway_chat/backend
python3 -m venv venv && source venv/bin/activate  # optional
pip install -r requirements.txt                    # optional — no-op
python3 run.py
```

That's it. Register an account through the UI, then if you want admin
rights on it, stop the server and restart with:

```bash
ADMIN_USERNAME=yourusername python3 run.py
```

## Running the tests

```bash
cd backend
python3 -m unittest discover tests -v
```

Tests run against a real server instance, not mocks. If you add a route or
change existing behavior, add or update a test in `tests/test_api.py` that
exercises it the same way.

## Project layout

```
backend/
├── run.py
├── app/
│   ├── server.py       # HTTP routes + WebSocket handling
│   ├── db.py            # SQLite schema and queries
│   ├── auth.py           # sessions, password hashing
│   ├── ai_providers.py    # chat-completion backends (GM, Chutes, Targon, etc.)
│   ├── bittensor_data.py  # optional live Taostats network snapshot
│   ├── wsutil.py          # WebSocket framing
│   ├── logging_util.py    # structured logging
│   ├── rate_limit.py      # request throttling
│   └── templates/         # entire frontend, as Python string templates
└── tests/
    └── test_api.py
```

## Code style

- Match what's already there — this codebase avoids frameworks on purpose,
  so please don't introduce a new dependency without discussing it in an
  issue first.
- Keep functions doing one thing. `server.py` routes should stay thin;
  push logic into `db.py` / `auth.py` / etc.
- No silent failures. If something can go wrong (a missing header, a bad
  token), handle it explicitly and return a real error response.

## Before opening a PR

- Run the test suite and make sure it's green.
- If you're fixing a bug, verify it against a running instance rather than
  just reading the code — this project has a habit of catching bugs that
  only show up when something is actually clicked. Say in the PR
  description what you did to verify it.
- Keep PRs scoped to one change. Easier to review, easier to merge.

## What's currently missing (a.k.a. good places to contribute)

- A deep-link router so shared invite links actually open the linked
  content, not just copy correctly
- Group-chat admin controls
- Message edit/delete
- Push notifications
- Horizontal scaling beyond a single SQLite-backed process

## Reporting bugs

Open an issue with steps to reproduce. If it's a UI bug, say which of the
four spaces (Gateway/Beta/Epsilon/Alpha) it's in — a lot of behavior is
space-specific.
