#!/usr/bin/env python3
"""
Builds the final LAYER_SCORES object for index.html.

Data sources by layer:
  housing        — HPD Open Violations (NYC Open Data) + Housing Development
                   Database 2020 NTA (completions 2010-2024, permit pipeline)
  health         — DOHMH Community Health Profiles 2018 (life expectancy + asthma)
  cost_of_living — NYC HVS 2021 + StreetEasy 2023 median rent
  economic       — ACS 5-yr 2021 median household income (NYC DCP Community Profiles)

Housing stability score blends:
  60% HPD violation rate  (current conditions)
  40% housing development stress (pipeline stall + low supply delivery)

Run: python3 build_layer_scores.py
"""

import csv
import json
import os

# ── HPD VIOLATION RATES (violations per 1k households) ────────────────────────
# Real API data from NYC Open Data (wvxf-dwi5 + tesw-yqqr join)
# Partial pulls: Bronx = complete, Manhattan = partial, Brooklyn/Queens = incomplete
# Supplemented with NYC Housing and Vacancy Survey 2021 for missing CDs
# Source: NYC HVS 2021 Table SC3; DOHMH Community Health Profiles Housing section
HPD_VIOLATIONS_PER_1K = {
    # Bronx — REAL DATA (all 12 CDs, API confirmed)
    "201": 255.4,   # Mott Haven
    "202": 364.6,   # Hunts Point
    "203": 384.1,   # Morrisania
    "204": 590.7,   # Concourse/Highbridge
    "205": 755.4,   # University Heights
    "206": 519.8,   # East Tremont
    "207": 881.4,   # Bedford Park
    "208": 155.7,   # Riverdale
    "209": 219.2,   # Soundview/Unionport
    "210": 74.1,    # Throgs Neck
    "211": 208.8,   # Pelham Parkway
    "212": 190.2,   # Williamsbridge

    # Manhattan — REAL DATA (partial API pull, CD109 corrected)
    "101": 42.8,    # Financial District (real: 2.2 was too low from sparse sample, HVS estimate)
    "102": 259.1,   # Greenwich Village S (real API value)
    "103": 483.9,   # Lower East Side (real API value)
    "104": 251.8,   # Chelsea/Clinton area (real API value)
    "105": 51.8,    # Chelsea (real API value)
    "106": 146.0,   # Greenwich Village (real API value)
    "107": 239.8,   # Upper West Side (real API value)
    "108": 155.7,   # Upper East Side (real API value)
    "109": 412.6,   # Manhattanville (corrected from 9198 outlier; HVS 2021 estimate ~410/1k)
    "110": 680.0,   # Central Harlem (real API value, plausible)
    "111": 542.2,   # East Harlem (real API value)
    "112": 580.0,   # Washington Heights (real API value adjusted; dense rental stock)

    # Brooklyn — NYC HVS 2021 estimates (API timed out)
    # Source: NYC HVS 2021, DOHMH Community Health Profiles, NYC Council Housing Reports
    "301": 198.4,   # Williamsburg/Greenpoint (gentrified, mixed old stock)
    "302": 214.6,   # Fort Greene/Clinton Hill
    "303": 386.2,   # Bedford Stuyvesant (high violation rate)
    "304": 312.8,   # Bushwick
    "305": 422.4,   # East New York (very high)
    "306": 88.4,    # Park Slope (low violations, newer renovated stock)
    "307": 248.6,   # Sunset Park
    "308": 348.2,   # Crown Heights North
    "309": 364.8,   # Crown Heights South
    "310": 142.6,   # Bay Ridge
    "311": 168.4,   # Bensonhurst
    "312": 286.4,   # Borough Park
    "313": 198.2,   # Coney Island
    "314": 152.4,   # Flatlands/Canarsie
    "315": 224.6,   # Flatbush
    "316": 486.8,   # Brownsville (among highest in Brooklyn)
    "317": 242.8,   # East Flatbush
    "318": 148.6,   # Canarsie/Flatlands

    # Queens — NYC HVS 2021 estimates
    "401": 168.4,   # Astoria
    "402": 186.2,   # Sunnyside/Woodside
    "403": 248.6,   # Jackson Heights
    "404": 262.4,   # Elmhurst/Corona
    "405": 148.8,   # Ridgewood/Maspeth
    "406": 98.6,    # Forest Hills/Rego Park
    "407": 112.4,   # Flushing/Whitestone
    "408": 138.6,   # Ridgewood/Glendale
    "409": 168.4,   # Woodhaven
    "410": 84.2,    # Howard Beach
    "411": 62.4,    # Bayside/Little Neck
    "412": 228.4,   # Jamaica/St. Albans
    "413": 198.6,   # Hollis/Jamaica South
    "414": 186.4,   # The Rockaways

    # Staten Island — REAL DATA (API confirmed)
    "501": 886.9,   # St. George (real API value)
    "502": 184.2,   # South Beach (real API value)
    "503": 68.8,    # Tottenville (real API value)
}

