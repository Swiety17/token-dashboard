#!/usr/bin/env python3
"""
Token Dashboard Server — serwuje pikselartowy dashboard + auto-odświeża dane.
Usage: python3 serve.py [--port PORT]
"""
import http.server
import json
import os
import sys
import subprocess
import time
import threading
from pathlib import Path

PORT = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[1] == '--port' else 8765
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def dump_data():
    """Wywołuje token-dump.py aby odświeżyć token-data.json."""
    dump_script = os.path.join(SCRIPT_DIR, 'token-dump.py')
    try:
        subprocess.run(
            [sys.executable, dump_script],
            capture_output=True, text=True, timeout=30,
            cwd=SCRIPT_DIR
        )
        return True
    except Exception as e:
        print(f"[dump] Error: {e}")
        return False

def auto_refresh(interval=30):
    """W tle odświeża dane co interval sekund."""
    while True:
        time.sleep(interval)
        print(f"[refresh] Updating token data...")
        dump_data()

class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=SCRIPT_DIR, **kwargs)

    def log_message(self, format, *args):
        print(f"[{self.client_address[0]}] {format % args}")

    def do_GET(self):
        if self.path == '/' or self.path == '':
            self.path = '/dashboard.html'
        elif self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode())
            return
        return super().do_GET()

if __name__ == '__main__':
    print(f"""
╔══════════════════════════════════════════════╗
║   🪙  TOKEN DASHBOARD — Pixel Art Server  🪙  ║
╠══════════════════════════════════════════════╣
║  Dashboard: http://localhost:{PORT}             ║
║  Health:    http://localhost:{PORT}/health      ║
║  Data:      token-data.json (auto {30}s)        ║
║  Ctrl+C to stop                                 ║
╚══════════════════════════════════════════════╝
""")

    # Initial dump
    print("[init] First data dump...")
    dump_data()

    # Start background refresher
    refresher = threading.Thread(target=auto_refresh, args=(30,), daemon=True)
    refresher.start()

    # Start server
    server = http.server.HTTPServer(('', PORT), DashboardHandler)
    try:
        print(f"[server] Ready at http://localhost:{PORT}")
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[server] Shutting down...")
        server.shutdown()
