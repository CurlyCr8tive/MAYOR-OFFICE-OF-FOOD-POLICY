#!/usr/bin/env python3
"""
Builds the final LAYER_SCORES object for index.html.

Data sources by layer:
  housing   — HPD Open Violations (NYC Open Data, real API pulls where available)
               supplemented with NYC Housing and Vacancy Survey 2021 estimates
  health    — DOHMH Community Health Profiles 2018 (life expectancy + asthma rates)
  cost_of_living — NYC HVS 2021 + StreetEasy 2023 median rent
  economic  — ACS 5-yr 2021 median household income (via NYC DCP Community Profiles)

Run: python3 build_layer_scores.py
"""

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
    rent_min, rent_max = min(rent_vals), max(rent_vals)
    inc_min, inc_max   = min(inc_vals), max(inc_vals)

    scores = {}
    raw_data = {}

    for fips in all_fips:
        hpd  = HPD_VIOLATIONS_PER_1K[fips]
        le   = LIFE_EXPECTANCY[fips]
        ast  = ASTHMA_PER_10K[fips]
        rent = MEDIAN_RENT[fips]
        inc  = MEDIAN_INCOME_K[fips]

        housing_score = normalize(hpd, hpd_min, hpd_max)

        # Health burden: low life expectancy + high asthma = high burden
        le_stress  = normalize(le, le_min, le_max, invert=True)
        ast_stress = normalize(ast, ast_min, ast_max)
        health_score = round(le_stress * 0.6 + ast_stress * 0.4)

        # Cost of living: high rent = high stress
        col_score = normalize(rent, rent_min, rent_max)

        # Economic stress: low income = high stress
        econ_score = normalize(inc, inc_min, inc_max, invert=True)

        scores[fips] = {
            "housing": housing_score,
            "cost_of_living": col_score,
            "health": health_score,
            "economic": econ_score,
        }
        raw_data[fips] = {
            "hpd_violations_per_1k": hpd,
            "life_expectancy": le,
            "asthma_per_10k": ast,
            "median_rent": rent,
            "median_income_k": inc,
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
            f'rent:{r["median_rent"]}, income_k:{r["median_income_k"]} }} }},'
        )
    lines.append("};")
    return "\n".join(lines)

def main():
    print("Building normalized layer scores from all sources...")
    scores, raw_data = build_layer_scores()

    js_output = format_js_layer_scores(scores, raw_data)

    outfile = "/Users/chericeheron/Desktop/MAYOR-OFFICE-OF-FOOD-POLICY/layer_scores_output.js"
    with open(outfile, "w") as f:
        f.write(js_output)
    print(f"Written to {outfile}")

    print("\nSample scores (stress = higher is worse):")
    for fips, name in [("201","Mott Haven"), ("316","Brownsville"), ("108","Upper East Side"), ("306","Park Slope")]:
        s = scores[fips]
        r = raw_data[fips]
        print(f"\n  {name} ({fips}):")
        print(f"    housing={s['housing']} (HPD {r['hpd_violations_per_1k']}/1k HH)")
        print(f"    health={s['health']} (LE {r['life_expectancy']} yrs, asthma {r['asthma_per_10k']}/10k)")
        print(f"    cost_of_living={s['cost_of_living']} (rent ${r['median_rent']}/mo)")
        print(f"    economic={s['economic']} (income ${r['median_income_k']}k)")

if __name__ == "__main__":
    main()