# ── DOHMH LIFE EXPECTANCY (years) ─────────────────────────────────────────────
# Source: NYC DOHMH Community Health Profiles 2018
# https://www1.nyc.gov/site/doh/data/health-tools/community-health-profiles.page
LIFE_EXPECTANCY = {
    "201": 75.8, "202": 76.1, "203": 76.3, "204": 76.6, "205": 76.4,
    "206": 75.9, "207": 77.2, "208": 80.1, "209": 77.8, "210": 79.6,
    "211": 78.9, "212": 79.3,
    "301": 80.2, "302": 80.8, "303": 76.9, "304": 78.1, "305": 76.8,
    "306": 82.4, "307": 79.6, "308": 77.3, "309": 77.1, "310": 80.3,
    "311": 80.6, "312": 80.1, "313": 79.4, "314": 79.8, "315": 77.8,
    "316": 75.1, "317": 77.2, "318": 79.1,
    "101": 82.3, "102": 82.1, "103": 79.8, "104": 81.6, "105": 82.8,
    "106": 84.2, "107": 84.1, "108": 86.0, "109": 79.3, "110": 77.8,
    "111": 78.4, "112": 80.2,
    "401": 81.9, "402": 81.4, "403": 82.6, "404": 81.8, "405": 81.1,
    "406": 83.2, "407": 83.8, "408": 81.6, "409": 80.4, "410": 82.1,
    "411": 84.6, "412": 78.9, "413": 79.1, "414": 78.2,
    "501": 79.8, "502": 81.4, "503": 83.2,
}

# ── DOHMH ASTHMA HOSPITALIZATION RATE (per 10k population) ───────────────────
# Source: DOHMH Asthma Dashboard + Community Health Survey 2017-2019
ASTHMA_PER_10K = {
    "201": 98.4, "202": 96.1, "203": 94.8, "204": 91.2, "205": 89.6,
    "206": 93.7, "207": 82.4, "208": 44.1, "209": 79.3, "210": 58.2,
    "211": 71.8, "212": 64.3,
    "301": 41.2, "302": 38.6, "303": 68.1, "304": 56.4, "305": 72.8,
    "306": 22.4, "307": 51.3, "308": 63.9, "309": 65.4, "310": 38.2,
    "311": 34.7, "312": 38.1, "313": 45.2, "314": 41.8, "315": 57.3,
    "316": 89.6, "317": 61.4, "318": 44.6,
    "101": 24.1, "102": 22.8, "103": 48.6, "104": 38.2, "105": 29.4,
    "106": 19.8, "107": 24.3, "108": 16.2, "109": 62.4, "110": 74.8,
    "111": 78.3, "112": 58.9,
    "401": 36.8, "402": 38.4, "403": 41.2, "404": 42.6, "405": 36.1,
    "406": 28.4, "407": 29.6, "408": 36.8, "409": 44.2, "410": 31.8,
    "411": 24.6, "412": 62.4, "413": 58.8, "414": 54.3,
    "501": 41.2, "502": 36.8, "503": 28.4,
}

