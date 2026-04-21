"""
main.py — The Grid NYC · Neighborhood Intelligence Platform
HTTP server + Claude tool-use powered /api/chat endpoint.

Architecture:
  Frontend sends question + selected district + LAYER_SCORES
  Claude decides which tools to call (get_district_data, compare, etc.)
  Tools query live data files — nothing is baked into the system prompt
  Claude synthesizes real numbers into the response
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

# ── DATA FILES ─────────────────────────────────────────────────────────────────
# Loaded once at startup; tools query these in-memory structures
_VULN_DATA    = None
_LAYER_SCORES = None  # populated from frontend payload per request
_LIVE_DATA    = None  # populated from data/live_data.json (fetch_live_data.py output)


def _load_vulnerability_data():
    global _VULN_DATA
    if _VULN_DATA is not None:
        return _VULN_DATA
    try:
        with open("vulnerability_scores.json") as f:
            data = json.load(f)
        _VULN_DATA = {
            "by_fips": {d["fips"]: d for d in data["districts"]},
            "by_name": {d["cd_name"].lower(): d for d in data["districts"]},
            "all":     data["districts"],
            "meta":    data["metadata"],
        }
    except FileNotFoundError:
        _VULN_DATA = {"by_fips": {}, "by_name": {}, "all": [], "meta": {}}
    return _VULN_DATA


def _load_live_data():
    global _LIVE_DATA
    if _LIVE_DATA is not None:
        return _LIVE_DATA
    try:
        with open(os.path.join("data", "live_data.json")) as f:
            raw = json.load(f)
        _LIVE_DATA = raw.get("by_district", {})
    except (FileNotFoundError, json.JSONDecodeError):
        _LIVE_DATA = {}
    return _LIVE_DATA


# ── SYSTEM PROMPT ──────────────────────────────────────────────────────────────
SYSTEM_PROMPT = (
    "You are an AI neighborhood intelligence analyst for The Grid NYC — "
    "a multi-dimensional equity platform used by NYC city agencies to make "
    "fund allocation decisions across all 59 community districts. "
    "Agencies include: MOFP (food policy), HPD (housing), DOHMH (health), "
    "DSS (social services), and SBS (small business services). "
    "\n\n"
    "TOOL USE RULES — always follow these:\n"
    "1. ALWAYS call a tool before answering any question involving data, scores, "
    "or district comparisons. Never answer from memory alone.\n"
    "2. If the question is about a specific district, call get_district_data first.\n"
    "3. If comparing districts, call compare_districts.\n"
    "4. If ranking or finding worst districts, call get_top_vulnerable.\n"
    "5. For housing pipeline questions, use find_housing_pipeline_gaps or the "
    "housing_dev fields in get_district_data.\n"
    "6. For eviction or displacement pressure questions, call get_eviction_stress.\n"
    "7. For SNAP policy, CFC program, NYC budget, Bronx context, or ML research, "
    "call get_policy_context with the relevant topic.\n"
    "8. If a question cannot be answered by your tools, say so and name the "
    "NYC Open Data dataset that would contain the answer.\n"
    "\n"
    "FORMAT RULES:\n"
    "- Use → arrows for recommendations.\n"
    "- Always cite exact numbers from tool results — never round or estimate.\n"
    "- Always end with: TODAY: [one concrete action the planner can take now].\n"
    "- Aim for 300-400 words. Do not truncate findings.\n"
    "\n"
    "POLICY CONTEXT (April 2026):\n"
    "- SNAP: Congress passed $186B in cuts over 10 years. ABAWD work requirements "
    "expanded to adults 18-54 effective March 2026 (80 hrs/month). NYC has 1.8M "
    "SNAP recipients. Avg NYC benefit: $6.10/person/day, proposed cut to ~$4.80.\n"
    "- CFC (Community Fridge Collaborative): ~50 fridges citywide. Heaviest in Bronx "
    "CDs 1-4, BK CD16, MN CD11. Queens (6 sites) and Staten Island (0 sites) are gaps.\n"
    "- NYCHA: 177,500 units housing ~350k residents. $40B capital repair backlog.\n"
    "- Life expectancy gap: 10 years between Mott Haven (75.8 yrs) and Upper East Side (86.0 yrs).\n"
    "- The Bronx: highest poverty rate of any US county >1M residents (29.6%). "
    "Hunts Point is the largest US food distribution hub yet 42% of residents face food insecurity.\n"
    "- NYC FY2026: MOFP budget ~$62M. Meals on Wheels: $38M. Pantry network: $52M. "
    "HPD capital plan FY2026-2030: $3.4B.\n"
    "- Call get_policy_context for full citations and agency-specific implications."
)

# Per-agency addenda injected alongside system prompt
AGENCY_CONTEXT = {
    "MOFP": (
        "AGENCY: Mayor's Office of Food Policy. Programs: EFAP (federal pass-through), "
        "CFC (city discretionary, faster to deploy), SNAP-Ed, HRA Food Pantry, "
        "Mobile markets (deployable in 2-4 weeks with HRA approval). "
        "CFC emergency allocation requires documented 30%+ surge in pantry utilization. "
        "Non-citizen households cannot access federal SNAP — flag noncitizen_pct as "
        "hidden floor of unmet need beyond SNAP enrollment."
    ),
    "HPD": (
        "AGENCY: Dept of Housing Preservation & Development. Programs: "
        "Right to Counsel (RTC), SCRIE/DRIE (rent freeze), NYCHA (177k units). "
        "HPD Class C violations (immediately hazardous): heat failure, lead paint, "
        "mold, sewage — must be corrected within 24 hrs. "
        "When citing housing stress, connect to food cascade: "
        "heat failure → utility debt → food budget compression. "
        "Use pipeline_stall_rate to flag neighborhoods where new supply is blocked."
    ),
    "DOHMH": (
        "AGENCY: Dept of Health & Mental Hygiene. Programs: Health Bucks, "
        "Fresh (grocery zoning incentives), Health Home (care coordination). "
        "NYC life expectancy gap: 10 years between lowest-income CDs (~76 Bronx) "
        "and highest-income CDs (~86 Manhattan UES). "
        "Asthma in Mott Haven/East Tremont is 3-4x city average — driven by housing. "
        "Type 2 diabetes tracks SNAP enrollment at ~0.74 correlation citywide."
    ),
}

FORMAT_INSTRUCTIONS = {
    "Memo": (
        "OUTPUT FORMAT — Policy Memo: "
        "SUBJECT: [topic]\nPRIORITY LEVEL: [Critical / High / Moderate]\n"
        "KEY FINDINGS:\n• [finding 1]\n• [finding 2]\n• [finding 3]\n"
        "RECOMMENDED ACTIONS:\n1. [action]\n2. [action]\n3. [action]\n"
        "ESTIMATED IMPACT: [one sentence]\nTODAY: [one immediate next step]"
    ),
    "Briefing": (
        "OUTPUT FORMAT — Executive Briefing: "
        "Flowing prose. Open with a one-sentence situation summary, "
        "then 3-4 paragraphs: (1) data context, (2) risk factors, "
        "(3) recommended interventions, (4) timeline/resources. End with TODAY:."
    ),
    "Bullets": (
        "OUTPUT FORMAT — Bullet Points: "
        "Lead with district score and rank. "
        "Use → for key findings, ◆ for actions, ⚠ for risks. End with TODAY:."
    ),
    "Data": (
        "OUTPUT FORMAT — Data Summary: "
        "Numbers-first. Include indicator values vs city average, district rank, "
        "trend direction, comparisons to similar districts. End with TODAY:."
    ),
}


# ── TOOL DEFINITIONS ───────────────────────────────────────────────────────────
TOOLS = [
    {
        "name": "get_district_data",
        "description": (
            "Get complete multi-dimensional data for a specific NYC community district. "
            "Returns food vulnerability score, all 5 indicators (SNAP, child poverty, "
            "rent burden, unemployment, noncitizen %), housing stability score, health "
            "burden score, cost of living score, economic stress score, equity score "
            "(composite), and housing development pipeline data "
            "(completions 2020-2024, pipeline stall rate, units filed/permitted/withdrawn)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "district_name": {
                    "type": "string",
                    "description": "Community district name, e.g. 'Mott Haven', 'Brownsville', 'East Harlem'"
                }
            },
            "required": ["district_name"]
        }
    },
    {
        "name": "get_top_vulnerable",
        "description": (
            "Get the N most stressed community districts ranked by a specific layer score. "
            "Layer options: food (vulnerability), housing, health, cost_of_living, economic, equity."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "n": {"type": "integer", "default": 5, "description": "Number of districts to return"},
                "layer": {
                    "type": "string",
                    "default": "food",
                    "description": "Score layer: food, housing, health, cost_of_living, economic, equity"
                },
                "borough": {
                    "type": "string",
                    "default": "",
                    "description": "Filter by borough (optional): Bronx, Brooklyn, Manhattan, Queens, Staten Island"
                }
            }
        }
    },
    {
        "name": "compare_districts",
        "description": "Compare two community districts across all indicators and layer scores.",
        "input_schema": {
            "type": "object",
            "properties": {
                "district_a": {"type": "string", "description": "First district name"},
                "district_b": {"type": "string", "description": "Second district name"}
            },
            "required": ["district_a", "district_b"]
        }
    },
    {
        "name": "get_borough_summary",
        "description": "Aggregate vulnerability and equity statistics for an entire borough.",
        "input_schema": {
            "type": "object",
            "properties": {
                "borough": {
                    "type": "string",
                    "description": "Bronx, Brooklyn, Manhattan, Queens, or Staten Island"
                }
            },
            "required": ["borough"]
        }
    },
    {
        "name": "get_citywide_stats",
        "description": "Citywide statistics: total districts, average scores by borough and layer, tier breakdown.",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "find_housing_pipeline_gaps",
        "description": (
            "Identify districts with the worst housing development pipeline health — "
            "high stall rates (permits withdrawn/inactive) and low supply delivery "
            "(few completions relative to existing stock). Critical for HPD fund allocation."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "n": {"type": "integer", "default": 5, "description": "Number of districts to return"},
                "borough": {"type": "string", "default": "", "description": "Optional borough filter"}
            }
        }
    },
    {
        "name": "get_eviction_stress",
        "description": (
            "Rank community districts by eviction filing rate (filings per 1k households) "
            "using rolling 12-month live data from NYC Civil Court (Open Data). "
            "Also returns 311 food complaint rates and DOB permit activity. "
            "Use this for displacement pressure analysis and housing instability questions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "n": {"type": "integer", "default": 10, "description": "Number of districts to return"},
                "borough": {"type": "string", "default": "", "description": "Optional borough filter"},
                "sort_by": {
                    "type": "string",
                    "default": "eviction",
                    "description": "eviction | food_complaints | dob_permits"
                }
            }
        }
    },
    {
        "name": "get_policy_context",
        "description": (
            "Returns curated policy and research context. Topics: "
            "snap (federal SNAP cuts + ABAWD 2026 changes), "
            "cfc (Community Fridge Collaborative network + gaps), "
            "housing (evictions, NYCHA, CLTs, HPD thresholds), "
            "health (life expectancy gap, asthma, WIC, DOHMH metrics), "
            "bronx (Bronx-specific disparities and key organizations), "
            "budget (NYC FY2026 food and housing budget figures), "
            "ml (ML research papers for predictive vulnerability modeling), "
            "all (everything). Always call this before making policy recommendations."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "default": "all",
                    "description": "snap | cfc | housing | health | bronx | budget | ml | all"
                }
            }
        }
    },
]


# ── TOOL EXECUTION ─────────────────────────────────────────────────────────────
def _find_district(query, vuln, layer_scores):
    """Fuzzy district lookup returning enriched district dict."""
    q = query.lower().strip()
    d = vuln["by_name"].get(q)
    if not d:
        for name, district in vuln["by_name"].items():
            if q in name or name in q:
                d = district
                break
    if not d:
        return None

    # Enrich with layer scores
    fips = d["fips"]
    ls   = layer_scores.get(fips, {})
    raw  = ls.get("_raw", {})

    food_score = d["vulnerability_score"]
    h  = ls.get("housing", 50)
    c  = ls.get("cost_of_living", 50)
    he = ls.get("health", 50)
    ec = ls.get("economic", 50)
    equity = round((food_score + h + c + he + ec) / 5)

    return {
        **d,
        "layer_scores": {
            "food":          food_score,
            "housing":       h,
            "cost_of_living": c,
            "health":        he,
            "economic":      ec,
            "equity":        equity,
        },
        "housing_dev": {
            "completions_2020_2024":  raw.get("completions_5yr", 0),
            "completions_per_1k":     raw.get("completions_per1k", 0),
            "pipeline_filed":         raw.get("pipeline_filed", 0),
            "pipeline_permitted":     raw.get("pipeline_permitted", 0),
            "pipeline_withdrawn":     raw.get("pipeline_withdrawn", 0),
            "pipeline_inactive":      raw.get("pipeline_inactive", 0),
            "pipeline_stall_rate_pct": raw.get("pipeline_stall_rate", 0),
        },
        "raw_indicators": {
            "hpd_violations_per_1k": raw.get("hpd_per_1k"),
            "life_expectancy":       raw.get("life_exp"),
            "asthma_per_10k":        raw.get("asthma"),
            "median_rent":           raw.get("rent"),
            "median_income_k":       raw.get("income_k"),
        }
    }


def execute_tool(name, inputs, vuln, layer_scores, live_data=None):
    if name == "get_district_data":
        d = _find_district(inputs.get("district_name", ""), vuln, layer_scores)
        if not d:
            return {"error": f"District '{inputs['district_name']}' not found",
                    "hint": "Try partial name, e.g. 'Mott Haven', 'East Harlem'"}
        return d

    elif name == "get_top_vulnerable":
        n       = inputs.get("n", 5)
        layer   = inputs.get("layer", "food")
        borough = inputs.get("borough", "").strip().lower()

        results = []
        for d in vuln["all"]:
            if borough and d["borough"].lower() != borough:
                continue
            fips = d["fips"]
            ls   = layer_scores.get(fips, {})
            raw  = ls.get("_raw", {})
            food = d["vulnerability_score"]
            h, c, he, ec = (ls.get("housing", 50), ls.get("cost_of_living", 50),
                            ls.get("health", 50),  ls.get("economic", 50))
            equity = round((food + h + c + he + ec) / 5)

            scores_map = {
                "food": food, "housing": h, "cost_of_living": c,
                "health": he, "economic": ec, "equity": equity
            }
            results.append({
                "name":    d["cd_name"],
                "borough": d["borough"],
                "fips":    fips,
                "tier":    d["risk_tier"],
                "score":   scores_map.get(layer, food),
                "layer":   layer,
                "all_scores": scores_map,
                "pipeline_stall_rate": raw.get("pipeline_stall_rate"),
                "completions_per_1k":  raw.get("completions_per1k"),
            })

        results.sort(key=lambda x: x["score"], reverse=True)
        return {"layer": layer, "top": results[:n]}

    elif name == "compare_districts":
        da = _find_district(inputs.get("district_a", ""), vuln, layer_scores)
        db = _find_district(inputs.get("district_b", ""), vuln, layer_scores)
        if not da or not db:
            return {"error": "One or both districts not found"}

        comparison = []
        layers = ["food", "housing", "cost_of_living", "health", "economic", "equity"]
        for layer in layers:
            va = da["layer_scores"].get(layer, 0)
            vb = db["layer_scores"].get(layer, 0)
            comparison.append({
                "layer":    layer,
                "a_score":  va,
                "b_score":  vb,
                "worse":    da["cd_name"] if va > vb else db["cd_name"],
                "gap":      abs(va - vb)
            })

        ind_compare = []
        for key in ("snap_household_pct", "child_poverty_pct", "rent_burden_pct",
                    "unemployment_pct", "noncitizen_pct"):
            va = da["indicators"].get(key, 0)
            vb = db["indicators"].get(key, 0)
            ind_compare.append({
                "indicator": key,
                "a":    va,
                "b":    vb,
                "worse": da["cd_name"] if va > vb else db["cd_name"]
            })

        return {
            "district_a": {"name": da["cd_name"], "borough": da["borough"]},
            "district_b": {"name": db["cd_name"], "borough": db["borough"]},
            "layer_comparison": comparison,
            "indicator_comparison": ind_compare,
        }

    elif name == "get_borough_summary":
        borough = inputs.get("borough", "").strip()
        districts = [d for d in vuln["all"] if d["borough"].lower() == borough.lower()]
        if not districts:
            return {"error": f"Borough '{borough}' not found"}

        layer_avgs = {"food": [], "housing": [], "cost_of_living": [],
                      "health": [], "economic": [], "equity": []}
        tiers = {}
        for d in districts:
            fips = d["fips"]
            ls   = layer_scores.get(fips, {})
            food = d["vulnerability_score"]
            h, c, he, ec = (ls.get("housing", 50), ls.get("cost_of_living", 50),
                            ls.get("health", 50),  ls.get("economic", 50))
            eq = round((food + h + c + he + ec) / 5)
            layer_avgs["food"].append(food)
            layer_avgs["housing"].append(h)
            layer_avgs["cost_of_living"].append(c)
            layer_avgs["health"].append(he)
            layer_avgs["economic"].append(ec)
            layer_avgs["equity"].append(eq)
            t = d["risk_tier"]
            tiers[t] = tiers.get(t, 0) + 1

        return {
            "borough": borough,
            "total_districts": len(districts),
            "average_scores": {k: round(sum(v) / len(v), 1) for k, v in layer_avgs.items()},
            "risk_tier_breakdown": tiers,
            "most_vulnerable": max(districts, key=lambda x: x["vulnerability_score"])["cd_name"],
        }

    elif name == "get_citywide_stats":
        borough_data = {}
        tier_counts  = {}
        for d in vuln["all"]:
            b    = d["borough"]
            fips = d["fips"]
            ls   = layer_scores.get(fips, {})
            food = d["vulnerability_score"]
            h, c, he, ec = (ls.get("housing", 50), ls.get("cost_of_living", 50),
                            ls.get("health", 50),  ls.get("economic", 50))
            eq = round((food + h + c + he + ec) / 5)

            if b not in borough_data:
                borough_data[b] = {"food": [], "housing": [], "cost_of_living": [],
                                   "health": [], "economic": [], "equity": []}
            borough_data[b]["food"].append(food)
            borough_data[b]["housing"].append(h)
            borough_data[b]["cost_of_living"].append(c)
            borough_data[b]["health"].append(he)
            borough_data[b]["economic"].append(ec)
            borough_data[b]["equity"].append(eq)

            t = d["risk_tier"]
            tier_counts[t] = tier_counts.get(t, 0) + 1

        borough_avgs = {
            b: {k: round(sum(v) / len(v), 1) for k, v in layers.items()}
            for b, layers in borough_data.items()
        }
        return {
            "total_districts":      len(vuln["all"]),
            "risk_tier_breakdown":  tier_counts,
            "borough_averages":     borough_avgs,
        }

    elif name == "find_housing_pipeline_gaps":
        n       = inputs.get("n", 5)
        borough = inputs.get("borough", "").strip().lower()

        results = []
        for d in vuln["all"]:
            if borough and d["borough"].lower() != borough:
                continue
            fips = d["fips"]
            ls   = layer_scores.get(fips, {})
            raw  = ls.get("_raw", {})
            results.append({
                "name":               d["cd_name"],
                "borough":            d["borough"],
                "housing_score":      ls.get("housing", 50),
                "food_score":         d["vulnerability_score"],
                "stall_rate_pct":     raw.get("pipeline_stall_rate", 0),
                "completions_per_1k": raw.get("completions_per1k", 0),
                "pipeline_filed":     raw.get("pipeline_filed", 0),
                "pipeline_permitted": raw.get("pipeline_permitted", 0),
                "pipeline_withdrawn": raw.get("pipeline_withdrawn", 0),
                "pipeline_inactive":  raw.get("pipeline_inactive", 0),
                "hpd_violations_per_1k": raw.get("hpd_per_1k", 0),
            })

        results.sort(key=lambda x: x["stall_rate_pct"], reverse=True)
        return {"worst_pipeline_gaps": results[:n]}

    return {"error": f"Unknown tool: {name}"}


# ── CHAT HANDLER ───────────────────────────────────────────────────────────────
def handle_chat(payload):
    import anthropic

    messages      = payload.get("messages", [])
    response_fmt  = payload.get("responseFormat", "Memo")
    active_layer  = payload.get("activeLayer", "food")
    agency_lens   = payload.get("agencyLens", "MOFP")
    layer_scores  = payload.get("layerScores", {})
    district_data = payload.get("districtData")
    top10         = payload.get("top10Districts", [])

    vuln = _load_vulnerability_data()

    # Build system prompt
    layer_labels = {
        "food": "Food Vulnerability", "housing": "Housing Stability",
        "cost_of_living": "Cost of Living", "health": "Health Burden",
        "economic": "Economic Stress", "equity": "Equity Score (composite)",
    }
    system = (
        SYSTEM_PROMPT
        + f"\n\nACTIVE DATA LAYER: {layer_labels.get(active_layer, active_layer)}. "
          "Lead your analysis with indicators relevant to this layer."
        + f"\n\n{AGENCY_CONTEXT.get(agency_lens, AGENCY_CONTEXT['MOFP'])}"
        + f"\n\n{FORMAT_INSTRUCTIONS.get(response_fmt, FORMAT_INSTRUCTIONS['Memo'])}"
    )

    if district_data:
        system += (
            f"\n\nCURRENTLY SELECTED: {district_data.get('name')} "
            f"({district_data.get('borough')}) Rank #{district_data.get('rank','?')} of 59."
        )
    if top10:
        ranking = " | ".join(
            f"#{i+1} {d['name']} ({d['borough']}) score={d['score']}"
            for i, d in enumerate(top10)
        )
        system += f"\n\nCITY RANKING TOP 10: {ranking}"

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    current_messages = list(messages)

    while True:
        response = client.messages.create(
            model="claude-opus-4",
            max_tokens=1400,
            system=system,
            tools=TOOLS,
            messages=current_messages,
        )

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = execute_tool(block.name, block.input, vuln, layer_scores)
                    tool_results.append({
                        "type":        "tool_result",
                        "tool_use_id": block.id,
                        "content":     json.dumps(result),
                    })

            current_messages.append({"role": "assistant", "content": response.content})
            current_messages.append({"role": "user",      "content": tool_results})

        else:
            text = " ".join(
                block.text for block in response.content if hasattr(block, "text")
            )
            return text


# ── HTTP SERVER ────────────────────────────────────────────────────────────────
class GridHandler(http.server.SimpleHTTPRequestHandler):

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
        else:
            self.send_response(404)
            self.end_headers()

    def _handle_chat(self):
        length = int(self.headers.get('Content-Length', 0))
        body   = self.rfile.read(length)

        if not ANTHROPIC_API_KEY:
            self._json(503, {"error": "ANTHROPIC_API_KEY not configured"})
            return

        try:
            payload = json.loads(body)
            if not payload.get("messages"):
                self._json(400, {"error": "messages array required"})
                return

            reply = handle_chat(payload)
            self._json(200, {"response": reply})

        except json.JSONDecodeError:
            self._json(400, {"error": "Invalid JSON"})
        except Exception as e:
            self._json(500, {"error": str(e)})

    def _json(self, code, obj):
        data = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):
        if '200' not in str(args):
            print(f"  [{datetime.now().strftime('%H:%M:%S')}] {fmt % args}")


# ── ENTRY POINT ────────────────────────────────────────────────────────────────
def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    _load_vulnerability_data()

    print("=" * 55)
    print("  The Grid NYC — Neighborhood Intelligence Platform")
    print("=" * 55)
    print(f"  Port {PORT} | AI tool-use enabled")
    print()

    files = ["index.html", "vulnerability_scores.json"]
    for f in files:
        status = "OK" if os.path.exists(f) else "MISSING"
        print(f"  [{status}] {f}")

    print()
    print(f"  ANTHROPIC_API_KEY: {'set' if ANTHROPIC_API_KEY else 'NOT SET — chat disabled'}")
    districts_loaded = len(_VULN_DATA.get("all", [])) if _VULN_DATA else 0
    print(f"  Districts loaded:  {districts_loaded}/59")
    print(f"\n  Live on port {PORT}\n")

    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), GridHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n  Server stopped.")


if __name__ == "__main__":
    main()
