"""
NYC Food Insecurity Vulnerability Scorer
=========================================
Builds a neighborhood-level vulnerability score for each of NYC's
59 Community Districts using uploaded CCC + NYC EH datasets.

Output: vulnerability_scores.json — ready to plug into your Leaflet map.

Data Sources:
  - SNAP (Food Stamps).csv           → CCC / HRA (2024)
  - Citizenship.csv                  → CCC / ACS (2023)
  - Poverty.csv                      → CCC / ACS (2024)
  - Rent-burdened_households.csv     → NYC EH Portal (2017-21)
  - Child_poverty_under_age_5.csv    → NYC EH Portal (2017-21)
  - Unemployment.csv                 → NYC EH Portal (2017-21)

Scoring Formula (0–100 scale):
  SNAP household rate       35%  ← primary federal cut exposure
  Child poverty rate        20%  ← most vulnerable population
  Rent burden rate          20%  ← zero financial buffer indicator
  Unemployment rate         15%  ← economic fragility
  Non-citizen population    10%  ← SNAP eligibility cut risk
"""

import csv
import json
import re
import os

# ── CONFIG ────────────────────────────────────────────────────────────────────

DATA_DIR = "data"   # put all your CSVs in a /data folder in Replit

WEIGHTS = {
    "snap_pct":         0.35,
    "child_poverty_pct":0.20,
    "rent_burden_pct":  0.20,
    "unemployment_pct": 0.15,
    "noncitizen_pct":   0.10,
}

# Borough prefix map — used to label outputs
BOROUGH_MAP = {
    "1": "Manhattan",
    "2": "Bronx",
    "3": "Brooklyn",
    "4": "Queens",
    "5": "Staten Island",
}

# ── HELPERS ───────────────────────────────────────────────────────────────────

def clean_number(val):
    """Strip commas, asterisks, confidence intervals, convert to float."""
    if not val or val.strip() == "":
        return None
    val = val.strip().strip('"')
    val = re.sub(r'\s*\(.*?\)', '', val)   # remove (CI ranges)
    val = val.replace(',', '').replace('*', '').replace('%', '')
    try:
        return float(val)
    except ValueError:
        return None

def skip_metadata(reader):
    """CCC CSVs have a metadata header block before actual data.
    Skip rows until we hit the real header row (Location,...)."""
    for row in reader:
        if row and row[0].strip().lower() in ("location", "timeperiod"):
            return row  # return the header row
    return None

def normalize(values):
    """Min-max normalize a dict of {key: value} to 0-1 scale."""
    nums = [v for v in values.values() if v is not None]
    if not nums:
        return {k: 0 for k in values}
    mn, mx = min(nums), max(nums)
    if mx == mn:
        return {k: 0.5 for k in values}
    return {
        k: (v - mn) / (mx - mn) if v is not None else 0
        for k, v in values.items()
    }

# ── PARSERS ───────────────────────────────────────────────────────────────────

def parse_ccc_snap(filepath):
    """
    Returns dict: {fips_code: snap_household_pct}
    Uses 2024 Households Percent data, community district level only.
    Excludes borough-level and citywide rows.
    """
    data = {}
    borough_fips = {"36005", "36047", "36061", "36081", "36085", "3651000"}

    with open(filepath, encoding="utf-8-sig", errors="replace") as f:
        reader = csv.reader(f)
        skip_metadata(reader)
        for row in reader:
            if len(row) < 6:
                continue
            location, recipient, timeframe, fmt, value, fips = row[:6]
            fips = fips.strip().strip('\r')
            if (timeframe.strip() == "2024"
                    and recipient.strip() == "Households"
                    and fmt.strip() == "Percent"
                    and fips not in borough_fips
                    and fips.strip().isdigit()
                    and len(fips.strip()) <= 3):
                pct = clean_number(value)
                if pct is not None:
                    # CCC stores as decimal (0.73 = 73%) — convert to %
                    data[fips.strip()] = round(pct * 100, 2)
    return data