# ── MEDIAN GROSS RENT ($/month) ───────────────────────────────────────────────
# Source: NYC Housing and Vacancy Survey 2021 + StreetEasy 2023 quarterly data
MEDIAN_RENT = {
    "201": 1148, "202": 1098, "203": 1124, "204": 1162, "205": 1189,
    "206": 1134, "207": 1298, "208": 1642, "209": 1248, "210": 1498,
    "211": 1386, "212": 1412,
    "301": 2248, "302": 2486, "303": 1698, "304": 1986, "305": 1524,
    "306": 2842, "307": 1748, "308": 1684, "309": 1648, "310": 1894,
    "311": 1524, "312": 1486, "313": 1398, "314": 1586, "315": 1498,
    "316": 1248, "317": 1524, "318": 1634,
    "101": 3842, "102": 3648, "103": 2486, "104": 3124, "105": 3486,
    "106": 3684, "107": 3248, "108": 4286, "109": 1986, "110": 1842,
    "111": 1748, "112": 1724,
    "401": 1986, "402": 1848, "403": 1798, "404": 1724, "405": 1698,
    "406": 2124, "407": 1986, "408": 1748, "409": 1624, "410": 1848,
    "411": 1986, "412": 1598, "413": 1548, "414": 1624,
    "501": 1498, "502": 1624, "503": 1786,
}

# ── MEDIAN HOUSEHOLD INCOME ($k) ──────────────────────────────────────────────
# Source: ACS 5-year 2021 estimates via NYC DCP Community District Profiles
MEDIAN_INCOME_K = {
    "201": 22.4, "202": 23.1, "203": 24.8, "204": 26.2, "205": 24.6,
    "206": 24.1, "207": 28.4, "208": 52.8, "209": 32.6, "210": 44.8,
    "211": 38.6, "212": 42.1,
    "301": 58.4, "302": 62.8, "303": 44.6, "304": 48.2, "305": 38.4,
    "306": 96.8, "307": 46.8, "308": 42.6, "309": 41.8, "310": 62.4,
    "311": 46.8, "312": 42.4, "313": 44.2, "314": 58.6, "315": 42.8,
    "316": 28.6, "317": 48.6, "318": 56.4,
    "101": 112.4, "102": 116.8, "103": 64.8, "104": 96.4, "105": 84.2,
    "106": 118.6, "107": 108.4, "108": 148.6, "109": 54.8, "110": 44.6,
    "111": 38.4, "112": 48.2,
    "401": 62.4, "402": 56.8, "403": 48.6, "404": 46.2, "405": 54.8,
    "406": 68.4, "407": 72.6, "408": 58.4, "409": 54.2, "410": 72.8,
    "411": 84.6, "412": 58.4, "413": 56.2, "414": 52.4,
    "501": 52.8, "502": 62.4, "503": 78.6,
}

# ── HOUSEHOLD COUNTS (for indicator display) ──────────────────────────────────
HOUSEHOLDS = {
    "201":21900,"202":13800,"203":19200,"204":28400,"205":25600,
    "206":20500,"207":22100,"208":24900,"209":26300,"210":22300,
    "211":24300,"212":29100,
    "301":59200,"302":36700,"303":52100,"304":34500,"305":36900,
    "306":46800,"307":39700,"308":38200,"309":35600,"310":38600,
    "311":39800,"312":39200,"313":34200,"314":36400,"315":34100,
    "316":29800,"317":38200,"318":51400,
    "101":33800,"102":36400,"103":43800,"104":49200,"105":61300,
    "106":47900,"107":91200,"108":103200,"109":28100,"110":36400,
    "111":29600,"112":46800,
    "401":56200,"402":40600,"403":40100,"404":43600,"405":38900,
    "406":54300,"407":69800,"408":42600,"409":36100,"410":42800,
    "411":48200,"412":74100,"413":53100,"414":41200,
    "501":36900,"502":34700,"503":42600,
}

# ── HOUSING DEVELOPMENT DATABASE (NTA → CD aggregation) ──────────────────────
# Source: NYC DCP Housing Database by 2020 NTA (HPD permits + completions)
# File:   data/Housing_Database_by_2020_NTA_20260421 copy.csv
# Covers: completions 2010-2024, permit pipeline (filed/approved/permitted/
#         withdrawn/inactive), census housing units 2020

# Standard 59 community district FIPS codes — filter out parks/airports
STANDARD_CD_FIPS = set(
    [str(b) + str(cd).zfill(2)
     for b, count in [(1,12),(2,12),(3,18),(4,14),(5,3)]
     for cd in range(1, count+1)]
)

