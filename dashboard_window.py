#!/usr/bin/env python3
"""
Token Watch — Native macOS Dashboard Window
Uses pywebview (native WebKit) to show the dashboard in a standalone window.
Spawned by tokenbar.py when user clicks the menu bar icon.
"""
import webview
import time
import json
import os

DASHBOARD_URL = "http://localhost:8765"
WINDOW_TITLE = "⛏ TOKEN WATCH — Dziadek Górnik"

# Wait for server (tokenbar.py starts it automatically)
for _ in range(30):
    try:
        import urllib.request
        urllib.request.urlopen(DASHBOARD_URL + "/health", timeout=1)
        break
    except Exception:
        time.sleep(0.5)

# Create native WebKit window
webview.create_window(
    title=WINDOW_TITLE,
    url=DASHBOARD_URL,
    width=1020,
    height=740,
    min_size=(860, 600),
    resizable=True,
    fullscreen=False,
    text_select=True,
    easy_drag=False,
)

webview.start()
