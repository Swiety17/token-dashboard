# 🪙 Token Dashboard

**Pixel-art dashboard + macOS menu bar app** for monitoring Claude Code & Codex token usage.

> Built by Rychu (the Silesian miner-turned-admin) & Przemek (Studio Lumo)

## What it does

- **🕹️ Dashboard** — NES 8-bit styled HTML dashboard with health-bar gauges
- **🍔 TokenBar** — Native macOS menu bar app showing Claude 5h usage at a glance
- **🔔 System Notifications** — macOS/Web notifications at 80%, 90%, 100% thresholds
- **📊 Multi-provider** — Tracks both Claude (Anthropic OAuth via TokenEater) and Codex (OpenAI OAuth via SQLite)
- **🎯 Smart recommendations** — Tells you which agent to delegate based on current limits

## Architecture

```
Claude (TokenEater) ──→ shared.json ──┐
                                       ├──→ tokentracker.py ──→ CLI report
Codex (SQLite) ──────→ state_5.sqlite ┘
                                       │
                                       ├──→ dashboard.html ──→ Browser (http://:8765)
                                       └──→ tokenbar.py ─────→ macOS Menu Bar
```

## Files

| File | Purpose |
|------|---------|
| `dashboard.html` | Pixel-art NES dashboard (open in browser) |
| `tokenbar.py` | macOS menu bar app (rumps) |
| `serve.py` | HTTP server + auto-refresh for dashboard |
| `tokentracker.py` | Text report generator |
| `token-dump.py` | JSON data dump for dashboard |
| `tokencheck` | CLI wrapper |

## Quick Start

```bash
# 1. Dashboard (requires web server):
python3 serve.py --port 8765
open http://localhost:8765

# 2. Menu bar app:
python3 tokenbar.py &

# 3. CLI quick check:
./tokencheck
```

## Requirements

- macOS 14+
- Python 3.9+
- pip: `rumps` (for menu bar app)
- **Claude**: [TokenEater](https://tokeneater.athevon.dev) installed (free macOS app)
- **Codex**: Codex CLI installed and authenticated (`~/.codex/` must exist)

## Data Sources

- **Claude**: Reads TokenEater's `shared.json` (`~/Library/Application Support/com.tokeneater.shared/`)
- **Codex**: Reads SQLite `~/.codex/state_5.sqlite` → `threads.tokens_used`

No API keys needed — everything uses existing OAuth sessions on disk.

## Notifications

System notifications fire at:
- ⚠️ **80%** — warning
- 🚨 **90%** — alert  
- 🔥 **100%** — limit exhausted
- 🔄 **Reset** — limit dropped from ≥80% to <10%

Each threshold fires only once per crossing. Resets when usage drops 5% below threshold.

## License

MIT — see [LICENSE](LICENSE)
