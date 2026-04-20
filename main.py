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
    "You are an AI neighborhood intelligence analyst for The Grid NYC — "
    "a multi-dimensional equity platform used by the NYC Mayor's Office of Food Policy "
    "and other city agencies to make fund allocation decisions. "
    "You have access to live data for all 59 NYC community districts across five dimensions: "
    "Food Vulnerability, Housing Stability, Cost of Living, Health Burden, and Economic Stress. "
    "Each district has an Equity Score (0-100) that composites all five dimensions. "
    "Federal context: $186B SNAP cuts incoming, 1.8M NYC SNAP recipients at risk, "
    "SNAP work requirements effective March 2026. "
    "Always format recommendations with → arrows. "
    "Rules: "
    "1. When an active data layer is specified, lead your analysis with that layer's indicators "
    "for the selected district, then connect to the other dimensions. "
    "2. Always cite specific scores and percentages — never give generic analysis. "
    "3. When discussing fund allocation, reference the Equity Score and gap between need and "
    "current investment. "
    "4. When discussing SNAP cuts, always cite the $186B figure and March 2026 deadline. "
    "5. Always end every response with a line starting 'TODAY:' followed by one concrete "
    "next step the planner can take immediately. "
    "6. Aim for 300-400 words. Do not truncate findings or recommendations."
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
            active_layer   = payload.get("activeLayer", "food")
            agency_lens    = payload.get("agencyLens", "MOFP")
            layer_scores   = payload.get("layerScores", {})

            if not messages:
                self._json_response(400, {"error": "messages array is required"})
                return

            # ── Build system context ──────────────────────────────────────────
            system = SYSTEM_PROMPT

            # Active layer context
            layer_labels = {
                "food": "Food Vulnerability",
                "housing": "Housing Stability",
                "cost_of_living": "Cost of Living",
                "health": "Health Burden",
                "economic": "Economic Stress",
                "equity": "Equity Score (composite)",
            }
            system += (
                f"\n\nACTIVE DATA LAYER: {layer_labels.get(active_layer, active_layer)}. "
                "Lead your analysis with indicators relevant to this layer."
            )

            # Agency lens context — program knowledge specific to the requesting agency
            agency_context = {
                "MOFP": (
                    "AGENCY CONTEXT — Mayor's Office of Food Policy (MOFP): "
                    "You are advising food policy planners. Reference these specific programs and mechanisms: "
                    "EFAP (Emergency Food Assistance Program) — federal pass-through, allocated by state to city; "
                    "CFC (City Funding for Community Organizations) — city discretionary, faster to deploy than federal; "
                    "SNAP-Ed — nutrition education tied to SNAP enrollment, can be co-located with pantries; "
                    "HRA Food Pantry Program — city-run network supplementing CFC partners; "
                    "Mobile food markets — can be deployed within 2–4 weeks with HRA approval. "
                    "Key threshold: CFC emergency allocation requires documented 30%+ surge in pantry utilization. "
                    "Non-citizen households (cannot access federal SNAP) rely entirely on EFAP and CFC — "
                    "always flag non-citizen % as a hidden floor of unmet need beyond SNAP enrollment numbers. "
                    "ABAWD (Able-Bodied Adults Without Dependents) work requirements take effect March 2026 — "
                    "estimate ABAWD exposure as roughly 18–22% of adult SNAP recipients in high-unemployment districts."
                ),
                "HPD": (
                    "AGENCY CONTEXT — Dept of Housing Preservation & Development (HPD): "
                    "You are advising housing preservation planners. Reference these specific programs: "
                    "Right to Counsel (RTC) — free legal representation for tenants in housing court, "
                    "available city-wide since 2022, reduces eviction rates ~40% where utilized; "
                    "SCRIE/DRIE — rent freeze for seniors/disabled on fixed income, underutilized in high-need CDs; "
                    "NYCHA — public housing authority managing ~177K units; "
                    "HPD Class C violations (immediately hazardous) must be corrected within 24 hours by law — "
                    "heat failures, lead paint (units with children under 6), vermin, mold, sewage; "
                    "Class B (hazardous) within 30 days; Class A (non-hazardous) within 90 days. "
                    "Key correlation: districts with rent burden >55% AND high non-citizen % systematically "
                    "under-report violations due to documentation fear — treat these as hidden high-violation zones. "
                    "When citing housing stress, connect to food insecurity cascade: "
                    "heat failure → utility debt → food budget compression; "
                    "mold/roach → food contamination + asthma → medical debt → SNAP dependency."
                ),
                "DOHMH": (
                    "AGENCY CONTEXT — Dept of Health & Mental Hygiene (DOHMH): "
                    "You are advising public health planners. Reference these specific programs and data: "
                    "Health Bucks — $2 coupons redeemable at farmers markets, doubled for SNAP users, "
                    "underutilized in districts farthest from greenmarkets; "
                    "Fresh program — zoning incentives for grocery stores in underserved areas; "
                    "Health Home program — care coordination for high-utilizers, often food-insecure; "
                    "DOHMH Community Health Survey — district-level chronic disease prevalence data. "
                    "Key health-food links to cite: "
                    "NYC life expectancy gap is 10 years between lowest-income CDs (Bronx ~76) and "
                    "highest-income CDs (UES Manhattan ~86); "
                    "asthma hospitalization rates in Mott Haven/East Tremont are 3–4× city average — "
                    "driven by mold/roach violations in housing stock; "
                    "Type 2 diabetes prevalence tracks SNAP enrollment at ~0.74 correlation city-wide; "
                    "food insecurity is a clinical risk factor — ask about FQHC (Federally Qualified Health Centers) "
                    "co-location with food pantries as an intervention model."
                ),
            }
            system += f"\n\n{agency_context.get(agency_lens, agency_context['MOFP'])}"

            # 1. Selected district — full live indicators + multi-layer scores
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
                # Append multi-layer scores if provided
                if layer_scores:
                    fips = district_data.get("fips", "")
                    scores = layer_scores.get(fips, {})
                    if scores:
                        food_score = district_data.get("vulnerability_score", "?")
                        eq = round((float(food_score) + scores.get("housing", 50) +
                                    scores.get("cost_of_living", 50) + scores.get("health", 50) +
                                    scores.get("economic", 50)) / 5)
                        system += (
                            f" Multi-dimensional scores: "
                            f"Housing Stability {scores.get('housing', '?')}/100, "
                            f"Cost of Living {scores.get('cost_of_living', '?')}/100, "
                            f"Health Burden {scores.get('health', '?')}/100, "
                            f"Economic Stress {scores.get('economic', '?')}/100, "
                            f"Equity Score (composite) {eq}/100."
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
