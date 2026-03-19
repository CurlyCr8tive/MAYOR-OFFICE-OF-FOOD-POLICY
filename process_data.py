"""
NYC Food Insecurity Vulnerability Scorer
Reads real data from local files and outputs vulnerability_scores.json
"""

import csv, io, json, os
from datetime import datetime

# ── FIPS lookups ────────────────────────────────────────────────────────────

BOROUGH_BY_FIPS_PREFIX = {
    "1": "Manhattan",
    "2": "Bronx",
    "3": "Brooklyn",
    "4": "Queens",
    "5": "Staten Island",
}

# Canonical CD names keyed by 3-digit FIPS string
CD_NAMES = {
    "101": "Battery Park/Tribeca",      "102": "Greenwich Village",
    "103": "Lower East Side",           "104": "Chelsea/Clinton",
    "105": "Midtown Business District", "106": "Murray Hill/Stuyvesant",
    "107": "Upper West Side",           "108": "Upper East Side",
    "109": "Manhattanville",            "110": "Central Harlem",
    "111": "East Harlem",               "112": "Washington Heights",
    "201": "Mott Haven",                "202": "Hunts Point",
    "203": "Morrisania",                "204": "Concourse/Highbridge",
    "205": "University Heights",        "206": "East Tremont",
    "207": "Bedford Park",              "208": "Riverdale",
    "209": "Unionport/Soundview",       "210": "Throgs Neck",
    "211": "Pelham Parkway",            "212": "Williamsbridge",
    "301": "Williamsburg/Greenpoint",   "302": "Fort Greene/Brooklyn Hts",
    "303": "Bedford Stuyvesant",        "304": "Bushwick",
    "305": "East New York",             "306": "Park Slope",
    "307": "Sunset Park",               "308": "Crown Heights North",
    "309": "Crown Heights South",       "310": "Bay Ridge",
    "311": "Bensonhurst",               "312": "Borough Park",
    "313": "Coney Island",              "314": "Flatbush/Midwood",
    "315": "Sheepshead Bay",            "316": "Brownsville",
    "317": "East Flatbush",             "318": "Canarsie",
    "401": "Astoria",                   "402": "Sunnyside/Woodside",
    "403": "Jackson Heights",           "404": "Elmhurst/Corona",
    "405": "Ridgewood/Glendale",        "406": "Rego Park/Forest Hills",
    "407": "Flushing",                  "408": "Fresh Meadows/Briarwood",
    "409": "Woodhaven",                 "410": "Howard Beach",
    "411": "Bayside",                   "412": "Jamaica/St. Albans",
    "413": "Queens Village",            "414": "The Rockaways",
    "501": "St. George",                "502": "South Beach",
    "503": "Tottenville",
}

# CDTA2020 GeoID → 3-digit FIPS string
def cdta_to_fips(geoid: str) -> str:
    n = int(geoid)
    if 501 <= n <= 512:   return str(n - 300)   # Bronx   201-212
    if 4701 <= n <= 4718: return str(n - 4400)  # Brooklyn 301-318
    if 6101 <= n <= 6112: return str(n - 6000)  # Manhattan 101-112
    if 8101 <= n <= 8114: return str(n - 7700)  # Queens  401-414
    if 8501 <= n <= 8503: return str(n - 8000)  # Staten Island 501-503
    return None

# Risk tiers
TIERS = [
    (70, "Critical", "#d32f2f"),
    (50, "High",     "#f57c00"),
    (30, "Moderate", "#f9a825"),
    (0,  "Lower",    "#388e3c"),
]

def assign_tier(score: float):
    for threshold, label, colour in TIERS:
        if score >= threshold:
            return label, colour
    return "Lower", "#388e3c"

# ── CCC file parser ──────────────────────────────────────────────────────────

def parse_ccc(fpath: str) -> list:
    """Skip HTML metadata block; return rows from the actual data table."""
    with open(fpath, encoding="utf-8-sig") as f:
        content = f.read()
    lines = content.split("\n")
    start = None
    for i, line in enumerate(lines):
        if line.startswith("Location,"):
            start = i
            break
    if start is None:
        raise ValueError(f"No 'Location,' header found in {fpath}")
    reader = csv.DictReader(io.StringIO("\n".join(lines[start:])))
    return list(reader)