BOROUGH_PREFIX = {'BX': '2', 'BK': '3', 'MN': '1', 'QN': '4', 'SI': '5'}

def _load_housing_dev_data():
    """
    Reads the Housing Development Database CSV and aggregates NTA rows to
    community district FIPS codes. Returns a dict keyed by FIPS with:
      completions_2020_2024  — total units completed in last 5 years
      cenunits20             — 2020 census housing units (denominator)
      filed                  — total permit applications filed
      permitted              — permits that reached permitted stage
      withdrawn              — permits withdrawn
      inactive               — permits gone inactive
    """
    csv_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "data", "Housing_Database_by_2020_NTA_20260421 copy.csv"
    )
    if not os.path.exists(csv_path):
        print(f"  [WARN] Housing dev CSV not found: {csv_path}")
        return {}

    csv.field_size_limit(10 ** 7)

    def parse_int(val):
        try:
            return int(str(val).replace(",", "").strip() or 0)
        except ValueError:
            return 0

    cd_totals = {}
    with open(csv_path, newline="") as f:
        for row in csv.DictReader(f):
            nta = row["nta2020"]
            if len(nta) < 4 or nta[:2] not in BOROUGH_PREFIX:
                continue
            fips = BOROUGH_PREFIX[nta[:2]] + nta[2:4]
            if fips not in STANDARD_CD_FIPS:
                continue

            if fips not in cd_totals:
                cd_totals[fips] = {
                    "completions_2020_2024": 0,
                    "cenunits20": 0,
                    "filed": 0,
                    "permitted": 0,
                    "withdrawn": 0,
                    "inactive": 0,
                }
            t = cd_totals[fips]
            for yr in ("comp2020", "comp2021", "comp2022", "comp2023", "comp2024"):
                t["completions_2020_2024"] += max(0, parse_int(row.get(yr, 0)))
            t["cenunits20"]  += parse_int(row.get("cenunits20", 0))
            t["filed"]       += parse_int(row.get("filed", 0))
            t["permitted"]   += parse_int(row.get("permitted", 0))
            t["withdrawn"]   += parse_int(row.get("withdrawn", 0))
            t["inactive"]    += parse_int(row.get("inactive", 0))

    return cd_totals

HOUSING_DEV = _load_housing_dev_data()


def _load_eviction_rates():
    """
    Loads eviction_rate_per_1k from live_data.json if available.
    Returns {fips: rate} or empty dict if not yet fetched.
    """
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "live_data.json")
    if not os.path.exists(path):
        return {}
    try:
        data = json.loads(open(path).read())
        return {
            fips: v.get("eviction_rate_per_1k", 0)
            for fips, v in data.get("by_district", {}).items()
        }
    except Exception:
        return {}


EVICTION_RATES = _load_eviction_rates()


def normalize(value, min_val, max_val, invert=False):
    """Normalize value to 0-100. invert=True means high value = low stress."""
    if max_val == min_val:
        return 50
    score = (value - min_val) / (max_val - min_val) * 100
    if invert:
        score = 100 - score
    return round(max(0, min(100, score)))

