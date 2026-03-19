"""
main.py — Simple HTTP server for NYC Food Insecurity Dashboard
Serves index.html and all static files on the assigned port.
Run with: python3 main.py
"""

import http.server
import socketserver
import os
import json
from datetime import datetime

PORT = int(os.environ.get("PORT", 3000))

class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    """Serves static files with CORS headers for local API calls."""

    def end_headers(self):
        # Allow the dashboard to make API calls
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, x-api-key, anthropic-version')
        self.send_header('Cache-Control', 'no-cache')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def log_message(self, format, *args):
        # Clean up server logs
        if '200' in str(args):
            pass  # suppress successful requests
        else:
            print(f"  [{datetime.now().strftime('%H:%M:%S')}] {format % args}")


def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    print("=" * 55)
    print("  NYC Food Insecurity Vulnerability Dashboard")
    print("=" * 55)
    print(f"  Server starting on port {PORT}...")
    print()

    # Check all required files exist
    required_files = [
        "index.html",
        "vulnerability_scores.json",
    ]
    optional_files = [
        "community_districts.geojson",
        "alerts.json",
        "pantry_locations.geojson",
    ]

    print("  Checking required files:")
    all_ok = True
    for f in required_files:
        exists = os.path.exists(f)
        status = "OK" if exists else "MISSING"
        print(f"    [{status}] {f}")
        if not exists:
            all_ok = False

    print("\n  Checking optional files:")
    for f in optional_files:
        exists = os.path.exists(f)
        status = "OK" if exists else "not found (optional)"
        print(f"    [{status}] {f}")

    if not all_ok:
        print("\n  Some required files are missing.")
        print("  Run python3 process_data.py first to generate scores.\n")

    # Check environment variables
    print("\n  Checking secrets:")
    nyc_token = os.environ.get("NYC_OPEN_DATA_TOKEN", "")
    ant_key   = os.environ.get("ANTHROPIC_API_KEY", "")
    print(f"    NYC_OPEN_DATA_TOKEN: {'set' if nyc_token else 'not set -- data pipeline disabled'}")
    print(f"    ANTHROPIC_API_KEY:   {'set' if ant_key   else 'not set -- AI chat uses fallback responses'}")

    print(f"\n  Dashboard live on port {PORT}")
    print(f"  Open the Replit browser panel to view")
    print(f"  Press Ctrl+C to stop\n")

    with socketserver.TCPServer(("", PORT), DashboardHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n  Server stopped.")


if __name__ == "__main__":
    main()
