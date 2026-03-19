"""
main.py — HTTP server for NYC Food Insecurity Dashboard
Serves static files and proxies Anthropic AI requests.
Run with: python3 main.py
"""

import http.server
import socketserver
import os
import json
import urllib.request
import urllib.error
from datetime import datetime

PORT = int(os.environ.get("PORT", 3000))
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")


class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    """Serves static files with CORS headers; proxies /api/claude requests."""

    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
        self.send_header('Pragma', 'no-cache')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_POST(self):
        if self.path == '/api/claude':
            self._proxy_claude()
        else:
            self.send_response(404)
            self.end_headers()

    def _proxy_claude(self):
        length = int(self.headers.get('Content-Length', 0))
        body   = self.rfile.read(length)

        if not ANTHROPIC_API_KEY:
            self.send_response(503)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                "error": "ANTHROPIC_API_KEY not configured on server"
            }).encode())
            return

        try:
            req = urllib.request.Request(
                'https://api.anthropic.com/v1/messages',
                data=body,
                headers={
                    'Content-Type':      'application/json',
                    'x-api-key':         ANTHROPIC_API_KEY,
                    'anthropic-version': '2023-06-01',
                },
                method='POST'
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                resp_body = resp.read()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(resp_body)

        except urllib.error.HTTPError as e:
            err_body = e.read()
            self.send_response(e.code)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(err_body)

        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

    def log_message(self, format, *args):
        if '200' in str(args):
            pass
        else:
            print(f"  [{datetime.now().strftime('%H:%M:%S')}] {format % args}")


def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    print("=" * 55)
    print("  NYC Food Insecurity Vulnerability Dashboard")
    print("=" * 55)
    print(f"  Server starting on port {PORT}...")
    print()

    required_files = ["index.html", "vulnerability_scores.json"]
    optional_files = ["community_districts.geojson", "alerts.json", "pantry_locations.geojson"]

    print("  Checking required files:")
    all_ok = True
    for f in required_files:
        exists = os.path.exists(f)
        print(f"    [{'OK' if exists else 'MISSING'}] {f}")
        if not exists:
            all_ok = False

    print("\n  Checking optional files:")
    for f in optional_files:
        exists = os.path.exists(f)
        print(f"    [{'OK' if exists else 'not found (optional)'}] {f}")

    if not all_ok:
        print("\n  Some required files are missing.")
        print("  Run python3 process_data.py first to generate scores.\n")

    print("\n  Checking secrets:")
    nyc_token = os.environ.get("NYC_OPEN_DATA_TOKEN", "")
    print(f"    NYC_OPEN_DATA_TOKEN: {'set' if nyc_token else 'not set -- data pipeline disabled'}")
    print(f"    ANTHROPIC_API_KEY:   {'set -- AI chat enabled' if ANTHROPIC_API_KEY else 'not set -- AI chat uses fallback responses'}")

    print(f"\n  Dashboard live on port {PORT}")
    print(f"  Open the Replit browser panel to view")
    print(f"  Press Ctrl+C to stop\n")

    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), DashboardHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n  Server stopped.")


if __name__ == "__main__":
    main()
