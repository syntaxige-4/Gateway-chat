# Security Policy

## Supported versions

This project doesn't currently maintain multiple release branches — only
the latest commit on `main` gets security fixes. If you're running an
older checkout, update before reporting an issue tied to a version that's
already been patched.

## What's currently in place

Worth knowing before you report something, so we're not duplicating known
tradeoffs:

- Passwords are hashed with PBKDF2-HMAC-SHA256 (200,000 iterations) plus a
  random per-user salt. No external crypto library — this is stdlib only.
- Sessions are a minimal HMAC-SHA256-signed token (JWT-shaped, not a full
  JWT library), valid for 14 days.
- `GATEWAY_SECRET_KEY` **must** be set to a real random value in any
  non-local deployment. The default in the code is a dev placeholder and
  is not safe to run in production — this is a known, intentional gap for
  local/dev use, not something to report.
- API keys for programmatic access follow a `gateway_live_<random>`
  format, generated with `os.urandom`.
- This is a single-process, SQLite-backed server intended for self-hosting
  or small deployments — it hasn't been hardened for large-scale or
  adversarial public internet exposure (no WAF, no built-in TLS
  termination — put it behind a reverse proxy for that).

## Reporting a vulnerability

If you find a genuine security issue — auth bypass, privilege escalation,
injection, an unsafe file-path handling bug in the media upload path,
token forgery, or anything that lets one account read/act as another —
please **don't** open a public issue first.

Instead:
1. Open a private security advisory on the repo (GitHub's "Report a
   vulnerability" under the Security tab), or
2. If that's not available, contact a maintainer directly rather than
   filing a public issue, so there's time to patch before details are
   public.

Include: what you found, steps to reproduce, and what you think the
impact is (what an attacker could actually do with it).

## What's not in scope

- The dev-mode default secret key (documented above as a known gap)
- Missing rate limiting on endpoints that aren't auth-related (rate
  limiting exists but isn't applied everywhere yet — this is tracked as a
  feature gap, not a vulnerability, unless you can show real abuse impact)
- Denial-of-service reports based on running a single-process server under
  heavy synthetic load — that's an architectural tradeoff of the current
  design, not a bug
