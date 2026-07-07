#!/usr/bin/env python3
"""fetcher.py — shared data layer for TokenEater (Claude) + Codex SQLite.
Import this from token-dump.py, tokentracker.py, tokenbar.py.
"""

import json
import sqlite3
import os
import time
from datetime import datetime, timezone

TOKENEATER = os.path.expanduser(
    "~/Library/Application Support/com.tokeneater.shared/shared.json"
)
CODEX_DB = os.path.expanduser("~/.codex/state_5.sqlite")


# ── CLAUDE (TokenEater) ──────────────────────────────────────

def get_claude() -> dict:
    """Czyta dane Claude z TokenEater shared.json."""
    if not os.path.exists(TOKENEATER):
        return {"error": "TokenEater shared.json nie znaleziony", "available": False}

    try:
        with open(TOKENEATER) as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        return {"error": str(e), "available": False}

    usage = data.get("cachedUsage", {}).get("usage", {})
    daily = data.get("lastWeekDailyTotals", [])
    thresholds = data.get("thresholds", {})
    pacing = data.get("smartColorProfile", "?")

    buckets = {}
    for key in ("five_hour", "seven_day", "extra_usage"):
        b = usage.get(key, {})
        pct = b.get("utilization", 0)
        resets = b.get("resets_at")
        remaining_min = None
        if resets:
            try:
                dt = datetime.fromisoformat(resets.replace("Z", "+00:00"))
                r = dt - datetime.now(timezone.utc)
                if r.total_seconds() > 0:
                    remaining_min = int(r.total_seconds() // 60)
            except Exception:
                pass

        label_map = {"five_hour": "5h", "seven_day": "7d", "extra_usage": "Extra"}
        entry = {
            "label": label_map.get(key, key),
            "pct": pct,
            "utilization_percent": pct,  # compat: tokentracker.py używa utilization_percent
            "remaining_min": remaining_min,
            "resets_at": resets,
        }
        if key == "extra_usage":
            entry["limit"] = b.get("monthly_limit", 0)
            entry["monthly_limit"] = b.get("monthly_limit", 0)
            entry["used"] = b.get("used_credits", 0)
            entry["used_credits"] = b.get("used_credits", 0)
            entry["enabled"] = b.get("is_enabled", False)
            entry["is_enabled"] = b.get("is_enabled", False)
            entry["currency"] = b.get("currency", "EUR")
            entry["disabled_reason"] = b.get("disabled_reason")
        buckets[key] = entry

    return {
        "provider": "claude",
        "available": True,
        "buckets": buckets,
        "daily": daily,
        "daily_totals_last_7d": daily,
        "total_7d": sum(daily),
        "total_tokens_7d": sum(daily),
        "peak_day": max(daily) if daily else 0,
        "peak_day_tokens": max(daily) if daily else 0,
        "thresholds": thresholds,
        "pacing": pacing,
        "pacing_profile": pacing,
        "source": "TokenEater (api.anthropic.com/api/oauth/usage)",
    }


# ── CODEX (SQLite) ────────────────────────────────────────────

def get_codex() -> dict:
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

    summary = query_one(
        "SELECT COUNT(*) as threads, COALESCE(SUM(tokens_used),0) as total, "
        "ROUND(AVG(tokens_used)) as avg_per_thread, "
        "MAX(tokens_used) as peak FROM threads"
    )
    # ponytail: dwie nazwy na to samo — compat dla różnych konsumentów
    summary["total_threads"] = summary.get("threads", 0)
    summary["total_tokens"] = summary.get("total", 0)
    summary["avg_tokens_per_thread"] = summary.get("avg_per_thread", 0)
    summary["max_tokens"] = summary.get("peak", 0)

    windows = {}
    for label, cutoff in [
        ("24h", now - 86400),
        ("7d", now - 604800),
        ("30d", now - 2592000),
    ]:
        r = query_one(
            "SELECT COUNT(*) as threads, COALESCE(SUM(tokens_used),0) as tokens "
            "FROM threads WHERE created_at > ?",
            (cutoff,),
        )
        windows[label] = r

    top = []
    for row in conn.execute(
        "SELECT substr(title,1,80) as title, tokens_used, model, "
        "datetime(created_at,'unixepoch') as created "
        "FROM threads ORDER BY tokens_used DESC LIMIT 5"
    ):
        top.append(dict(row))

    daily = []
    for row in conn.execute(
        "SELECT date(created_at,'unixepoch') as day, "
        "COUNT(*) as threads, COALESCE(SUM(tokens_used),0) as tokens "
        "FROM threads WHERE created_at > ? "
        "GROUP BY day ORDER BY day",
        (now - 604800,),
    ):
        daily.append(dict(row))

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
        "windows": windows,
        "usage_windows": windows,  # compat
        "top": top,
        "top_threads": top,  # compat
        "daily": daily,
        "daily_breakdown_7d": daily,  # compat
        "models": models,
        "source": f"Codex SQLite ({CODEX_DB})",
    }
