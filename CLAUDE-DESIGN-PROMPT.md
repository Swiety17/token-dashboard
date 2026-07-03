You are an expert UI designer. Create a complete, self-contained HTML dashboard
that monitors AI token usage for two services: Claude (Anthropic) and Codex (OpenAI).
The artifact is a real-time monitoring dashboard — not a marketing page.

## Audience

A single developer who uses both Claude Code and Codex CLI daily. They need to
quickly see: "am I close to my limit? which service should I use next?"

## Format

Single self-contained HTML file. Embedded CSS in <style>, JS in <script>.
Font: "Press Start 2P" from Google Fonts (retro pixel aesthetic).
No frameworks, no CDN dependencies except the font.
Must work opened directly via file:// or localhost.

## Visual System — NES 8-bit Pixel Art Aesthetic

Palette (dark terminal with retro game accents):

```
Background:   #0a0a1a  (deep navy-black)
Panel surface: #12122a  (slightly lighter navy)
Borders:       #2a2a5a  (purple-blue border)
Text:          #e0e0f0  (off-white)
Dim text:      #606090  (muted lavender)
Accent:        #40c0ff  (cyan-blue)
Green:         #40e040  (NES green for safe)
Yellow:        #f8d830  (NES gold for warning)
Red:           #f04040  (NES red for danger)
```

Typography:
- All text in "Press Start 2P", monospace fallback, font-size 11px base
- No anti-aliasing: -webkit-font-smoothing: none; image-rendering: pixelated
- Uppercase labels, tight letter-spacing

Layout:
- CSS Grid: two equal columns (Claude left, Codex right) + full-width footer
- Max width 960px, gap 20px, padding 28px
- Panels: 5px solid border, 5px 5px 0 box-shadow (pixel drop shadow)
- No rounded corners anywhere. Everything is square/rectangular.

**IMPORTANT: No animations. No blinking. No CRT scanlines. No pulsing.**
All elements are static. Color alone communicates state (safe/warn/danger).

## Components

### 1. Claude Panel (left column, header: "🔵 CLAUDE" + "PLAYER 1" label)

Three gauge bars stacked vertically:

```
Label row:  "5 GODZIN" left-aligned, "85%" right-aligned
Bar:        18px tall, dark bg #1a1a3a, fill color by percentage
            safe: #40e040 (<80%), warn: #f8d830 (80-89%), danger: #f04040 (90%+)
Below bar:  "RESET: 45min" in dim small text (right-aligned)

(Same for "7 DNI" and "EXTRA KREDYTY")
```

Below gauges: a row of 7 small blocks (daily pacing) — each 10px tall, filled=solid accent, empty=dark background.

Then a 2×2 grid of stat blocks:
- Tokeny 7d (big number)
- Peak Day (big number)
- Pacing (label)
- Źródło: TokenEater

### 2. Codex Panel (right column, header: "🟢 CODEX" + "PLAYER 2" label)

2×3 grid of stat blocks:
- Wątków (thread count)
- Tokenów (total tokens, big number)
- 24h (tokens)
- 7 dni (tokens)
- 30 dni (tokens)
- Max wątek (big number)

Below stats: list of "Top threads" — each row shows truncated thread name left + token count right in compact bordered blocks.

### 3. Recommendation Strip (full width, bottom)

Centered: "REKOMENDACJA:" label followed by a bordered badge.

Badge logic (drive from Claude 5-hour percentage):
- <60%: "✅ CLAUDE — LUZ" (gold border, gold text)
- 60-79%: "⚡ ROZWAŻ CODEX" (gold border, gold text)
- 80-89%: "⚠ UŻYJ CODEX — 80%+" (green border, green text)
- 90%+: "🔥 UŻYJ CODEX — 90%+" (green border, green text)

### 4. Clock Footer

"OSTATNIA AKTUALIZACJA: HH:MM:SS" in dim text, centered, small.

### 5. System Notifications (Web Notification API)

- Request permission on page load (`Notification.requestPermission()`)
- On every data refresh (every 30s), check all Claude buckets against thresholds: 80%, 90%, 100%
- Fire a notification only when crossing UPWARD past a threshold (not every refresh)
- Track fired thresholds per bucket to avoid repeats
- Reset fired state when percentage drops 5% below threshold (so it can re-fire on next crossing)
- On reset detection (previous >=80%, current <10%): fire a "limit odświeżony" notification
- Notification: `requireInteraction: true` so it stays until clicked

## Data Source

The page fetches `token-data.json` from the same directory every 30 seconds.

JSON structure (provided by external script):

```json
{
  "ts": "ISO timestamp",
  "claude": {
    "provider": "claude",
    "available": true,
    "buckets": {
      "five_hour": {"label": "5h", "pct": 85, "remaining_min": 45},
      "seven_day": {"label": "7d", "pct": 12, "remaining_min": 1440},
      "extra_usage": {"label": "Extra", "pct": 0, "limit": 1000, "used": 0, "currency": "EUR", "enabled": false}
    },
    "daily": [5425, 0, 300745, 30216, 0, 0, 5727],
    "total_7d": 342113,
    "peak_day": 300745,
    "pacing": "balanced"
  },
  "codex": {
    "provider": "codex",
    "available": true,
    "summary": {"threads": 86, "total": 543704931, "peak": 161424825},
    "windows": {
      "24h": {"threads": 1, "tokens": 0},
      "7d": {"threads": 6, "tokens": 553147},
      "30d": {"threads": 27, "tokens": 150406184}
    },
    "top": [
      {"title": "projekt proxmox", "tokens": 161424825, "model": "gpt-5.5"},
      {"title": "blocklisty pi-hole", "tokens": 54631427, "model": "gpt-5.5"}
    ]
  }
}
```

## Number formatting

Helper function:
- >= 1B → "1.62B"
- >= 1M → "543.70M"
- >= 1K → "553.1K"
- else raw number

## States

- Loading: panel content shows "ŁADOWANIE..." in dim text
- Error/unavailable: panel content shows "BRAK DANYCH" in red
- Normal: data displayed

## Constraints

- No JavaScript frameworks (React, Vue, etc.)
- No CSS frameworks (Tailwind, Bootstrap, etc.)
- No external network requests except the font CSS and `token-data.json` fetch
- No hover animations, no transitions, no keyframes
- No rounded corners, no gradients, no shadows except the pixel box-shadow on panels
- Mobile: stack columns below 600px

## Deliverable

One file: `dashboard.html`. All CSS in <style>, all JS in <script>.
Openable directly in browser. Fetch data from `token-data.json` (relative path).
Auto-refresh every 30 seconds. System notifications at thresholds.

Write the complete HTML now — no placeholders, no summaries.
