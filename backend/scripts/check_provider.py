#!/usr/bin/env python3
"""
check_provider.py — verify a chat-completion endpoint actually speaks the
protocol a downstream client expects, before you depend on it.

Two ways to use this:

  1. Check one of Gateway's own configured providers (reads base_url/model
     from ai_providers.py, API key from the environment):

         python3 scripts/check_provider.py --provider lium

     Or check everything that currently has a key set:

         python3 scripts/check_provider.py --all

  2. Check ANY OpenAI-compatible endpoint, with no dependency on Gateway's
     provider list at all — this is the one that matters if you're a
     miner who just stood up your own server (e.g. vLLM on a rented Lium
     node) and want to confirm it works before pointing real traffic at
     it, or before wiring it into whatever app is going to consume it:

         python3 scripts/check_provider.py \\
             --base-url https://your-endpoint.example.com/v1 \\
             --api-key sk-... \\
             --model your-model-name

     Add --kind anthropic if your server speaks the native Anthropic
     Messages API shape instead of the OpenAI chat/completions shape.

Exit code is 0 if every check that ran passed, 1 otherwise — so this is
safe to use in a deploy script or CI step to gate on "is my endpoint
actually reachable and correctly shaped" before going further.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import provider_check, ai_providers  # noqa: E402


def _print_result(label, result):
    if result.get("skipped"):
        print(f"  SKIP  {label:<20} — {result['reason']}")
        return True
    status = "PASS" if result["ok"] else "FAIL"
    latency = f"{result['latency_ms']}ms" if result["latency_ms"] is not None else "—"
    print(f"  {status}  {label:<20} — {latency}", end="")
    if result["ok"]:
        print(f"  reply: {result['sample_reply']!r}")
    else:
        print(f"\n         {result['error']}")
    return result["ok"]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--all", action="store_true",
                         help="check every Gateway provider that has its API key env var set")
    parser.add_argument("--provider", help="check one Gateway provider by id (e.g. gm, lium, targon)")
    parser.add_argument("--base-url", help="check an arbitrary endpoint instead (no Gateway config needed)")
    parser.add_argument("--api-key", default=None, help="API key for --base-url mode")
    parser.add_argument("--model", default="default", help="model name for --base-url mode")
    parser.add_argument("--kind", choices=["openai_compat", "anthropic"], default="openai_compat",
                         help="protocol shape for --base-url mode (default: openai_compat)")
    parser.add_argument("--timeout", type=int, default=10, help="request timeout in seconds")
    args = parser.parse_args()

    all_ok = True

    if args.base_url:
        print(f"Checking {args.base_url} ({args.kind})...")
        if args.kind == "anthropic":
            result = provider_check.check_anthropic_compat(args.base_url, args.api_key, args.model, args.timeout)
        else:
            result = provider_check.check_openai_compat(args.base_url, args.api_key, args.model, args.timeout)
        all_ok = _print_result(args.base_url, result)

    elif args.provider:
        cfg = ai_providers.PROVIDERS.get(args.provider)
        if not cfg:
            print(f"Unknown provider '{args.provider}'. Options: {list(ai_providers.PROVIDERS)}")
            sys.exit(2)
        api_key = os.environ.get(cfg["api_key_env"], "")
        if not api_key:
            print(f"{cfg['api_key_env']} is not set — nothing to check.")
            sys.exit(2)
        if cfg["kind"] == "anthropic":
            result = provider_check.check_anthropic_compat(cfg["base_url"], api_key, cfg["model"], args.timeout)
        else:
            result = provider_check.check_openai_compat(cfg["base_url"], api_key, cfg["model"], args.timeout)
        all_ok = _print_result(cfg["label"], result)

    elif args.all:
        print("Checking all configured Gateway providers...\n")
        results = provider_check.check_configured_providers(args.timeout)
        for result in results:
            ok = _print_result(result["label"], result)
            if not result.get("skipped"):
                all_ok = all_ok and ok

    else:
        parser.print_help()
        sys.exit(2)

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