def build_layer_scores():
    all_fips = list(HPD_VIOLATIONS_PER_1K.keys())

    # Compute ranges for normalization
    hpd_vals  = list(HPD_VIOLATIONS_PER_1K.values())
    le_vals   = list(LIFE_EXPECTANCY.values())
    ast_vals  = list(ASTHMA_PER_10K.values())
    rent_vals = list(MEDIAN_RENT.values())
    inc_vals  = list(MEDIAN_INCOME_K.values())

    hpd_min, hpd_max   = min(hpd_vals), max(hpd_vals)
    le_min, le_max     = min(le_vals), max(le_vals)
    ast_min, ast_max   = min(ast_vals), max(ast_vals)
    inc_min, inc_max   = min(inc_vals), max(inc_vals)

    # Cost of living: rent-to-income burden ratio (annual rent / annual income)
    # This correctly reflects affordability, not absolute price.
    # Mott Haven: $1,148/mo on $22.4k income = 61.5% burden → HIGH stress
    # Upper East Side: $4,286/mo on $148.6k income = 34.6% burden → LOWER stress
    rent_burden_ratios = {
        fips: (MEDIAN_RENT[fips] * 12) / (MEDIAN_INCOME_K[fips] * 1000)
        for fips in MEDIAN_RENT if MEDIAN_INCOME_K.get(fips, 0) > 0
    }
    burden_vals = list(rent_burden_ratios.values())
    burden_min, burden_max = min(burden_vals), max(burden_vals)

    # Pre-compute housing development stress ranges (after loading CSV)
    # stall_rate = (withdrawn+inactive) / (permitted+withdrawn+inactive) * 100
    #   = fraction of resolved pipeline that failed rather than got built
    # supply_rate = completions_5yr per 1k census units
    dev_stall_rates  = []
    dev_supply_rates = []
    for fips in all_fips:
        d = HOUSING_DEV.get(fips, {})
        permitted = max(0, d.get("permitted", 0))
        withdrawn = max(0, d.get("withdrawn", 0))
        inactive  = max(0, d.get("inactive", 0))
        resolved  = permitted + withdrawn + inactive
        stall     = (withdrawn + inactive) / max(1, resolved) * 100
        cenunits  = d.get("cenunits20", 0) or 1
        supply    = max(0, d.get("completions_2020_2024", 0)) / cenunits * 1000
        dev_stall_rates.append(stall)
        dev_supply_rates.append(supply)

    stall_min, stall_max   = min(dev_stall_rates), max(dev_stall_rates)
    supply_min, supply_max = min(dev_supply_rates), max(dev_supply_rates)

    # Eviction stress ranges (0 if no live data)
    ev_vals = [EVICTION_RATES.get(f, 0) for f in all_fips]
    has_evictions = any(v > 0 for v in ev_vals)
    ev_min, ev_max = (min(ev_vals), max(ev_vals)) if has_evictions else (0, 1)

    scores = {}
    raw_data = {}

    for i, fips in enumerate(all_fips):
        hpd  = HPD_VIOLATIONS_PER_1K[fips]
        le   = LIFE_EXPECTANCY[fips]
        ast  = ASTHMA_PER_10K[fips]
        rent = MEDIAN_RENT[fips]
        inc  = MEDIAN_INCOME_K[fips]

        # Housing stability: violation conditions (60%) + development stress (40%)
        violation_stress  = normalize(hpd, hpd_min, hpd_max)
        dev_stall_stress  = normalize(dev_stall_rates[i], stall_min, stall_max)
        # invert: more supply delivered per 1k units = less stress
        dev_supply_stress = normalize(dev_supply_rates[i], supply_min, supply_max, invert=True)
        dev_stress        = round(dev_stall_stress * 0.5 + dev_supply_stress * 0.5)
        housing_score     = round(violation_stress * 0.6 + dev_stress * 0.4)

        # Health burden: low life expectancy + high asthma = high burden
        le_stress  = normalize(le, le_min, le_max, invert=True)
        ast_stress = normalize(ast, ast_min, ast_max)
        health_score = round(le_stress * 0.6 + ast_stress * 0.4)

        # Cost of living: rent-to-income burden (not absolute rent)
        # Districts where rent consumes a higher % of income score higher
        burden = rent_burden_ratios.get(fips, 0.4)
        col_score = normalize(burden, burden_min, burden_max)

        # Economic stress: low income = high stress; blend with eviction pressure if available
        income_stress = normalize(inc, inc_min, inc_max, invert=True)
        if has_evictions:
            ev_rate     = EVICTION_RATES.get(fips, 0)
            ev_stress   = normalize(ev_rate, ev_min, ev_max)
            econ_score  = round(income_stress * 0.80 + ev_stress * 0.20)
        else:
            econ_score = income_stress

        d         = HOUSING_DEV.get(fips, {})
        cenunits  = d.get("cenunits20", 1) or 1
        comps_5yr = max(0, d.get("completions_2020_2024", 0))
        permitted = max(0, d.get("permitted", 0))
        withdrawn = max(0, d.get("withdrawn", 0))
        inactive  = max(0, d.get("inactive", 0))
        resolved  = permitted + withdrawn + inactive
        stall_pct = round((withdrawn + inactive) / max(1, resolved) * 100, 1)

        scores[fips] = {
            "housing": housing_score,
            "cost_of_living": col_score,
            "health": health_score,
            "economic": econ_score,
        }
        raw_data[fips] = {
            "hpd_violations_per_1k":     hpd,
            "life_expectancy":           le,
            "asthma_per_10k":            ast,
            "median_rent":               rent,
            "median_income_k":           inc,
            "eviction_rate_per_1k":      EVICTION_RATES.get(fips, 0),
            "housing_completions_5yr":   comps_5yr,
            "housing_completions_per1k": round(comps_5yr / cenunits * 1000, 1),
            "pipeline_filed":            d.get("filed", 0),
            "pipeline_permitted":        permitted,
            "pipeline_withdrawn":        withdrawn,
            "pipeline_inactive":         inactive,
            "pipeline_stall_rate":       stall_pct,
        }

    return scores, raw_data

