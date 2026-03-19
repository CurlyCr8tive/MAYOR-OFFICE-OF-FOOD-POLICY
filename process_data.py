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

DATA_DIR = "data"

WEIGHTS = {
    "snap_pct":         0.35,
    "child_poverty_pct":0.20,
    "rent_burden_pct":  0.20,
    "unemployment_pct": 0.15,
    "noncitizen_pct":   0.10,
}

BOROUGH_MAP = {
    "1": "Manhattan",
    "2": "Bronx",
    "3": "Brooklyn",
    "4": "Queens",
    "5": "Staten Island",
}


def clean_number(val):
    if not val or val.strip() == "":
        return None
    val = val.strip().strip('"')
    val = re.sub(r'\s*\(.*?\)', '', val)
    val = val.replace(',', '').replace('*', '').replace('%', '')
    try:
        return float(val)
    except ValueError:
        return None


def skip_metadata(reader):
    for row in reader:
        if row and row[0].strip().lower() in ("location", "timeperiod"):
            return row
    return None


def normalize(values):
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


def parse_ccc_snap(filepath):
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
                    data[fips.strip()] = round(pct * 100, 2)
    return data


def parse_ccc_citizenship(filepath):
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


def parse_nyc_eh_by_cd(filepath):
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


def build_cd_name_lookup(snap_data_path):
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
    fips = str(fips).strip()
    if not fips or not fips.isdigit():
        return "Unknown"
    first = fips[0]
    return BOROUGH_MAP.get(first, "Unknown")


def main():
    print("NYC Food Insecurity Vulnerability Scorer")
    print("=" * 50)

    snap_path        = os.path.join(DATA_DIR, "SNAP (Food Stamps).csv")
    citizenship_path = os.path.join(DATA_DIR, "Citizenship.csv")
    rent_path        = os.path.join(DATA_DIR, "NYC_EH_Rent-burdened_households.csv")
    child_pov_path   = os.path.join(DATA_DIR, "NYC_EH_Child_poverty_under_age_5.csv")
    unemploy_path    = os.path.join(DATA_DIR, "NYC_EH_Unemployment.csv")

    print("\nLoading datasets...")

    snap        = parse_ccc_snap(snap_path)
    citizenship = parse_ccc_citizenship(citizenship_path)
    rent_burden = parse_nyc_eh_by_cd(rent_path)
    child_pov   = parse_nyc_eh_by_cd(child_pov_path)
    unemployment= parse_nyc_eh_by_cd(unemploy_path)
    cd_names    = build_cd_name_lookup(snap_path)

    print(f"  SNAP data:          {len(snap)} community districts")
    print(f"  Citizenship data:   {len(citizenship)} community districts")
    print(f"  Rent burden data:   {len(rent_burden)} community districts")
    print(f"  Child poverty data: {len(child_pov)} community districts")
    print(f"  Unemployment data:  {len(unemployment)} community districts")

    print("\nBuilding raw indicators per community district...")

    all_fips = set(snap.keys())

    raw = {}
    for fips in all_fips:
        cd_id = str(fips).zfill(3)
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

    print("Normalizing indicators...")

    for indicator in WEIGHTS.keys():
        raw_vals = {fips: d[indicator] for fips, d in raw.items()}
        normed   = normalize(raw_vals)
        for fips in raw:
            raw[fips][f"{indicator}_norm"] = normed[fips]

    print("Computing vulnerability scores...")

    results = []
    for fips, d in raw.items():
        score = sum(
            d.get(f"{ind}_norm", 0) * weight
            for ind, weight in WEIGHTS.items()
        )
        score_100 = round(score * 100, 1)

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

    results.sort(key=lambda x: x["vulnerability_score"], reverse=True)

    print("\nTOP 15 MOST VULNERABLE COMMUNITY DISTRICTS")
    print("-" * 65)
    print(f"{'Rank':<5} {'Community District':<28} {'Borough':<14} {'Score':<8} {'Tier'}")
    print("-" * 65)
    for i, r in enumerate(results[:15], 1):
        print(f"{i:<5} {r['cd_name']:<28} {r['borough']:<14} {r['vulnerability_score']:<8} {r['risk_tier']}")

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

    print(f"\nDone! Output saved to: {out_path}")
    print(f"   {len(results)} community districts scored")
    print(f"   {output['metadata']['critical_count']} Critical risk")
    print(f"   {output['metadata']['high_count']} High risk")


if __name__ == "__main__":
    main()