# ── NYC EH Portal file parser ────────────────────────────────────────────────

def parse_eh(fpath: str, geo_type: str = "CDTA2020") -> list:
    """Return rows where GeoType matches (default CDTA2020)."""
    with open(fpath, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    return [r for r in rows if r.get("GeoType", "").strip() == geo_type]

def clean_pct(val: str) -> float:
    """Strip commas / asterisks / CI intervals and return float."""
    val = val.split("(")[0].strip().replace(",", "").replace("*", "").strip()
    return float(val)

# ── Indicator loaders ────────────────────────────────────────────────────────

DATA_DIR = "data"

def load_snap() -> dict:
    """SNAP % of individuals (latest year per CD). Returns {fips: pct}."""
    rows = parse_ccc(os.path.join(DATA_DIR, "SNAP (Food Stamps).csv"))
    relevant = [
        r for r in rows
        if r.get("Recipient", "").strip() == "Individuals"
        and r.get("DataFormat", "").strip() == "Percent"
        and len(r.get("Fips", "").strip()) == 3
    ]
    by_fips = {}
    for r in relevant:
        fips = r["Fips"].strip()
        year = int(r["TimeFrame"].strip())
        pct  = float(r["Data"].strip()) * 100  # stored as decimal 0-1
        if fips not in by_fips or year > by_fips[fips][0]:
            by_fips[fips] = (year, pct)
    return {fips: v[1] for fips, v in by_fips.items()}

def load_citizenship() -> dict:
    """Non-citizen % (latest year per CD). Returns {fips: pct}."""
    rows = parse_ccc(os.path.join(DATA_DIR, "Citizenship.csv"))
    relevant = [
        r for r in rows
        if r.get("Citizenship Type", "").strip() == "Non-Citizens"
        and r.get("DataFormat", "").strip() == "Percent"
        and len(r.get("Fips", "").strip()) == 3
    ]
    by_fips = {}
    for r in relevant:
        fips = r["Fips"].strip()
        year = int(r["TimeFrame"].strip())
        pct  = float(r["Data"].strip()) * 100
        if fips not in by_fips or year > by_fips[fips][0]:
            by_fips[fips] = (year, pct)
    return {fips: v[1] for fips, v in by_fips.items()}

def load_eh_indicator(fname: str) -> dict:
    """NYC EH Portal CDTA2020 indicator (latest TimePeriod first).
    Returns {fips: pct}."""
    rows = parse_eh(os.path.join(DATA_DIR, fname))
    rows.sort(key=lambda r: r.get("TimePeriod", ""), reverse=True)
    by_fips = {}
    for r in rows:
        fips = cdta_to_fips(r["GeoID"].strip())
        if fips is None or fips in by_fips:
            continue
        try:
            by_fips[fips] = clean_pct(r["Percent"])
        except (ValueError, KeyError):
            continue
    return by_fips

# ── Scoring ──────────────────────────────────────────────────────────────────

WEIGHTS = {
    "snap":          0.35,
    "child_poverty": 0.20,
    "rent_burden":   0.20,
    "unemployment":  0.15,
    "noncitizen":    0.10,
}

def minmax_norm(values: list) -> list:
    lo, hi = min(values), max(values)
    if hi == lo:
        return [0.5] * len(values)
    return [(v - lo) / (hi - lo) for v in values]

def score_districts() -> dict:
    print("Loading SNAP data …")
    snap      = load_snap()
    print("Loading citizenship data …")
    citizen   = load_citizenship()
    print("Loading child poverty data …")
    child_pov = load_eh_indicator("NYC_EH_Child_poverty_under_age_5.csv")
    print("Loading rent burden data …")
    rent      = load_eh_indicator("NYC_EH_Rent-burdened_households.csv")
    print("Loading unemployment data …")
    unemp     = load_eh_indicator("NYC_EH_Unemployment.csv")

    all_fips = sorted(CD_NAMES.keys())

    # Compute city-wide means as fallback for missing CDs
    def mean(d): return sum(d.values()) / len(d) if d else 0
    snap_mean   = mean(snap)
    cp_mean     = mean(child_pov)
    rent_mean   = mean(rent)
    unemp_mean  = mean(unemp)
    noncit_mean = mean(citizen)

    def safe(d, fips, fallback):
        return d.get(fips, fallback)

    snap_vals   = [safe(snap,      f, snap_mean)   for f in all_fips]
    cp_vals     = [safe(child_pov, f, cp_mean)     for f in all_fips]
    rent_vals   = [safe(rent,      f, rent_mean)   for f in all_fips]
    unemp_vals  = [safe(unemp,     f, unemp_mean)  for f in all_fips]
    noncit_vals = [safe(citizen,   f, noncit_mean) for f in all_fips]

    # Min-max normalise across all 59 CDs
    snap_n   = minmax_norm(snap_vals)
    cp_n     = minmax_norm(cp_vals)
    rent_n   = minmax_norm(rent_vals)
    unemp_n  = minmax_norm(unemp_vals)
    noncit_n = minmax_norm(noncit_vals)

    districts = []
    for i, fips in enumerate(all_fips):
        borough = BOROUGH_BY_FIPS_PREFIX[fips[0]]
        cd_name = CD_NAMES[fips]

        raw = (
            snap_n[i]   * WEIGHTS["snap"]          +
            cp_n[i]     * WEIGHTS["child_poverty"] +
            rent_n[i]   * WEIGHTS["rent_burden"]   +
            unemp_n[i]  * WEIGHTS["unemployment"]  +
            noncit_n[i] * WEIGHTS["noncitizen"]
        ) * 100

        score        = round(raw, 1)
        tier, colour = assign_tier(score)

        districts.append({
            "fips":                fips,
            "cd_name":             cd_name,
            "borough":             borough,
            "vulnerability_score": score,
            "risk_tier":           tier,
            "color":               colour,
            "indicators": {
                "snap_household_pct": round(snap_vals[i],   2),
                "child_poverty_pct":  round(cp_vals[i],     1),
                "rent_burden_pct":    round(rent_vals[i],   1),
                "unemployment_pct":   round(unemp_vals[i],  1),
                "noncitizen_pct":     round(noncit_vals[i], 2),
            },
        })

    districts.sort(key=lambda d: d["vulnerability_score"], reverse=True)

    critical_count = sum(1 for d in districts if d["risk_tier"] == "Critical")
    high_count     = sum(1 for d in districts if d["risk_tier"] == "High")

    return {
        "metadata": {
            "description":     "NYC Food Insecurity Vulnerability Score by Community District",
            "generated":       datetime.now().isoformat(timespec="seconds"),
            "scoring_weights": WEIGHTS,
            "data_sources": {
                "snap":          "NYC HRA via CCC — latest year per district",
                "citizenship":   "ACS via CCC — latest year per district",
                "rent_burden":   "NYC EH Portal, CDTA2020 — latest 5-year period",
                "child_poverty": "NYC EH Portal, CDTA2020 — latest 5-year period",
                "unemployment":  "NYC EH Portal, CDTA2020 — latest 5-year period",
            },
            "total_districts": len(districts),
            "critical_count":  critical_count,
            "high_count":      high_count,
        },
        "districts": districts,
    }

# ── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    output   = score_districts()
    out_path = "vulnerability_scores.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)

    meta = output["metadata"]
    print(f"\nWrote {out_path}")
    print(f"  {meta['total_districts']} districts scored")
    print(f"  Critical: {meta['critical_count']}")
    print(f"  High:     {meta['high_count']}")
    print("\nTop 5 most vulnerable:")
    for d in output["districts"][:5]:
        ind = d["indicators"]
        print(f"  {d['fips']}  {d['cd_name']:30s}  score={d['vulnerability_score']}  [{d['risk_tier']}]")
        print(f"       SNAP={ind['snap_household_pct']:.1f}%  "
              f"ChildPov={ind['child_poverty_pct']:.1f}%  "
              f"Rent={ind['rent_burden_pct']:.1f}%  "
              f"Unemp={ind['unemployment_pct']:.1f}%  "
              f"NonCit={ind['noncitizen_pct']:.1f}%")
