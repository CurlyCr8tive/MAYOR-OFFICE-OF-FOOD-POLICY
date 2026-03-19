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

SYSTEM_PROMPT = (
    "You are an AI food policy analyst for the NYC Mayor's Office of Food Policy. "
    "You have access to vulnerability data for all 59 NYC community districts. "
    "8 Critical districts are all in the Bronx except Brownsville Brooklyn. "
    "Top critical: University Heights 91.2, Morrisania 88.6, Mott Haven 87.5, "
    "East Tremont 86.4, Hunts Point 84.6. "
    "Federal context: $186B SNAP cuts incoming, 1.8M NYC SNAP recipients at risk, "
    "work requirements March 2026. "
    "Pantry gaps: East Tremont 2.1 per 10k, Brownsville 2.4 per 10k, "
    "Hunts Point 2.8 per 10k. "
    "Keep responses under 120 words. Be specific, data-driven, and actionable. "
    "Format recommendations with → arrows."
)


class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    """Serves static files with CORS headers; handles /api/chat requests."""

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
        if self.path == '/api/chat':
            self._handle_chat()
        elif self.path == '/api/claude':
            self._proxy_claude()
        else:
            self.send_response(404)
            self.end_headers()

    # ── /api/chat — clean endpoint with server-side system prompt ──────────────

    def _handle_chat(self):
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length)

        if not ANTHROPIC_API_KEY:
            self._json_response(503, {"error": "ANTHROPIC_API_KEY not configured on server"})
            return

        try:
            payload = json.loads(body)
            messages = payload.get("messages", [])
            district = payload.get("district")

            if not messages:
                self._json_response(400, {"error": "messages array is required"})
                return

            # Optionally inject district context into the system prompt
            system = SYSTEM_PROMPT
            if district:
                system += f" The user is currently viewing data for: {district}."

            # Call Anthropic using urllib (anthropic package not always importable
            # in all Python envs; fall back to direct HTTP so no import needed)
            try:
                import anthropic
                client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
                result = client.messages.create(
                    model="claude-opus-4-5",
                    max_tokens=400,
                    system=system,
                    messages=messages,
                )
                reply = result.content[0].text
                self._json_response(200, {"response": reply})

            except ImportError:
                # Fall back to raw HTTP if the package isn't available
                req_body = json.dumps({
                    "model": "claude-opus-4-5",
                    "max_tokens": 400,
                    "system": system,
                    "messages": messages,
                }).encode()
                req = urllib.request.Request(
                    'https://api.anthropic.com/v1/messages',
                    data=req_body,
                    headers={
                        'Content-Type': 'application/json',
                        'x-api-key': ANTHROPIC_API_KEY,
                        'anthropic-version': '2023-06-01',
                    },
                    method='POST'
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = json.loads(resp.read())
                reply = data['content'][0]['text']
                self._json_response(200, {"response": reply})

        except json.JSONDecodeError:
            self._json_response(400, {"error": "Invalid JSON body"})
        except urllib.error.HTTPError as e:
            err = json.loads(e.read()).get("error", {}).get("message", str(e))
            self._json_response(e.code, {"error": err})
        except Exception as e:
            self._json_response(500, {"error": str(e)})

    # ── /api/claude — legacy raw pass-through proxy ────────────────────────────

    def _proxy_claude(self):
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length)

        if not ANTHROPIC_API_KEY:
            self._json_response(503, {"error": "ANTHROPIC_API_KEY not configured on server"})
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
            self.send_response(e.code)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(e.read())
        except Exception as e:
            self._json_response(500, {"error": str(e)})

    # ── helpers ────────────────────────────────────────────────────────────────

    def _json_response(self, code, obj):
        data = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(data)

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
