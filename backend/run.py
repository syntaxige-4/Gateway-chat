#!/usr/bin/env python3
"""
Entry point for the Gateway Chat backend.

Usage:
    python3 run.py                 # serve on 0.0.0.0:8000
    PORT=9000 python3 run.py       # custom port

Environment variables (all optional):
    GATEWAY_SECRET_KEY      - JWT signing secret (set a real one in production)
    GATEWAY_PROVIDER         - default AI provider: gm | chutes | lium | anthropic  (default: gm)
    GM_API_KEY, GM_BASE_URL, GM_MODEL
    CHUTES_API_KEY, CHUTES_BASE_URL, CHUTES_MODEL
    LIUM_API_KEY, LIUM_BASE_URL, LIUM_MODEL
    ANTHROPIC_API_KEY, ANTHROPIC_BASE_URL, ANTHROPIC_MODEL
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from app.server import run

if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))
    run(host, port)
