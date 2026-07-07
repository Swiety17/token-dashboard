#!/usr/bin/env python3
"""
TokenTracker — monitor zużycia tokenów Claude (TokenEater) + Codex (OpenAI)
======================================================================
Czyta dane lokalnie (TokenEater shared.json + Codex SQLite),
nie wymaga API keys, wszystko z OAuth sesji na dysku.

Użycie:
  python3 tokentracker.py              → czytelny raport tekstowy
  python3 tokentracker.py --json       → JSON output (do pipeline)
  python3 tokentracker.py --claude     → tylko Claude
  python3 tokentracker.py --codex      → tylko Codex
  python3 tokentracker.py --watch      → live refresh co 60s
"""

import json
import sys
import os
import time
from datetime import datetime, timezone
from fetcher import get_claude, get_codex


def format_big_number(n: int) -> str:
    """1 234 567 → '1.23M'"""
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.2f}B"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.2f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def utilization_bar(pct: int, width: int = 16) -> str:
    """Pasek procentowy z emoji."""
    filled = int(pct / 100 * width)
    empty = width - filled
    if pct >= 85:
        emoji = "🔴"
    elif pct >= 60:
        emoji = "🟡"
    else:
        emoji = "🟢"
    return f"{emoji} [{'█' * filled}{'░' * empty}] {pct}%"


def recommend_provider(claude: dict, codex: dict) -> str:
    """Kogo lepiej użyć do następnego zadania?"""
    reasons = []
    claude_5h = 0
    if claude.get("available"):
        claude_5h = claude["buckets"].get("five_hour", {}).get("utilization_percent", 0)

    if claude_5h >= 85:
        reasons.append("Claude 5h na wyczerpaniu 🔴")
    elif claude_5h >= 60:
        reasons.append("Claude 5h ostrzegawczo 🟡")

    if not reasons:
        return "✅ CLAUDE — ma luz. Użyj Claude Code."
    return f"⚠️  CODEX — {'; '.join(reasons)}. Przerzuć na Codexa."


def print_report(claude: dict, codex: dict):
    """Ładny raport tekstowy."""
    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║         🪙  TOKEN TRACKER — Rychu kokpit  🪙           ║")
    print("╠══════════════════════════════════════════════════════════╣")

    # ── CLAUDE ──
    print("║  🔵 CLAUDE (Anthropic OAuth)                            ║")
    if claude.get("available"):
        for key, b in claude["buckets"].items():
            pct = b["utilization_percent"]
            bar = utilization_bar(pct, 16)
            reset = ""
            if b.get("resets_at"):
                try:
                    dt = datetime.fromisoformat(b["resets_at"].replace("Z", "+00:00"))
                    remaining = dt - datetime.now(timezone.utc)
                    if remaining.total_seconds() > 0:
                        h = int(remaining.total_seconds() // 3600)
                        m = int((remaining.total_seconds() % 3600) // 60)
                        reset = f" (reset za {h}h {m}m)"
                except (ValueError, TypeError):
                    pass
            print(f"║    {b['label']:<10} {bar} {reset}")
        print(f"║    7d łącznie: {format_big_number(claude['total_tokens_7d']):>8} tokenów")
        print(f"║    Peak day:    {format_big_number(claude['peak_day_tokens']):>8}")
        print(f"║    Pacing:      {claude['pacing_profile']}")
    else:
        print(f"║    ❌ {claude.get('error', 'brak danych')}")

    # ── CODEX ──
    print("╠══════════════════════════════════════════════════════════╣")
    print("║  🟢 CODEX (OpenAI OAuth)                                ║")
    if codex.get("available"):
        s = codex["summary"]
        print(f"║    Wątków łącznie:  {s['total_threads']:>5}")
        print(f"║    Tokenów łącznie: {format_big_number(s['total_tokens']):>8}")
        print(f"║    Średnio/wątek:   {format_big_number(int(s['avg_tokens_per_thread'])):>8}")
        print(f"║    Max wątek:       {format_big_number(s['max_tokens']):>8}")
        print("║    ────────────────")
        for label, w in codex["usage_windows"].items():
            print(
                f"║    {label:<5}          {format_big_number(w['tokens']):>8} tokenów "
                f"({w['threads']} wątków)"
            )
        if codex.get("top_threads"):
            print("║    ── Top wątki ──")
            for t in codex["top_threads"][:3]:
                print(
                    f"║    {format_big_number(t['tokens_used']):>8}  "
                    f"{t['title'][:45]}"
                )
    else:
        print(f"║    ❌ {codex.get('error', 'brak danych')}")

    print("╠══════════════════════════════════════════════════════════╣")
    print(f"║  🎯 REKOMENDACJA: {recommend_provider(claude, codex)}")
    print("╚══════════════════════════════════════════════════════════╝")
    print()


def main():
    json_mode = "--json" in sys.argv
    claude_only = "--claude" in sys.argv
    codex_only = "--codex" in sys.argv
    watch_mode = "--watch" in sys.argv

    def fetch():
        c = get_claude() if not codex_only else {}
        x = get_codex() if not claude_only else {}
        return c, x

    if watch_mode:
        try:
            while True:
                os.system("clear" if os.name == "posix" else "cls")
                c, x = fetch()
                print_report(c, x)
                print("[auto-odświeżanie co 60s — Ctrl+C aby zatrzymać]")
                time.sleep(60)
        except KeyboardInterrupt:
            print("\nZatrzymano.")
        return

    claude, codex = fetch()

    if json_mode:
        output = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "claude": claude,
            "codex": codex,
            "recommendation": recommend_provider(claude, codex),
        }
        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        print_report(claude, codex)


if __name__ == "__main__":
    main()
