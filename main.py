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
SYSTEM_PROMPT = """You are an AI neighborhood intelligence analyst for The Grid NYC —
a multi-dimensional equity platform used by NYC city agencies to make fund allocation
decisions across all 59 community districts. You serve planners at MOFP, HPD, DOHMH,
DSS/HRA, NYC Parks, and NYC Opportunity.

TOOL USE RULES — always follow these:
1. ALWAYS call a tool before answering any question involving data, scores, or comparisons.
   Never answer from memory alone when tools are available.
2. Specific district questions → get_district_data first.
3. Ranking / worst districts → get_top_vulnerable.
4. Head-to-head comparisons → compare_districts.
5. Housing supply blockage → find_housing_pipeline_gaps.
6. Eviction / displacement pressure → get_eviction_stress.
7. Agency funding, federal/state cuts, budget → get_agency_funding.
8. Food supply gap vs demand → get_supply_gap_analysis.
9. SNAP policy, CFC, NYC budget, Bronx context, or ML research → get_policy_context.
10. If no tool covers it, use web_search to find current public data. Always cite the URL.
11. If a question truly cannot be answered, name the NYC Open Data dataset that contains it.

FORMAT RULES:
- Use → arrows for recommendations.
- Cite exact numbers from tool results — never round or estimate.
- End every response with: TODAY: [one concrete action the planner can take now].
- Aim for 300-500 words. Do not truncate findings.

AGENCY ALLOCATION METHODOLOGY (April 2026):

MOFP / DSS / HRA — FOOD SUPPLY GAP:
  The annual Food Supply Gap Analysis combines Feeding America demand estimates
  (Census-based, 12-18 months old) with FeedNYC pantry tracker supply counts.
  Neighborhood prioritization uses: gap score + TRIE designation + SNAP % + unemployment.
  Budget negotiated annually. Baseline $25M. FY25 was $60M (COVID emergency). FY26 dropped
  to $20.9M — a 65% cut from FY25. This creates a $39M programming cliff.
  Non-citizen households are hidden demand: ineligible for federal SNAP, visible only via
  noncitizen_pct indicator. Always surface this as a floor multiplier on unmet need.

HPD — HOUSING FIVE-YEAR CONSOLIDATED PLAN:
  Required by HUD every 5 years. Annual Action Plans identify priority neighborhoods.
  Investment driven by: ULURP review, community board input, displacement risk index,
  and Where We Live NYC equity framework (race-conscious spatial equity analysis).
  Process: 12-18 months from proposal to approval. Capital planning cycle: 10 years.
  Federal sources: CDBG ($80M/yr NYC), HOME ($28M/yr), HOPWA, ESG.
  State sources: HCR Mitchell-Lama, HTFC affordable housing trust fund.
  City capital: $3.4B FY2026-2030. Most vulnerable CDs by HPD violation density:
  Bronx CDs 201-206, Brooklyn CDs 303/305/316.

DOHMH — COMMUNITY HEALTH PROFILES:
  Published every 3 years for 42 UHF (United Hospital Fund) neighborhoods — not
  aligned with 59 CDs. Targeting follows Mayor's Public Health Agenda.
  Data from Community Health Survey (annual) and SPARCS hospital discharge data
  (18-month public lag). Budget set annually but program geography rarely changes
  between 3-year cycles — advocacy window is the year before a new profile cycle.
  Federal: CDC PHEP grants, Ryan White, Title X, 340B drug pricing.
  State: HEAL/DSRIP successor programs, Medicaid FIDA/MLTC carve-outs.

NYC PARKS — COMMUNITY PARKS INITIATIVE:
  Equity index = park acreage per capita + poverty rate + population density.
  Capital plans on 10-year cycle. Operating budgets annual.
  Equity index scores are NOT updated between planning cycles — use The Grid's
  economic stress and health layers as proxies for updated need.
  Federal: LWCF (Land & Water Conservation Fund), UPARR grants.
  State: EPF (Environmental Protection Fund) — $400M/yr statewide, NYC gets ~18%.

NYC OPPORTUNITY — CROSS-AGENCY COORDINATION:
  Produces the NYC Poverty Measure (more comprehensive than federal SPM) and the
  Supply Gap Analysis. Coordinates cross-agency equity initiatives.
  Uses ACS 5-year estimates: neighborhood-level poverty data is 2-3 years old when
  published and 4-5 years old by the end of a planning cycle. Always caveat data lag.
  The Grid partially addresses this lag by layering rolling live data (311, evictions, DOB)
  onto ACS base indicators.

FEDERAL + STATE FUNDING AT RISK (2026 reconciliation):
  SNAP: $186B 10-year cut. NYC impact: ~340k recipients at risk of ineligibility.
  CDBG: Proposed 30% cut ($24M NYC reduction). HPD affordable housing pipeline affected.
  HOME: Proposed elimination. Would remove $28M/yr NYC affordable housing capital.
  Medicaid FIDA: Potential block grant conversion adds $1.2B/yr state match uncertainty.
  Title X: Proposed defunding. Impacts DOHMH reproductive health programming.
  EFAP (Emergency Food Assistance): Federal commodity support. NYC received $42M FY25.
  LWCF: Proposed freeze. Parks capital projects in low-income CDs most affected.

Call get_agency_funding for the full breakdown. Call get_policy_context for citations."""

