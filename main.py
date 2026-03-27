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
    "You have access to live vulnerability data for all 59 NYC community districts. "
    "Federal context: $186B SNAP cuts incoming, 1.8M NYC SNAP recipients at risk, "
    "SNAP work requirements effective March 2026. "
    "Always format recommendations with → arrows. "
    "Rules: "
    "1. When discussing a specific district, always lead with its exact vulnerability score, "
    "rank out of 59, risk tier, and all five live indicators "
    "(SNAP %, child poverty %, rent burden %, unemployment %, non-citizen %). "
    "2. When discussing pantry gaps, cite the pantry count and coverage for affected areas "
    "using the pantry data provided in context. "
    "3. When discussing SNAP cuts, always cite the $186B figure and March 2026 deadline. "
    "4. Always end every response with a line starting 'TODAY:' followed by one concrete "
    "next step the planner can take immediately. "
    "5. Aim for 300-400 words for thorough, complete analysis. "
    "Do not truncate findings or recommendations."
)

# Per-format output instructions injected alongside the system prompt
FORMAT_INSTRUCTIONS = {
    "Memo": (
        "OUTPUT FORMAT — Policy Memo: "
        "Structure your response exactly as: "
        "SUBJECT: [topic]\n"
        "PRIORITY LEVEL: [Critical / High / Moderate]\n"
        "KEY FINDINGS:\n• [finding 1]\n• [finding 2]\n• [finding 3]\n"
        "RECOMMENDED ACTIONS:\n1. [action]\n2. [action]\n3. [action]\n"
        "ESTIMATED IMPACT: [one sentence]\n"
        "TODAY: [one immediate next step]"
    ),
    "Briefing": (
        "OUTPUT FORMAT — Executive Briefing: "
        "Write in flowing prose. Open with a one-sentence situation summary, "
        "then 3-4 paragraphs: (1) data context and current indicators, "
        "(2) risk factors and contributing dynamics, "
        "(3) recommended interventions with rationale, "
        "(4) timeline and resource implications. End with TODAY: action."
    ),
    "Bullets": (
        "OUTPUT FORMAT — Bullet Points: "
        "Use only bullet points. No prose paragraphs. "
        "Lead with district score and rank. "
        "Use → for key findings, ◆ for recommended actions, ⚠ for risks. "
        "End with TODAY: action."
    ),
    "Data": (
        "OUTPUT FORMAT — Data Summary: "
        "Present all information in a structured, numbers-first format. "
        "Include: indicator values vs city average, district rank, "
        "year-over-year trend direction, and comparison to similar districts. "
        "Minimal narrative — let the numbers lead. End with TODAY: action."
    ),
}


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
            messages       = payload.get("messages", [])
            district       = payload.get("district")
            district_data  = payload.get("districtData")
            top10          = payload.get("top10Districts", [])
            pantry_data    = payload.get("pantryData", [])
            response_fmt   = payload.get("responseFormat", "Memo")

            if not messages:
                self._json_response(400, {"error": "messages array is required"})
                return

            # ── Build system context ──────────────────────────────────────────
            system = SYSTEM_PROMPT

            # 1. Selected district — full live indicators
            if district_data:
                ind = district_data.get("indicators", {})
                system += (
                    f"\n\nCURRENTLY SELECTED DISTRICT: {district_data.get('name')} "
                    f"({district_data.get('borough')}) — "
                    f"Rank #{district_data.get('rank', '?')} of 59. "
                    f"Vulnerability Score: {district_data.get('vulnerability_score')} "
                    f"({district_data.get('risk_tier')} tier). "
                    f"Live indicators: "
                    f"SNAP enrollment {ind.get('snap_household_pct')}%, "
                    f"Child poverty {ind.get('child_poverty_pct')}%, "
                    f"Rent burden {ind.get('rent_burden_pct')}%, "
                    f"Unemployment {ind.get('unemployment_pct')}%, "
                    f"Non-citizen pop {ind.get('noncitizen_pct')}%. "
                    f"Always cite these exact numbers when discussing this district."
                )
            elif district:
                system += f"\n\nThe user is currently viewing: {district}."

            # 2. Full city ranking — top 10 most vulnerable districts
            if top10:
                ranking_lines = " | ".join(
                    f"#{i+1} {d.get('name')} ({d.get('borough')}) score={d.get('score')} [{d.get('tier')}]"
                    for i, d in enumerate(top10)
                )
                system += f"\n\nCITY VULNERABILITY RANKING (top 10 of 59): {ranking_lines}"

            # 3. Pantry coverage by area
            if pantry_data:
                pantry_lines = ", ".join(
                    f"{p.get('name')} ({p.get('count')} pantry{'s' if p.get('count',1)>1 else ''})"
                    for p in pantry_data
                )
                system += f"\n\nPANTRY COVERAGE (mapped locations): {pantry_lines}"

            # 4. Response format instruction
            fmt_instruction = FORMAT_INSTRUCTIONS.get(response_fmt, FORMAT_INSTRUCTIONS["Memo"])
            system += f"\n\n{fmt_instruction}"

            # ── Call Anthropic ────────────────────────────────────────────────
            try:
                import anthropic
                client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
                result = client.messages.create(
                    model="claude-opus-4",
                    max_tokens=800,
                    system=system,
                    messages=messages,
                )
                reply = result.content[0].text
                self._json_response(200, {"response": reply})

            except ImportError:
                # Fall back to raw HTTP if the package isn't available
                req_body = json.dumps({
                    "model": "claude-opus-4",
                    "max_tokens": 800,
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
