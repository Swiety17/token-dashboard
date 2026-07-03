#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TokenTracker — self-updating pixel-art dashboard.
Write to ~/Projects/token-dashboard/token-data.json on each run.
Usage: python3 tokentracker.py --dump
"""

import json
import sqlite3
import sys
import os
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

TOKENEATER_SHARED = os.path.expanduser(
    "~/Library/Application Support/com.tokeneater.shared/shared.json"
)
CODEX_DB = os.path.expanduser("~/.codex/state_5.sqlite")
DUMP_PATH = os.path.expanduser("~/Projects/token-dashboard/token-data.json")


# ── CLAUDE ──────────────────────────────────────────────────────
def get_claude():
    if not os.path.exists(TOKENEATER_SHARED):
        return {"error": "TokenEater not found", "available": False}
    try:
        with open(TOKENEATER_SHARED) as f:
            data = json.load(f)
    except Exception as e:
        return {"error": str(e), "available": False}

    usage = data.get("cachedUsage", {}).get("usage", {})
    daily = data.get("lastWeekDailyTotals", [])
    thresholds = data.get("thresholds", {})

    buckets = {}
    for key in ("five_hour", "seven_day", "extra_usage"):
        b = usage.get(key, {})
        pct = b.get("utilization", 0)
        resets = b.get("resets_at")
        remaining_min = None
        if resets:
            try:
                dt = datetime.fromisoformat(resets.replace("Z", "+00:00"))
                remaining = dt - datetime.now(timezone.utc)
                if remaining.total_seconds() > 0:
                    remaining_min = int(remaining.total_seconds() // 60)
            except Exception:
                pass
        label_map = {"five_hour": "5h", "seven_day": "7d", "extra_usage": "Extra"}
        buckets[key] = {
            "label": label_map.get(key, key),
            "pct": pct,
            "remaining_min": remaining_min,
        }
        if key == "extra_usage":
            buckets[key]["limit"] = b.get("monthly_limit", 0)
            buckets[key]["used"] = b.get("used_credits", 0)
            buckets[key]["enabled"] = b.get("is_enabled", False)
            buckets[key]["currency"] = b.get("currency", "EUR")

    return {
        "provider": "claude",
        "available": True,
        "buckets": buckets,
        "daily": daily,
        "total_7d": sum(daily),
        "peak_day": max(daily) if daily else 0,
        "pacing": data.get("smartColorProfile", "balanced"),
    }


# ── CODEX ───────────────────────────────────────────────────────
def get_codex():
    if not os.path.exists(CODEX_DB):
        return {"error": "Codex DB not found", "available": False}
    try:
        conn = sqlite3.connect(CODEX_DB)
        conn.row_factory = sqlite3.Row
    except Exception as e:
        return {"error": str(e), "available": False}

    now = int(time.time())

    def q(sql, params=()):
        row = conn.execute(sql, params).fetchone()
        return dict(row) if row else {}

    summary = q(
        "SELECT COUNT(*) as threads, COALESCE(SUM(tokens_used),0) as total, "
        "MAX(tokens_used) as peak FROM threads"
    )

    windows = {}
    for label, cutoff in [
        ("24h", now - 86400),
        ("7d", now - 604800),
        ("30d", now - 2592000),
    ]:
        r = q(
            "SELECT COUNT(*) as threads, COALESCE(SUM(tokens_used),0) as tokens "
            "FROM threads WHERE created_at > ?",
            (cutoff,),
        )
        windows[label] = r

    top = []
    for row in conn.execute(
        "SELECT title, tokens_used, model FROM threads ORDER BY tokens_used DESC LIMIT 3"
    ):
        top.append(
            {
                "title": (row["title"] or "")[:50],
                "tokens": row["tokens_used"],
                "model": row["model"],
            }
        )

    conn.close()

    return {
        "provider": "codex",
        "available": True,
        "summary": summary,
        "windows": windows,
        "top": top,
    }


# ── DUMP ─────────────────────────────────────────────────────────
def dump():
    claude = get_claude()
    codex = get_codex()
    output = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "claude": claude,
        "codex": codex,
    }
    os.makedirs(os.path.dirname(DUMP_PATH), exist_ok=True)
    with open(DUMP_PATH, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    dump()