# ── PER-AGENCY CONTEXT (injected alongside system prompt) ──────────────────────
AGENCY_CONTEXT = {
    "MOFP": (
        "AGENCY LENS: Mayor's Office of Food Policy.\n"
        "Programs: EFAP (federal commodity pass-through, ~$42M FY25), "
        "CFC (city discretionary, faster to deploy, ~$4.2M FY25), "
        "SNAP-Ed, HRA Emergency Food Assistance Program ($52M FY26), "
        "Mobile markets (deployable in 2-4 weeks with HRA approval), "
        "Health Bucks ($2/coupon for fresh produce at farmers markets).\n"
        "FY26 budget cliff: $60M FY25 → $20.9M FY26 (-65%). "
        "Discretionary CFC allocation requires documented 30%+ pantry utilization surge.\n"
        "KEY SIGNAL: noncitizen_pct = hidden unmet demand floor. Noncitizen households "
        "are ineligible for federal SNAP but not tracked in supply counts. "
        "CDs with high noncitizen_pct have systematically underestimated gap scores.\n"
        "TRIE designation (Targeted Resource Intensive Engagement) given to CDs with "
        "food score ≥70. Currently 8 Critical CDs, all in the Bronx."
    ),
    "HPD": (
        "AGENCY LENS: Dept of Housing Preservation & Development.\n"
        "Programs: Right to Counsel (RTC), SCRIE/DRIE (rent freeze for seniors/disabled), "
        "NYCHA (177,500 units, $40B backlog), Affordable Neighborhood Cooperative Program, "
        "HomeFix small repair loans, Neighborhood Pillars (preservation lending).\n"
        "HPD Class C violations (immediately hazardous — heat failure, lead, mold, sewage) "
        "must be corrected within 24 hrs. CD 207 (Bedford Park, Bronx): 881/1k — citywide high.\n"
        "Housing → food cascade: heat failure → utility debt → food budget compression. "
        "Always connect HPD violations to food vulnerability in Bronx CDs.\n"
        "Use pipeline_stall_rate to flag CDs where new supply is blocked. "
        "Stall rate >70% = critical intervention needed.\n"
        "ULURP timeline: 12-18 months. Prioritize CDs that already have projects in pipeline.\n"
        "Federal risk: HOME elimination removes $28M/yr; CDBG -30% = $24M/yr less."
    ),
    "DOHMH": (
        "AGENCY LENS: Dept of Health & Mental Hygiene.\n"
        "Programs: Health Bucks, Fresh (grocery zoning incentives), "
        "Health Home (care coordination for high-utilizers), Bureau of Chronic Disease, "
        "Mental Health Service Corps, School Health.\n"
        "NYC life expectancy gap: 10 years (Mott Haven 75.8 yrs vs UES 86.0 yrs).\n"
        "Asthma hospitalization in South Bronx: ~96-98/10k — 4x Manhattan average.\n"
        "Type 2 diabetes correlates with SNAP enrollment at r=0.74 citywide.\n"
        "Data lag warning: SPARCS hospital discharge data has 18-month public lag. "
        "Community Health Profiles published every 3 years (next cycle 2027). "
        "Current CHS data reflects 2021-2022 conditions.\n"
        "DOHMH targeting is UHF-based (42 neighborhoods), not CD-based (59 CDs). "
        "When advising DOHMH, aggregate CD data to UHF level or note the mismatch.\n"
        "Federal risk: Title X defunding impacts 8 DOHMH clinics. CDC PHEP grant "
        "freeze would cut public health emergency capacity by ~$18M/yr."
    ),
    "DSS": (
        "AGENCY LENS: Dept of Social Services / HRA.\n"
        "Programs: SNAP administration (1.8M NYC recipients), "
        "Cash Assistance (106k households), "
        "Emergency Food Assistance (HRA pantry network, 500+ sites), "
        "Single Adult Shelter, Family Shelter, HomeBase (homelessness prevention), "
        "One-Shot Deals (emergency rental assistance).\n"
        "SNAP ABAWD expansion (March 2026): adults 18-54 now require 80 hrs/month "
        "work or training. ~150k NYC recipients potentially affected. "
        "DSS case management surge expected Q2-Q3 2026.\n"
        "Benefit cliff: avg benefit $6.10/person/day → proposed $4.80 = 21% reduction. "
        "Pantry network will absorb overflow — model utilization surge by CD.\n"
        "HRA SNAP offices by borough: Bronx (5), Brooklyn (6), Manhattan (4), "
        "Queens (4), SI (1). Access gaps in Rockaways (414), SI (501-503), Far Rockaway.\n"
        "Federal risk: $186B SNAP cut over 10 years. Medicaid block grant conversion "
        "adds $1.2B/yr state match uncertainty for Cash Assistance co-enrollees."
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


# ── FUNDING KNOWLEDGE BASE ─────────────────────────────────────────────────────
FUNDING_KB = {
    "MOFP": {
        "agency_full": "Mayor's Office of Food Policy",
        "fy26_city_budget_m": 20.9,
        "fy25_city_budget_m": 60.0,
        "fy24_city_budget_m": 25.0,
        "budget_note": "FY25 was elevated due to COVID-era emergency allocations. FY26 returned below baseline.",
        "federal_funding": {
            "EFAP": {"amount_m": 42.0, "fy": "FY25", "source": "USDA TEFAP commodity pass-through via NY State",
                     "risk": "Proposed 15% USDA cut = ~$6.3M NYC reduction"},
            "SNAP_admin": {"amount_m": 28.0, "fy": "FY25", "source": "50% federal match on state/city SNAP admin costs",
                           "risk": "Work requirement expansion adds admin burden; federal match unchanged"},
            "SNAP_Ed": {"amount_m": 4.1, "fy": "FY25", "source": "USDA SNAP-Ed formula grant",
                        "risk": "Proposed SNAP-Ed cut of 30% = ~$1.2M NYC reduction"},
        },
        "state_funding": {
            "HPNAP": {"amount_m": 12.3, "fy": "FY25", "source": "Hunger Prevention & Nutrition Assistance Program",
                      "risk": "Stable — state funded, no federal component"},
            "CACFP": {"amount_m": 8.7, "fy": "FY25", "source": "Child & Adult Care Food Program (state admin)",
                      "risk": "Federal matching — at risk if SNAP block grant converts"},
        },
        "total_federal_state_m": 95.1,
        "potential_cuts_scenario": {
            "low": {"cut_m": 8.0, "description": "EFAP -15% + SNAP-Ed -30%"},
            "mid": {"cut_m": 18.5, "description": "Above + CACFP 20% reduction"},
            "high": {"cut_m": 42.0, "description": "Full SNAP-Ed elimination + EFAP block grant conversion + HPNAP freeze"},
        }
    },
    "HPD": {
        "agency_full": "Dept of Housing Preservation & Development",
        "fy26_capital_plan_5yr_b": 3.4,
        "fy26_city_expense_budget_m": 312.0,
        "federal_funding": {
            "CDBG": {"amount_m": 80.0, "fy": "FY25", "source": "Community Development Block Grant (HUD)",
                     "risk": "Proposed 30% cut = $24M NYC reduction. Affects housing rehab + services."},
            "HOME": {"amount_m": 28.0, "fy": "FY25", "source": "HOME Investment Partnerships (HUD)",
                     "risk": "Proposed ELIMINATION. Removes $28M/yr affordable housing capital."},
            "HOPWA": {"amount_m": 9.2, "fy": "FY25", "source": "Housing for Persons with AIDS",
                      "risk": "Proposed 40% cut = $3.7M reduction. Affects 1,200+ households."},
            "ESG": {"amount_m": 6.8, "fy": "FY25", "source": "Emergency Solutions Grant (homelessness)",
                    "risk": "Proposed 50% cut = $3.4M reduction."},
        },
        "state_funding": {
            "HCR_Mitchell_Lama": {"amount_m": 45.0, "fy": "FY25", "source": "NYS HCR Mitchell-Lama program",
                                   "risk": "Stable — state appropriation"},
            "HTFC": {"amount_m": 22.0, "fy": "FY25", "source": "Housing Trust Fund Corporation",
                     "risk": "Stable — state"},
        },
        "total_federal_state_m": 191.0,
        "potential_cuts_scenario": {
            "low": {"cut_m": 24.0, "description": "CDBG -30% only"},
            "mid": {"cut_m": 52.0, "description": "CDBG -30% + HOPWA -40% + ESG -50%"},
            "high": {"cut_m": 65.8, "description": "CDBG -30% + HOME eliminated + HOPWA -40% + ESG -50%"},
        }
    },
    "DOHMH": {
        "agency_full": "Dept of Health & Mental Hygiene",
        "fy26_city_budget_b": 2.1,
        "federal_funding": {
            "Medicaid_admin": {"amount_m": 420.0, "fy": "FY25", "source": "50% federal Medicaid admin match",
                                "risk": "Block grant conversion = unknown but potentially -$200M+"},
            "CDC_PHEP": {"amount_m": 48.0, "fy": "FY25", "source": "CDC Public Health Emergency Preparedness",
                         "risk": "Proposed freeze/cut = up to $18M NYC reduction"},
            "Ryan_White": {"amount_m": 112.0, "fy": "FY25", "source": "Ryan White HIV/AIDS program",
                           "risk": "Proposed 20% cut = $22.4M reduction. Affects 30k+ NYC clients."},
            "Title_X": {"amount_m": 9.8, "fy": "FY25", "source": "Title X Family Planning",
                        "risk": "Proposed defunding. Impacts 8 DOHMH clinics, ~45k patients/yr."},
            "WIC": {"amount_m": 128.0, "fy": "FY25", "source": "WIC (Women Infants Children) federal admin",
                    "risk": "Proposed 10% WIC benefit cut = $12.8M. NYC administers ~100k certs/month."},
        },
        "state_funding": {
            "DSRIP_successor": {"amount_m": 85.0, "fy": "FY25", "source": "Medicaid 1115 waiver programs",
                                 "risk": "Waiver renewal uncertain. Potential $85M exposure."},
        },
        "total_federal_state_m": 802.8,
        "potential_cuts_scenario": {
            "low": {"cut_m": 35.0, "description": "Title X eliminated + CDC PHEP -38%"},
            "mid": {"cut_m": 80.0, "description": "Above + Ryan White -20% + WIC -10%"},
            "high": {"cut_m": 250.0, "description": "Above + Medicaid block grant conversion"},
        }
    },
    "DSS": {
        "agency_full": "Dept of Social Services / HRA",
        "fy26_city_budget_b": 11.2,
        "federal_funding": {
            "SNAP_benefits": {"amount_m": 4200.0, "fy": "FY25", "source": "100% federal SNAP benefit payments",
                               "risk": "$186B 10-yr cut. NYC annual impact: ~$420M-$840M range."},
            "TANF": {"amount_m": 556.0, "fy": "FY25", "source": "Temporary Assistance for Needy Families block grant",
                     "risk": "Proposed block grant reductions = up to $111M NYC"},
            "CCDF": {"amount_m": 142.0, "fy": "FY25", "source": "Child Care & Development Fund",
                     "risk": "Proposed 15% cut = $21.3M"},
            "FEMA_ESG": {"amount_m": 38.0, "fy": "FY25", "source": "Emergency food + shelter (FEMA/ESG)",
                          "risk": "Proposed 50% cut = $19M"},
        },
        "state_funding": {
            "Safety_Net": {"amount_m": 890.0, "fy": "FY25", "source": "NY State Safety Net Assistance",
                           "risk": "Stable — state funded"},
        },
        "total_federal_state_m": 5826.0,
        "potential_cuts_scenario": {
            "low": {"cut_m": 130.0, "description": "SNAP -5yr avg cut + CCDF -15%"},
            "mid": {"cut_m": 600.0, "description": "SNAP -15% + TANF -20% + CCDF -15% + ESG -50%"},
            "high": {"cut_m": 1500.0, "description": "SNAP block grant + TANF major cut + Medicaid work requirements"},
        }
    },
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
            "hpd_process (HPD Consolidated Plan, ULURP timeline, Where We Live NYC), "
            "dohmh_data (Community Health Profiles cycle, UHF neighborhoods, SPARCS lag), "
            "parks (Community Parks Initiative equity index, capital cycle), "
            "nyc_opportunity (Supply Gap Analysis, ACS data lag, cross-agency coordination), "
            "all (everything). Call this before making agency-specific recommendations."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "default": "all",
                    "description": "snap | cfc | housing | health | bronx | budget | ml | hpd_process | dohmh_data | parks | nyc_opportunity | all"
                }
            }
        }
    },
    {
        "name": "get_agency_funding",
        "description": (
            "Returns complete federal + state + city funding breakdown for any NYC agency, "
            "including FY25/FY26 budget amounts, each funding stream source, and "
            "3-scenario analysis of potential federal cuts (low/mid/high impact). "
            "Agencies: MOFP, HPD, DOHMH, DSS. Use this for any question about "
            "how much funding an agency gets, where it comes from, and what cuts mean."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "agency": {
                    "type": "string",
                    "description": "MOFP | HPD | DOHMH | DSS — or 'all' for cross-agency comparison"
                },
                "scenario": {
                    "type": "string",
                    "default": "all",
                    "description": "low | mid | high | all — which cut scenario to show"
                }
            },
            "required": ["agency"]
        }
    },
    {
        "name": "get_supply_gap_analysis",
        "description": (
            "Food supply vs demand gap analysis by community district. "
            "Demand estimated from Feeding America / Census food insecurity rates. "
            "Supply from SNAP enrollment rates, pantry coverage, and CFC sites. "
            "Returns gap score, TRIE designation, and prioritization ranking "
            "per the MOFP/DSS/HRA annual allocation methodology."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "n": {"type": "integer", "default": 10, "description": "Top N districts by gap score"},
                "borough": {"type": "string", "default": "", "description": "Optional borough filter"},
                "include_noncitizen_adjustment": {
                    "type": "boolean",
                    "default": True,
                    "description": "Adjust gap score upward for noncitizen_pct (hidden demand floor)"
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

    elif name == "get_eviction_stress":
        n       = inputs.get("n", 10)
        borough = inputs.get("borough", "").strip().lower()
        sort_by = inputs.get("sort_by", "eviction")
        live    = live_data or {}

        if not live:
            return {
                "error": "Live data not available",
                "hint": "Run: python3 fetch_live_data.py — takes ~5 min (NYC Open Data API)"
            }

        results = []
        for d in vuln["all"]:
            if borough and d["borough"].lower() != borough:
                continue
            fips = d["fips"]
            ld   = live.get(fips, {})
            ls   = layer_scores.get(fips, {})
            results.append({
                "name":                      d["cd_name"],
                "borough":                   d["borough"],
                "fips":                      fips,
                "risk_tier":                 d["risk_tier"],
                "food_score":                d["vulnerability_score"],
                "housing_score":             ls.get("housing", 50),
                "eviction_filings_12mo":     ld.get("eviction_filings_12mo", 0),
                "eviction_rate_per_1k_hh":   ld.get("eviction_rate_per_1k", 0),
                "food_complaints_12mo":      ld.get("food_complaints_12mo", 0),
                "food_complaint_rate_per_1k": ld.get("food_complaint_rate_per_1k", 0),
                "dob_permits_12mo":          ld.get("dob_permits_12mo", 0),
                "dob_permit_rate_per_1k":    ld.get("dob_permit_rate_per_1k", 0),
            })

        sort_key = {
            "eviction":        "eviction_rate_per_1k_hh",
            "food_complaints": "food_complaint_rate_per_1k",
            "dob_permits":     "dob_permit_rate_per_1k",
        }.get(sort_by, "eviction_rate_per_1k_hh")
        results.sort(key=lambda x: x[sort_key], reverse=True)
        return {
            "sort_by": sort_by, "borough_filter": borough or "all boroughs",
            "window": "rolling 12 months",
            "source": "NYC Open Data 6z8x-wfk4 (evictions), erm2-nwe9 (311)",
            "top": results[:n],
        }

    elif name == "get_policy_context":
        topic = inputs.get("topic", "all").strip().lower()

        POLICY_KB = {
            "snap": {
                "title": "SNAP Federal Policy — 2025-2026 Changes",
                "facts": [
                    "Congress passed $186B in SNAP cuts over 10 years (FY2026 reconciliation).",
                    "March 2026: ABAWD work requirements expanded — now apply to adults 18-54 (was 18-49). "
                    "Must work/train 80 hrs/month. NY State has NOT opted into stricter requirements as of April 2026.",
                    "Benefit cliff: avg NYC SNAP = $6.10/person/day. Proposed cut to ~$4.80 (-21%).",
                    "NYC: ~1.8M recipients. ~150k adults 18-54 potentially affected by ABAWD expansion.",
                    "NYC DSS: ~23% seniors, ~31% children under 18 among recipients.",
                    "Non-citizen households ineligible for federal SNAP — estimate 180k-220k NYC households invisible to supply counts.",
                    "Source: CBPP FY2026 reconciliation analysis; NYC DSS SNAP Dashboard April 2026.",
                ],
            },
            "cfc": {
                "title": "Community Fridge Collaborative (CFC) — NYC Pantry Network",
                "facts": [
                    "~50 community fridges citywide. Top CDs: Mott Haven, Hunts Point, Brownsville, East Harlem, Crown Heights.",
                    "CFC distributed 2.1M lbs of food in 2024. 40% from NYC food rescue partners.",
                    "Funding: $4.2M NYC Council FY2025; $2.8M private foundations. Gap: ~$3M/year.",
                    "CFC operates without eligibility requirements — no ID, no income verification.",
                ],
                "gaps": [
                    "Queens: only 6 sites for 2.3M residents. Jackson Heights (CD3), Jamaica (CD12) underserved.",
                    "Staten Island: 0 CFC sites. Highest need in St. George (CD1) and Stapleton.",
                    "Only 12 of 50 fridges offer 24hr access.",
                ],
            },
            "housing": {
                "title": "NYC Housing Stability & Displacement",
                "facts": [
                    "Eviction filings returned to pre-pandemic levels (~200k citywide annually, 2024).",
                    "Right to Counsel (Local Law 136-2017): free legal rep expanded citywide 2022.",
                    "NYCHA: 177,500 units, ~350k residents, 7-10yr avg wait, $40B capital backlog.",
                    "Good Cause Eviction (Local Law 97, 2023): most renters have just-cause protections.",
                    "HPD Class C violations: 24-hr correction required. CD 207 Bedford Park: 881/1k = citywide high.",
                    "~20 CLTs controlling ~2,000 permanently affordable units. BronxWorks, IMPACCT Brooklyn, NHS Jamaica active.",
                ],
            },
            "health": {
                "title": "NYC Health Burden & Social Determinants",
                "facts": [
                    "Life expectancy gap: UES (86.0 yrs) vs Mott Haven (75.8 yrs) = 10-year gap.",
                    "Asthma hospitalization South Bronx: ~96-98/10k — 4x Manhattan average.",
                    "Premature mortality: Bronx highest of 5 boroughs (DOHMH Community Health Profiles 2018).",
                    "Heat Vulnerability Index 4-5 (highest): South Bronx CDs 1-4.",
                    "Depression prevalence Bronx CD 1-4: 2x citywide avg (CHS 2021).",
                    "R²=0.74 between food insecurity and asthma hospitalization rate (DOHMH 2022).",
                    "WIC: NYC ~100k certs/month. BX CDs 1-6 = 28% of citywide certs.",
                ],
            },
            "bronx": {
                "title": "Bronx-Specific Disparity Context",
                "facts": [
                    "Highest poverty rate, US county >1M residents: 29.6% (ACS 2021).",
                    "South Bronx CDs 201-206 median HH income: $22k-$26k vs NYC median $70k.",
                    "Hunts Point (CD 202): largest US food distribution hub — 42% residents face food insecurity.",
                    "Bronx food insecurity rate: ~28% (Feeding America 2023) vs NYC avg ~16%.",
                    "6 of 10 shortest life expectancies, 45% of highest HPD violation CDs, 38% of highest asthma CDs.",
                    "3 Bronx FQHCs facing closure as of April 2026. BronxWorks, WHEDco, Banana Kelly active.",
                ],
            },
            "budget": {
                "title": "NYC Budget Context — FY2026 Food & Housing",
                "facts": [
                    "NYC FY2026 Executive Budget: $114.5B total. Human services: $18.3B.",
                    "MOFP FY2026: $20.9M city funds (-65% from FY25 $60M). Baseline was $25M.",
                    "EFAP federal pass-through: ~$42M FY25. HPNAP state: $12.3M.",
                    "HRA Emergency Food Assistance: $52M FY26. Meals on Wheels: $38M.",
                    "FoodWorks NYC 2023-2028: $400M 5-year commitment.",
                    "HPD capital FY2026-2030: $3.4B. Affordable preservation: $1.2B.",
                    "NYC 15-year housing plan (City of Yes): 82,000 new units target.",
                    "DOE school meals: 700k+/day, universal free = $600M/yr.",
                ],
            },
            "ml": {
                "title": "ML & Predictive Vulnerability — Research References",
                "papers": [
                    {"title": "Predicting Food Insecurity from Social Determinants using Gradient Boosted Trees",
                     "source": "American Journal of Public Health, 2022",
                     "finding": "XGBoost R²=0.91 using 14 SDoH features. Features: unemployment, poverty, child poverty, disability, housing cost burden, racial composition, SNAP take-up."},
                    {"title": "Deep Learning for Neighborhood Vulnerability Forecasting",
                     "source": "KDD 2021",
                     "finding": "LSTM on 311 + evictions + permits predicts 18-month displacement risk at 82% AUC. NYC has all required inputs."},
                    {"title": "Using Administrative Data to Identify Housing Instability",
                     "source": "NYU Furman Center 2023",
                     "finding": "Eviction filings + HPD violations predict 12-month displacement at 79% precision."},
                ],
            },
            "hpd_process": {
                "title": "HPD Investment Process — Consolidated Plan + ULURP",
                "facts": [
                    "HUD requires a 5-year Consolidated Plan. Annual Action Plans identify priority neighborhoods.",
                    "Investment driven by: ULURP review, community board input, displacement risk index, "
                    "Where We Live NYC equity framework (race-conscious spatial equity analysis).",
                    "ULURP process: 12-18 months from application to approval. "
                    "Community board has 60 days; Borough President 30 days; City Planning Commission 60 days; City Council 50 days.",
                    "Capital planning cycle: 10 years. Operating budgets: annual.",
                    "Where We Live NYC: geospatial equity tool maps historical disinvestment, segregation, "
                    "and current displacement risk. High-priority CDs: Bronx 201-206, BK 305/316, QN 403/412.",
                    "ULURP tip: CDs with community board endorsement + existing HPD pipeline move 40% faster.",
                    "Federal CDBG national objectives require: LMI benefit (51%+ low-mod income residents), "
                    "slum/blight elimination, or urgent need. Most CDs 201-206 qualify on LMI and slum/blight.",
                ],
            },
            "dohmh_data": {
                "title": "DOHMH Data Cycles, UHF Geography, SPARCS Lag",
                "facts": [
                    "Community Health Profiles published every 3 years for 42 UHF (United Hospital Fund) neighborhoods.",
                    "UHF ≠ community districts. 42 UHF neighborhoods aggregate to cover all 59 CDs but at different boundaries.",
                    "When advising DOHMH, note: CD-level data must be aggregated to UHF level for program alignment.",
                    "SPARCS (Statewide Planning and Research Cooperative System) hospital discharge data has 18-month public lag. "
                    "Current public SPARCS reflects 2023 discharges.",
                    "Community Health Survey (CHS): annual survey, ~8,000 NYC adults. Results published 6-12 months after collection.",
                    "Budget set annually but program geography rarely changes between 3-year cycles. "
                    "Advocacy window: the year before a new profile cycle launches (next: ~2026-2027).",
                    "Mayor's Public Health Agenda (2024): targets chronic disease, behavioral health, environmental health.",
                    "DOHMH targeting note: programs can be deployed to CD level but are funded and reported at UHF level.",
                ],
            },
            "parks": {
                "title": "NYC Parks — Community Parks Initiative Equity Index",
                "facts": [
                    "Community Parks Initiative (CPI) uses equity index: park acreage per capita + poverty rate + population density.",
                    "Capital plans: 10-year cycle. Operating budgets: annual.",
                    "Equity index scores NOT updated between planning cycles — use The Grid's economic stress "
                    "and health burden layers as proxies for updated neighborhood need.",
                    "Federal LWCF (Land & Water Conservation Fund): ~$15M/yr NYC; proposed freeze = full cut.",
                    "NYS Environmental Protection Fund (EPF): $400M/yr statewide; NYC gets ~18% (~$72M/yr).",
                    "Parks maintenance gap: NYC parks receive ~$1.20/resident/day vs national benchmark $4-6.",
                    "Lowest park access CDs: Bronx CD 201/202 (0.7 acres/1k residents), BK CD 303/316.",
                    "CPI originally targeted 35 parks in underserved neighborhoods. Capital investment ~$130M (2014-2019).",
                    "Operating budget equity gap: wealthy CDs with active conservancies outspend city-funded CDs 3:1.",
                ],
            },
            "nyc_opportunity": {
                "title": "NYC Opportunity — Cross-Agency Coordination & Data",
                "facts": [
                    "NYC Opportunity produces: NYC Poverty Measure (more comprehensive than federal SPM) "
                    "and the annual Food Supply Gap Analysis.",
                    "Coordinates cross-agency equity initiatives including Where We Live NYC and OneNYC.",
                    "Uses ACS 5-year estimates: neighborhood-level poverty data is 2-3 years old when published "
                    "and 4-5 years old by end of a planning cycle.",
                    "The Grid partially addresses ACS lag by layering rolling live data (311, evictions, DOB permits) "
                    "onto ACS base indicators.",
                    "Food Supply Gap Analysis methodology: Feeding America demand estimates (Census-based, 12-18 months old) "
                    "combined with FeedNYC pantry tracker supply. Gap = demand - supply, expressed as % of food insecure population.",
                    "TRIE (Targeted Resource Intensive Engagement) designation: CDs with food gap score in top quintile "
                    "get priority in MOFP/DSS/HRA allocation.",
                    "NYC Poverty Measure 2023: overall poverty rate 18.3% (higher than federal 14.6% due to "
                    "inclusion of housing costs, SNAP, work expenses, tax credits).",
                    "Key report: 'The State of Food Insecurity in NYC' published annually by CUNY Urban Food Policy Institute.",
                ],
            },
        }

        if topic == "all":
            return {"topics": list(POLICY_KB.keys()), "data": POLICY_KB}
        if topic not in POLICY_KB:
            return {"error": f"Topic '{topic}' not found", "available": list(POLICY_KB.keys())}
        return {"topic": topic, "data": POLICY_KB[topic]}

    elif name == "get_agency_funding":
        agency   = inputs.get("agency", "").upper().strip()
        scenario = inputs.get("scenario", "all").lower().strip()

        if agency == "ALL":
            results = {}
            for ag, data in FUNDING_KB.items():
                results[ag] = {
                    "agency_full": data["agency_full"],
                    "fy26_total_city_budget": (
                        data.get("fy26_city_budget_m") or
                        data.get("fy26_city_budget_b", 0) * 1000 or
                        data.get("fy26_capital_plan_5yr_b", 0) * 1000
                    ),
                    "total_federal_state_m": data["total_federal_state_m"],
                    "cut_scenarios": data["potential_cuts_scenario"],
                }
            return {"cross_agency_funding": results,
                    "note": "All dollar amounts in millions (M) unless noted as billions (B)"}

        if agency not in FUNDING_KB:
            return {"error": f"Agency '{agency}' not in funding database",
                    "available": list(FUNDING_KB.keys())}

        data = FUNDING_KB[agency]
        result = dict(data)
        if scenario != "all":
            result["highlighted_scenario"] = {
                "scenario": scenario,
                "data": data["potential_cuts_scenario"].get(scenario, "Scenario not found")
            }
        result["note"] = "Dollar amounts in millions (M). Budget figures are FY25 actuals unless marked FY26 projected."
        return result

    elif name == "get_supply_gap_analysis":
        n           = inputs.get("n", 10)
        borough     = inputs.get("borough", "").strip().lower()
        nc_adjust   = inputs.get("include_noncitizen_adjustment", True)

        results = []
        for d in vuln["all"]:
            if borough and d["borough"].lower() != borough:
                continue
            fips = d["fips"]
            ls   = layer_scores.get(fips, {})
            ind  = d.get("indicators", {})

            snap_pct   = ind.get("snap_household_pct", 0)
            poverty    = ind.get("child_poverty_pct", 0)
            unemp      = ind.get("unemployment_pct", 0)
            noncitizen = ind.get("noncitizen_pct", 0)

            # Demand proxy: Feeding America methodology adapts Census food insecurity
            # Food insecurity ~ 1.4x * SNAP enrollment rate (adjusted for non-SNAP eligible)
            demand_score = round(snap_pct * 1.4, 1)
            if nc_adjust:
                # Noncitizen adjustment: each 1% noncitizen adds 0.3% hidden demand
                demand_score = round(demand_score + noncitizen * 0.3, 1)

            # Supply proxy: SNAP coverage + pantry density indicator
            supply_score = round(snap_pct * 0.85, 1)  # SNAP covers ~85% of eligible households

            gap_score = round(demand_score - supply_score, 1)
            adjusted_gap = round(gap_score + (unemp * 0.2), 1)  # unemployment amplifier

            food_score = d["vulnerability_score"]
            trie = food_score >= 70

            results.append({
                "name":             d["cd_name"],
                "borough":          d["borough"],
                "fips":             fips,
                "risk_tier":        d["risk_tier"],
                "food_vulnerability_score": food_score,
                "snap_enrollment_pct":      snap_pct,
                "child_poverty_pct":        poverty,
                "unemployment_pct":         unemp,
                "noncitizen_pct":           noncitizen,
                "demand_score":             demand_score,
                "supply_score":             supply_score,
                "gap_score":                gap_score,
                "adjusted_gap_score":       adjusted_gap,
                "trie_designated":          trie,
                "priority_notes": (
                    "TRIE eligible — top priority for MOFP/DSS allocation" if trie
                    else ("High gap — consider for expanded pantry coverage" if adjusted_gap > 10
                    else "Monitor")
                ),
            })

        results.sort(key=lambda x: x["adjusted_gap_score"], reverse=True)
        citywide_gap = round(sum(r["gap_score"] for r in results) / len(results), 1) if results else 0
        trie_count   = sum(1 for r in results if r["trie_designated"])

        return {
            "methodology": (
                "Demand estimated via Feeding America Census-based methodology (12-18 month lag). "
                "Supply proxy: SNAP enrollment rate (covers ~85% of eligible HH). "
                "Gap = demand - supply. Noncitizen adjustment adds 0.3pt per 1% noncitizen pop "
                "to account for federal SNAP ineligibility."
            ),
            "budget_context": (
                "MOFP/DSS/HRA FY26 discretionary: $20.9M city funds (down from $60M FY25). "
                "Federal EFAP: ~$42M pass-through. Allocate TRIE-designated CDs first."
            ),
            "citywide_avg_gap": citywide_gap,
            "trie_eligible_count": trie_count,
            "top_gap_districts": results[:n],
            "noncitizen_adjustment_applied": nc_adjust,
        }

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

    live_data = _load_live_data()

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    current_messages = list(messages)

    # Include web_search as a built-in Anthropic tool alongside custom tools
    all_tools = TOOLS + [{"type": "web_search_20250305", "name": "web_search"}]

    while True:
        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=2000,
            system=system,
            tools=all_tools,
            messages=current_messages,
        )

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = execute_tool(block.name, block.input, vuln, layer_scores, live_data)
                    tool_results.append({
                        "type":        "tool_result",
                        "tool_use_id": block.id,
                        "content":     json.dumps(result),
                    })
                # web_search results are handled natively by the API — no manual dispatch needed

            current_messages.append({"role": "assistant", "content": response.content})
            if tool_results:
                current_messages.append({"role": "user", "content": tool_results})

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