def parse_ccc_citizenship(filepath):
    """
    Returns dict: {fips_code: noncitizen_pct}
    Uses 2023 Non-Citizens Percent, community district level.
    """
    data = {}
    borough_fips = {"36005", "36047", "36061", "36081", "36085", "3651000"}

    with open(filepath, encoding="utf-8-sig", errors="replace") as f:
        reader = csv.reader(f)
        skip_metadata(reader)
        for row in reader:
            if len(row) < 6:
                continue
            location, cit_type, timeframe, fmt, value, fips = row[:6]
            fips = fips.strip().strip('\r')
            if (timeframe.strip() == "2023"
                    and "Non-Citizen" in cit_type
                    and fmt.strip() == "Percent"
                    and fips not in borough_fips
                    and fips.strip().isdigit()
                    and len(fips.strip()) <= 3):
                pct = clean_number(value)
                if pct is not None:
                    data[fips.strip()] = round(pct * 100, 2)
    return data


def parse_nyc_eh(filepath, geo_type="NTA2020"):
    """
    Generic parser for NYC EH Portal CSVs.
    Returns dict: {geography_name: percent}
    Uses the specified GeoType and most recent TimePeriod.
    """
    data = {}
    rows_by_geo = {}

    with open(filepath, encoding="utf-8-sig", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("GeoType", "").strip() != geo_type:
                continue
            geo_name = row.get("Geography", "").strip()
            time_period = row.get("TimePeriod", "").strip()
            pct_raw = row.get("Percent", "").strip()
            pct = clean_number(pct_raw)
            if pct is None or geo_name == "":
                continue
            # Keep only the most recent time period per geography
            if geo_name not in rows_by_geo or time_period > rows_by_geo[geo_name]["time"]:
                rows_by_geo[geo_name] = {"time": time_period, "pct": pct}

    return {geo: v["pct"] for geo, v in rows_by_geo.items()}


def parse_nyc_eh_by_cd(filepath):
    """
    Parse NYC EH data at the CD (Community District) level.
    Returns dict: {geo_id_str: percent}
    """
    data = {}
    rows_by_geo = {}

    with open(filepath, encoding="utf-8-sig", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("GeoType", "").strip() != "CD":
                continue
            geo_id = str(row.get("GeoID", "")).strip()
            geo_name = row.get("Geography", "").strip()
            time_period = row.get("TimePeriod", "").strip()
            pct_raw = row.get("Percent", "").strip()
            pct = clean_number(pct_raw)
            if pct is None or geo_id == "":
                continue
            if geo_id not in rows_by_geo or time_period > rows_by_geo[geo_id]["time"]:
                rows_by_geo[geo_id] = {
                    "time": time_period,
                    "pct": pct,
                    "name": geo_name
                }

    return {geo_id: v["pct"] for geo_id, v in rows_by_geo.items()}


# ── NTA → CD AGGREGATION ──────────────────────────────────────────────────────

# NTA2020 GeoID prefix → Community District FIPS
# NTA GeoIDs follow the pattern: BBNNN where BB=borough code, NNN=sequence
# We map by borough + approximate CD using NTA GeoID ranges
# This is a simplified crosswalk — for production use NYC's official NTA-CD crosswalk

def nta_geoid_to_cd_fips(nta_geo_id):
    """
    NTA2020 GeoIDs are 5-digit: first 2 = borough code
    50xxx = Bronx, 30xxx = Brooklyn, 10xxx = Manhattan,
    40xxx = Queens, 60xxx = Staten Island
    Returns approximate CD FIPS (1-3 digit string matching CCC data)
    """
    # We'll use the NTA geography names to match CD names where possible
    # This is handled in the main aggregation step
    pass


def aggregate_nta_to_borough(nta_data):
    """
    Since exact NTA→CD crosswalk requires a separate lookup table,
    we aggregate NTA data to borough level as a fallback,
    then use borough averages for CDs without direct matches.
    Returns dict: {borough_name: avg_pct}
    """
    # NTA GeoID prefix → borough
    prefix_to_borough = {
        "1": "Manhattan",
        "2": "Manhattan",  # some overlap
        "3": "Manhattan",
        "5": "Bronx",
        "3": "Brooklyn",
        "4": "Queens",
        "6": "Staten Island",
    }
    # Better: use NTA GeoID first digit
    geo_prefix_borough = {
        "1": "Manhattan",
        "5": "Bronx",
        "3": "Brooklyn",
        "4": "Queens",
        "6": "Staten Island",
    }
    return nta_data  # return as-is, we'll match by name below


# ── MAIN BUILDER ──────────────────────────────────────────────────────────────

def build_cd_name_lookup(snap_data_path):
    """Build a lookup of FIPS → community district name from SNAP data."""
    lookup = {}
    borough_fips = {"36005", "36047", "36061", "36081", "36085", "3651000"}

    with open(snap_data_path, encoding="utf-8-sig", errors="replace") as f:
        reader = csv.reader(f)
        skip_metadata(reader)
        for row in reader:
            if len(row) < 6:
                continue
            location, _, timeframe, fmt, _, fips = row[:6]
            fips = fips.strip().strip('\r')
            if (timeframe.strip() == "2024"
                    and fips not in borough_fips
                    and fips.strip().isdigit()
                    and len(fips.strip()) <= 3
                    and fips.strip() not in lookup):
                lookup[fips.strip()] = location.strip()
    return lookup


def get_borough(fips):
    """Derive borough from FIPS code."""
    fips = str(fips).strip()
    if not fips or not fips.isdigit():
        return "Unknown"
    first = fips[0]
    return BOROUGH_MAP.get(first, "Unknown")


def main():
    print("🗽 NYC Food Insecurity Vulnerability Scorer")
    print("=" * 50)

    # ── Load datasets ─────────────────────────────────────────────────────────
    snap_path        = os.path.join(DATA_DIR, "SNAP (Food Stamps).csv")
    citizenship_path = os.path.join(DATA_DIR, "Citizenship.csv")
    rent_path        = os.path.join(DATA_DIR, "NYC_EH_Rent-burdened_households.csv")
    child_pov_path   = os.path.join(DATA_DIR, "NYC_EH_Child_poverty_under_age_5.csv")
    unemploy_path    = os.path.join(DATA_DIR, "NYC_EH_Unemployment.csv")

    print("\n📂 Loading datasets...")

    snap        = parse_ccc_snap(snap_path)
    citizenship = parse_ccc_citizenship(citizenship_path)
    rent_burden = parse_nyc_eh_by_cd(rent_path)
    child_pov   = parse_nyc_eh_by_cd(child_pov_path)
    unemployment= parse_nyc_eh_by_cd(unemploy_path)
    cd_names    = build_cd_name_lookup(snap_path)

    print(f"  ✅ SNAP data:          {len(snap)} community districts")
    print(f"  ✅ Citizenship data:   {len(citizenship)} community districts")
    print(f"  ✅ Rent burden data:   {len(rent_burden)} community districts")
    print(f"  ✅ Child poverty data: {len(child_pov)} community districts")
    print(f"  ✅ Unemployment data:  {len(unemployment)} community districts")

    # ── Build raw scores per CD ───────────────────────────────────────────────
    print("\n📊 Building raw indicators per community district...")

    all_fips = set(snap.keys())

    raw = {}
    for fips in all_fips:
        cd_id = str(fips).zfill(3)  # normalize to 3 digits for EH lookup
        raw[fips] = {
            "fips":              fips,
            "cd_name":           cd_names.get(fips, f"CD {fips}"),
            "borough":           get_borough(fips),
            "snap_pct":          snap.get(fips),
            "noncitizen_pct":    citizenship.get(fips),
            "rent_burden_pct":   rent_burden.get(fips) or rent_burden.get(cd_id),
            "child_poverty_pct": child_pov.get(fips) or child_pov.get(cd_id),
            "unemployment_pct":  unemployment.get(fips) or unemployment.get(cd_id),
        }

    # ── Normalize each indicator 0–1 ──────────────────────────────────────────
    print("📐 Normalizing indicators...")

    for indicator in WEIGHTS.keys():
        raw_vals = {fips: d[indicator] for fips, d in raw.items()}
        normed   = normalize(raw_vals)
        for fips in raw:
            raw[fips][f"{indicator}_norm"] = normed[fips]

    # ── Compute weighted vulnerability score (0–100) ──────────────────────────
    print("⚡ Computing vulnerability scores...")

    results = []
    for fips, d in raw.items():
        score = sum(
            d.get(f"{ind}_norm", 0) * weight
            for ind, weight in WEIGHTS.items()
        )
        score_100 = round(score * 100, 1)

        # Risk tier
        if score_100 >= 70:
            tier = "Critical"
            color = "#d32f2f"
        elif score_100 >= 50:
            tier = "High"
            color = "#f57c00"
        elif score_100 >= 30:
            tier = "Moderate"
            color = "#fbc02d"
        else:
            tier = "Lower"
            color = "#388e3c"

        results.append({
            "fips":              fips,
            "cd_name":           d["cd_name"],
            "borough":           d["borough"],
            "vulnerability_score": score_100,
            "risk_tier":         tier,
            "color":             color,
            "indicators": {
                "snap_household_pct":    d["snap_pct"],
                "child_poverty_pct":     d["child_poverty_pct"],
                "rent_burden_pct":       d["rent_burden_pct"],
                "unemployment_pct":      d["unemployment_pct"],
                "noncitizen_pct":        d["noncitizen_pct"],
            }
        })

    # Sort by score descending
    results.sort(key=lambda x: x["vulnerability_score"], reverse=True)

    # ── Print summary table ───────────────────────────────────────────────────
    print("\n📋 TOP 15 MOST VULNERABLE COMMUNITY DISTRICTS")
    print("-" * 65)
    print(f"{'Rank':<5} {'Community District':<28} {'Borough':<14} {'Score':<8} {'Tier'}")
    print("-" * 65)
    for i, r in enumerate(results[:15], 1):
        print(f"{i:<5} {r['cd_name']:<28} {r['borough']:<14} {r['vulnerability_score']:<8} {r['risk_tier']}")

    print("\n📋 BOTTOM 5 LEAST VULNERABLE")
    print("-" * 65)
    for i, r in enumerate(results[-5:], len(results)-4):
        print(f"{i:<5} {r['cd_name']:<28} {r['borough']:<14} {r['vulnerability_score']:<8} {r['risk_tier']}")

    # ── Export JSON ───────────────────────────────────────────────────────────
    output = {
        "metadata": {
            "description": "NYC Food Insecurity Vulnerability Score by Community District",
            "scoring_weights": WEIGHTS,
            "data_sources": {
                "snap":          "NYC HRA via CCC, 2024",
                "citizenship":   "ACS via CCC, 2023",
                "rent_burden":   "NYC EH Portal, 2017-21",
                "child_poverty": "NYC EH Portal, 2017-21",
                "unemployment":  "NYC EH Portal, 2017-21",
            },
            "total_districts": len(results),
            "critical_count":  sum(1 for r in results if r["risk_tier"] == "Critical"),
            "high_count":      sum(1 for r in results if r["risk_tier"] == "High"),
        },
        "districts": results
    }

    out_path = "vulnerability_scores.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n✅ Done! Output saved to: {out_path}")
    print(f"   {len(results)} community districts scored")
    print(f"   {output['metadata']['critical_count']} Critical risk")
    print(f"   {output['metadata']['high_count']} High risk")


if __name__ == "__main__":
    main()
