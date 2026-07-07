#!/usr/bin/env python3
"""token-dump.py — zrzuca dane tokenów do token-data.json dla dashboardu."""
import json
import os
from datetime import datetime, timezone
from fetcher import get_claude, get_codex

DUMP_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "token-data.json")


def dump():
    claude = get_claude()
    codex = get_codex()

    # Przycinamy do pól potrzebnych dashboardowi (ponytail: dashboard nie potrzebuje daily breakdowns, models itp.)
    if claude.get("available"):
        claude = {
            "provider": "claude",
            "available": True,
            "buckets": claude["buckets"],
            "daily": claude.get("daily", []),
            "total_7d": claude.get("total_7d", 0),
            "peak_day": claude.get("peak_day", 0),
            "pacing": claude.get("pacing", "?"),
        }

    if codex.get("available"):
        codex = {
            "provider": "codex",
            "available": True,
            "summary": codex["summary"],
            "windows": codex["windows"],
            "top": codex.get("top", [])[:3],
        }

    output = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "claude": claude,
        "codex": codex,
    }
    with open(DUMP_PATH, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    dump()
