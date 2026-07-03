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
  python3 tokentracker.py --watch      → live refresh co 30s

Autor: Rychu & Przemek, 2026
"""

import json
import sqlite3
import sys
import os
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ── Ścieżki do danych ──────────────────────────────────────────
TOKENEATER_SHARED = os.path.expanduser(
    "~/Library/Application Support/com.tokeneater.shared/shared.json"
)
CODEX_DB = os.path.expanduser("~/.codex/state_5.sqlite")


# ══════════════════════════════════════════════════════════════════
#  CLAUDE — z TokenEater shared.json
# ══════════════════════════════════════════════════════════════════

def get_claude_usage() -> dict:
    """Czyta dane Claude z TokenEater shared.json."""
    if not os.path.exists(TOKENEATER_SHARED):
        return {"error": "TokenEater shared.json nie znaleziony", "available": False}

    try:
        with open(TOKENEATER_SHARED) as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        return {"error": str(e), "available": False}

    usage = data.get("cachedUsage", {}).get("usage", {})
    daily = data.get("lastWeekDailyTotals", [])
    thresholds = data.get("thresholds", {})
    pacing = data.get("smartColorProfile", "?")

    buckets = {}
    for key in ("five_hour", "seven_day", "extra_usage"):
        bucket = usage.get(key, {})
        buckets[key] = {
            "utilization_percent": bucket.get("utilization", 0),
            "resets_at": bucket.get("resets_at"),
            "label": {
                "five_hour": "5 godzin",
                "seven_day": "7 dni",
                "extra_usage": "Extra kredyty",
            }.get(key, key),
        }
        if key == "extra_usage":
            buckets[key]["monthly_limit"] = bucket.get("monthly_limit", 0)
            buckets[key]["used_credits"] = bucket.get("used_credits", 0)
            buckets[key]["currency"] = bucket.get("currency", "EUR")
            buckets[key]["is_enabled"] = bucket.get("is_enabled", False)
            buckets[key]["disabled_reason"] = bucket.get("disabled_reason")

    last_7d_total = sum(daily) if daily else 0
    peak_day = max(daily) if daily else 0

    return {
        "provider": "claude",
        "available": True,
        "buckets": buckets,
        "daily_totals_last_7d": daily,
        "total_tokens_7d": last_7d_total,
        "peak_day_tokens": peak_day,
        "thresholds": thresholds,
        "pacing_profile": pacing,
        "source": "TokenEater (api.anthropic.com/api/oauth/usage)",
    }


# ══════════════════════════════════════════════════════════════════
#  CODEX — z SQLite state_5.sqlite
# ══════════════════════════════════════════════════════════════════

def get_codex_usage() -> dict:
    """Czyta dane Codex z SQLite (threads.tokens_used)."""
    if not os.path.exists(CODEX_DB):
        return {"error": f"Codex DB nie znaleziony: {CODEX_DB}", "available": False}

    try:
        conn = sqlite3.connect(CODEX_DB)
        conn.row_factory = sqlite3.Row
    except sqlite3.Error as e:
        return {"error": str(e), "available": False}

    now = int(time.time())

    def query_one(sql, params=()):
        row = conn.execute(sql, params).fetchone()
        return dict(row) if row else {}

    # Podsumowanie ogólne
    summary = query_one("""
        SELECT
            COUNT(*) as total_threads,
            COALESCE(SUM(tokens_used), 0) as total_tokens,
            ROUND(AVG(tokens_used)) as avg_tokens_per_thread,
            MAX(tokens_used) as max_tokens
        FROM threads
    """)

    # Okna czasowe
    windows = {
        "24h": now - 86400,
        "7d": now - 604800,
        "30d": now - 2592000,
    }
    usage_windows = {}
    for label, cutoff in windows.items():
        row = query_one(
            "SELECT COUNT(*) as threads, COALESCE(SUM(tokens_used),0) as tokens "
            "FROM threads WHERE created_at > ?",
            (cutoff,),
        )
        usage_windows[label] = {
            "threads": row.get("threads", 0),
            "tokens": row.get("tokens", 0),
        }

    # Top 5 wątków
    top_threads = []
    for row in conn.execute(
        "SELECT substr(title,1,80) as title, tokens_used, model, "
        "datetime(created_at,'unixepoch') as created "
        "FROM threads ORDER BY tokens_used DESC LIMIT 5"
    ):
        top_threads.append(dict(row))

    # Rozkład dzienny (ostatnie 7 dni)
    daily = []
    for row in conn.execute(
        "SELECT date(created_at,'unixepoch') as day, "
        "COUNT(*) as threads, COALESCE(SUM(tokens_used),0) as tokens "
        "FROM threads WHERE created_at > ? "
        "GROUP BY day ORDER BY day",
        (now - 604800,),
    ):
        daily.append(dict(row))

    # Modele
    models = []
    for row in conn.execute(
        "SELECT model, COUNT(*) as threads, COALESCE(SUM(tokens_used),0) as tokens "
        "FROM threads GROUP BY model ORDER BY tokens DESC"
    ):
        models.append(dict(row))

    conn.close()

    return {
        "provider": "codex",
        "available": True,
        "summary": summary,
        "usage_windows": usage_windows,
        "top_threads": top_threads,
        "daily_breakdown_7d": daily,
        "models": models,
        "source": f"Codex SQLite ({CODEX_DB})",
    }


# ══════════════════════════════════════════════════════════════════
#  RAPORT
# ══════════════════════════════════════════════════════════════════

def format_big_number(n: int) -> str:
    """1 234 567 → '1.23M'"""
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.2f}B"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.2f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def utilization_bar(pct: int, width: int = 20) -> str:
    """Pasek procentowy z emoji."""
    filled = int(pct / 100 * width)
    empty = width - filled
    if pct >= 85:
        emoji = "🔴"
    elif pct >= 60:
        emoji = "🟡"
    else:
        emoji = "🟢"
    return f"{emoji} [{('█' * filled)}{('░' * empty)}] {pct}%"


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
                    now = datetime.now(timezone.utc)
                    remaining = dt - now
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

    # ── DECYZJA ──
    print("╠══════════════════════════════════════════════════════════╣")
    decision = recommend_provider(claude, codex)
    print(f"║  🎯 REKOMENDACJA: {decision}")

    print("╚══════════════════════════════════════════════════════════╝")
    print()


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
    else:
        return f"⚠️  CODEX — {'; '.join(reasons)}. Przerzuć na Codexa."


# ══════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════

def main():
    json_mode = "--json" in sys.argv
    claude_only = "--claude" in sys.argv
    codex_only = "--codex" in sys.argv
    watch_mode = "--watch" in sys.argv

    def fetch():
        c = get_claude_usage() if not codex_only else {}
        x = get_codex_usage() if not claude_only else {}
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