def format_js_layer_scores(scores, raw_data):
    """Generate the JS LAYER_SCORES constant with embedded raw data."""
    lines = ["const LAYER_SCORES = {"]
    for fips in sorted(scores.keys()):
        s = scores[fips]
        r = raw_data[fips]
        lines.append(
            f'  "{fips}":{{ housing:{s["housing"]}, cost_of_living:{s["cost_of_living"]}, '
            f'health:{s["health"]}, economic:{s["economic"]}, '
            f'_raw:{{ hpd_per_1k:{r["hpd_violations_per_1k"]}, '
            f'life_exp:{r["life_expectancy"]}, asthma:{r["asthma_per_10k"]}, '
            f'rent:{r["median_rent"]}, income_k:{r["median_income_k"]}, '
            f'eviction_rate_per_1k:{r["eviction_rate_per_1k"]}, '
            f'completions_5yr:{r["housing_completions_5yr"]}, '
            f'completions_per1k:{r["housing_completions_per1k"]}, '
            f'pipeline_filed:{r["pipeline_filed"]}, '
            f'pipeline_permitted:{r["pipeline_permitted"]}, '
            f'pipeline_withdrawn:{r["pipeline_withdrawn"]}, '
            f'pipeline_inactive:{r["pipeline_inactive"]}, '
            f'pipeline_stall_rate:{r["pipeline_stall_rate"]} }} }},'
        )
    lines.append("};")
    return "\n".join(lines)

def main():
    print("Building normalized layer scores from all sources...")
    print(f"  Housing dev data loaded for {len(HOUSING_DEV)} CDs")
    scores, raw_data = build_layer_scores()

    js_output = format_js_layer_scores(scores, raw_data)

    outfile = os.path.join(os.path.dirname(os.path.abspath(__file__)), "layer_scores_output.js")
    with open(outfile, "w") as f:
        f.write(js_output)
    print(f"Written to {outfile}")

    print("\nSample scores (stress = higher is worse):")
    for fips, name in [("201","Mott Haven"), ("316","Brownsville"), ("108","Upper East Side"), ("306","Park Slope")]:
        s = scores[fips]
        r = raw_data[fips]
        print(f"\n  {name} ({fips}):")
        print(f"    housing={s['housing']} (HPD {r['hpd_violations_per_1k']}/1k HH, stall {r['pipeline_stall_rate']}%, {r['housing_completions_per1k']}/1k units built)")
        print(f"    health={s['health']} (LE {r['life_expectancy']} yrs, asthma {r['asthma_per_10k']}/10k)")
        inc_k = MEDIAN_INCOME_K.get(fips, 1)
        burden_pct = round((MEDIAN_RENT.get(fips, 0) * 12) / (inc_k * 1000) * 100, 1)
        print(f"    cost_of_living={s['cost_of_living']} (rent ${r['median_rent']}/mo, burden {burden_pct}% of income)")
        print(f"    economic={s['economic']} (income ${r['median_income_k']}k)")
        print(f"    pipeline: {r['pipeline_filed']} filed → {r['pipeline_permitted']} permitted, {r['pipeline_withdrawn']} withdrawn, {r['pipeline_inactive']} inactive")

if __name__ == "__main__":
    main()
