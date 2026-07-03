#!/usr/bin/env python3
"""
TokenBar — macOS menu bar app do monitorowania tokenów Claude + Codex.
Siedzi w górnym pasku, pokazuje % Claude 5h, menu z pełnymi statami.
Powiadomienia systemowe macOS na 80% / 90% / 100%.

Usage: python3 tokenbar.py
Zatrzymaj: kliknij ikonę → Quit
"""
import json
import sqlite3
import os
import time
import threading
from datetime import datetime, timezone

import rumps

# ── Ścieżki ──────────────────────────────────────────────────
TOKENEATER = os.path.expanduser(
    "~/Library/Application Support/com.tokeneater.shared/shared.json"
)
CODEX_DB = os.path.expanduser("~/.codex/state_5.sqlite")

# ── Progi powiadomień ────────────────────────────────────────
NOTIFY_LEVELS = [80, 90, 100]

# ══════════════════════════════════════════════════════════════
#  DATA FETCH
# ══════════════════════════════════════════════════════════════

def fetch_claude():
    if not os.path.exists(TOKENEATER):
        return {}
    try:
        with open(TOKENEATER) as f:
            data = json.load(f)
    except Exception:
        return {}
    usage = data.get("cachedUsage", {}).get("usage", {})
    daily = data.get("lastWeekDailyTotals", [])
    result = {}
    for key in ("five_hour", "seven_day", "extra_usage"):
        b = usage.get(key, {})
        pct = b.get("utilization", 0)
        resets = b.get("resets_at")
        rem = None
        if resets:
            try:
                dt = datetime.fromisoformat(resets.replace("Z", "+00:00"))
                r = dt - datetime.now(timezone.utc)
                if r.total_seconds() > 0:
                    rem = int(r.total_seconds() // 60)
            except Exception:
                pass
        result[key] = {"pct": pct, "remaining_min": rem}
        if key == "extra_usage":
            result[key]["limit"] = b.get("monthly_limit", 0)
            result[key]["used"] = b.get("used_credits", 0)
    result["_daily"] = daily
    result["_total_7d"] = sum(daily)
    result["_pacing"] = data.get("smartColorProfile", "?")
    return result


def fetch_codex():
    if not os.path.exists(CODEX_DB):
        return {}
    try:
        conn = sqlite3.connect(CODEX_DB)
        conn.row_factory = sqlite3.Row
    except Exception:
        return {}

    def q(sql, p=()):
        r = conn.execute(sql, p).fetchone()
        return dict(r) if r else {}

    now = int(time.time())
    summary = q(
        "SELECT COUNT(*) as threads, COALESCE(SUM(tokens_used),0) as total "
        "FROM threads"
    )
    windows = {}
    for label, cutoff in [("24h", now-86400), ("7d", now-604800), ("30d", now-2592000)]:
        windows[label] = q(
            "SELECT COALESCE(SUM(tokens_used),0) as tokens FROM threads WHERE created_at > ?",
            (cutoff,),
        )
    conn.close()
    return {"summary": summary, "windows": windows}


def fmt(n):
    if n is None: return "0"
    if n >= 1e9: return f"{n/1e9:.1f}B"
    if n >= 1e6: return f"{n/1e6:.1f}M"
    if n >= 1e3: return f"{n/1e3:.0f}K"
    return str(n)


# ══════════════════════════════════════════════════════════════
#  MENU BAR APP
# ══════════════════════════════════════════════════════════════

class TokenBarApp(rumps.App):
    def __init__(self):
        super().__init__(
            name="🪙",
            title="🪙",
            quit_button=None,
        )
        self.last_alerts = {}      # bucket_key -> set of fired thresholds
        self.last_pcts = {}        # bucket_key -> last known pct
        self.claude = {}
        self.codex = {}

        # Build menu
        self.claude_menu = rumps.MenuItem("🔵 Claude", [])
        self.codex_menu = rumps.MenuItem("🟢 Codex", [])
        self.rec_menu = rumps.MenuItem("Rekomendacja...")
        self.refresh_btn = rumps.MenuItem("🔄 Odśwież", callback=self.do_refresh)
        self.dash_btn = rumps.MenuItem("🌐 Dashboard", callback=self.open_dashboard)
        self.quit_btn = rumps.MenuItem("⏻ Quit", callback=self.quit_app)

        self.menu = [
            self.claude_menu,
            self.codex_menu,
            None,
            self.rec_menu,
            None,
            self.refresh_btn,
            self.dash_btn,
            None,
            self.quit_btn,
        ]

        # Timery
        self.refresh_timer = rumps.Timer(self.do_refresh, 60)
        self.refresh_timer.start()

        # Pierwsze odświeżenie
        self.do_refresh(None)

    # ── Data refresh ──────────────────────────────────────

    def do_refresh(self, _):
        self.claude = fetch_claude()
        self.codex = fetch_codex()
        self.update_title()
        self.update_menus()
        self.check_alerts()

    # ── Title bar ─────────────────────────────────────────

    def update_title(self):
        c5h = self.claude.get("five_hour", {}).get("pct", 0)
        if c5h >= 90:
            self.title = f"🔥{c5h}%"
        elif c5h >= 80:
            self.title = f"⚠️{c5h}%"
        elif c5h >= 60:
            self.title = f"⚡{c5h}%"
        else:
            self.title = f"🪙{c5h}%"

    # ── Menu items ────────────────────────────────────────

    def update_menus(self):
        # Claude submenu
        claude_items = []
        for key in ("five_hour", "seven_day", "extra_usage"):
            b = self.claude.get(key, {})
            pct = b.get("pct", 0)
            label_map = {"five_hour": "5 godzin", "seven_day": "7 dni", "extra_usage": "Extra kredyty"}
            emoji = "🔴" if pct >= 90 else ("🟡" if pct >= 80 else "🟢")
            extra = ""
            if key == "extra_usage" and b.get("limit"):
                extra = f" ({b.get('used',0)}/{b['limit']} EUR)"
            rem = b.get("remaining_min")
            rem_str = f" — reset za {rem}min" if rem is not None else ""
            claude_items.append(
                rumps.MenuItem(f"{emoji} {label_map[key]}: {pct}%{extra}{rem_str}")
            )
        total = self.claude.get("_total_7d", 0)
        claude_items.append(rumps.MenuItem(f"   7d łącznie: {fmt(total)} tokenów"))
        self._safe_clear_menu(self.claude_menu)
        for item in claude_items:
            self.claude_menu.add(item)

        # Codex submenu
        codex_items = []
        s = self.codex.get("summary", {})
        w = self.codex.get("windows", {})
        codex_items.append(rumps.MenuItem(f"Wątków: {s.get('threads',0)}"))
        codex_items.append(rumps.MenuItem(f"Tokenów: {fmt(s.get('total',0))}"))
        for label in ("24h", "7d", "30d"):
            t = w.get(label, {}).get("tokens", 0)
            codex_items.append(rumps.MenuItem(f"   {label}: {fmt(t)}"))
        self._safe_clear_menu(self.codex_menu)
        for item in codex_items:
            self.codex_menu.add(item)

        # Rekomendacja
        c5h = self.claude.get("five_hour", {}).get("pct", 0)
        if c5h >= 90:
            rec = "🔥 CODEX — Claude 90%+"
        elif c5h >= 80:
            rec = "⚠️ CODEX — Claude 80%+"
        elif c5h >= 60:
            rec = "⚡ Rozważ Codexa"
        else:
            rec = "✅ Claude — luz"
        self.rec_menu.title = f"🎯 {rec}"

    def _safe_clear_menu(self, menu_item):
        """Bezpiecznie czyści submenu — rumps nie tworzy _menu dla pustych MenuItem."""
        try:
            if menu_item._menu is not None:
                menu_item._menu.removeAllItems()
        except AttributeError:
            pass

    # ── Alerty ────────────────────────────────────────────

    def check_alerts(self):
        for key in ("five_hour", "seven_day", "extra_usage"):
            b = self.claude.get(key, {})
            pct = b.get("pct", 0)
            bucket_id = f"claude:{key}"
            prev_pct = self.last_pcts.get(bucket_id, 0)

            if bucket_id not in self.last_alerts:
                self.last_alerts[bucket_id] = set()

            # Check thresholds
            for level in NOTIFY_LEVELS:
                if pct >= level and level not in self.last_alerts[bucket_id]:
                    if prev_pct < level:  # crossing UPWARD
                        self.last_alerts[bucket_id].add(level)
                        label_map = {"five_hour": "5h", "seven_day": "7d", "extra_usage": "Extra"}
                        self.do_notify(
                            f"Claude {label_map.get(key, key)}: {pct}%",
                            f"Próg {level}% przekroczony"
                        )
                # Reset when drops below threshold -5%
                if pct < level - 5:
                    self.last_alerts[bucket_id].discard(level)

            # Reset detection
            if prev_pct >= 80 and pct < 10:
                label_map = {"five_hour": "5h", "seven_day": "7d", "extra_usage": "Extra"}
                self.do_notify(
                    f"🔄 Claude {label_map.get(key, key)} — limit odświeżony!",
                    f"Spadło z {prev_pct}% → {pct}%. Możesz wrócić do Claude."
                )
                self.last_alerts[bucket_id] = set()

            self.last_pcts[bucket_id] = pct

    def do_notify(self, title, subtitle=""):
        try:
            rumps.notification(
                title=title,
                subtitle=subtitle,
                message="",
                sound=True,
            )
        except Exception:
            pass  # cicho jeśli notification center nie działa

    # ── Actions ───────────────────────────────────────────

    def open_dashboard(self, _):
        os.system("open http://localhost:8765")

    def quit_app(self, _):
        self.refresh_timer.stop()
        rumps.quit_application()


# ══════════════════════════════════════════════════════════════
#  RUN
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    TokenBarApp().run()
