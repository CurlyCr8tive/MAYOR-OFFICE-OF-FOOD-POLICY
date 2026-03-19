"""
NYC Food Insecurity Vulnerability Dashboard
Data Pipeline — data_pipeline.py
==============================================
Handles automated data refresh from NYC Open Data APIs.

Refresh Schedule:
  Daily     — 311 food complaints (leading indicator)
  Monthly   — SNAP enrollment + cash assistance by district
  Quarterly — Pantry utilization + full vulnerability rescore

Usage:
  python data_pipeline.py           → runs full scheduler
  python data_pipeline.py daily     → runs daily refresh only
  python data_pipeline.py monthly   → runs monthly refresh only
  python data_pipeline.py quarterly → runs quarterly refresh only
  python data_pipeline.py test      → tests API connection

Setup:
  1. Add NYC_OPEN_DATA_TOKEN to Replit Secrets
  2. Add ANTHROPIC_API_KEY to Replit Secrets
  3. pip install requests schedule anthropic
"""

import requests
import json
import os
import shutil
import schedule
import time
from datetime import datetime, timedelta

# ── CONFIG ────────────────────────────────────────────────────────────────────

NYC_TOKEN       = os.environ.get("NYC_OPEN_DATA_TOKEN", "")
ANTHROPIC_KEY   = os.environ.get("ANTHROPIC_API_KEY", "")
BASE_URL        = "https://data.cityofnewyork.us/resource"

CURRENT_FILE    = "vulnerability_scores.json"
BASELINE_FILE   = "vulnerability_scores_baseline.json"
ALERTS_FILE     = "alerts.json"
PIPELINE_LOG    = "pipeline_log.json"

# Alert thresholds
SCORE_SPIKE_THRESHOLD   = 5.0   # points — triggers HIGH alert
SCORE_CRITICAL_THRESHOLD= 10.0  # points — triggers CRITICAL alert
SNAP_SURGE_THRESHOLD    = 3.0   # % month-over-month — triggers alert
PANTRY_CAPACITY_WARNING = 85.0  # % utilization — triggers HIGH alert
PANTRY_CAPACITY_CRITICAL= 95.0  # % utilization — triggers CRITICAL alert
COMPLAINTS_SPIKE        = 10    # 311 complaints per community board per day

# NYC Open Data dataset IDs
DATASETS = {
    "snap_by_district":  "jye8-w4d7",  # SNAP Population by Community District
    "cash_assistance":   "kjcq-h8d9",  # Cash Assistance by Community District
    "cfc_utilization":   "unw5-rvbq",  # CFC Pantry Meals & Individuals Served
    "complaints_311":    "erm2-nwe9",  # 311 Service Requests
    "pantry_locations":  "54h5-vbp4",  # Community Food Connection Locations
}


# ── API FETCHERS ──────────────────────────────────────────────────────────────

def api_get(dataset_id, params={}):
    """
    Generic Socrata API fetch for any NYC Open Data dataset.
    Returns list of records or empty list on failure.
    """
    url = f"{BASE_URL}/{dataset_id}.json"
    if NYC_TOKEN:
        params["$$app_token"] = NYC_TOKEN

    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        log_error(f"Timeout fetching dataset {dataset_id}")
        return []
    except requests.exceptions.HTTPError as e:
        log_error(f"HTTP error fetching {dataset_id}: {e}")
        return []
    except requests.exceptions.ConnectionError:
        log_error(f"Connection error fetching {dataset_id} — check internet")
        return []
    except Exception as e:
        log_error(f"Unexpected error fetching {dataset_id}: {e}")
        return []


def fetch_snap_by_district():
    """
    Monthly — SNAP enrollment by community district.
    Returns most recent month's data for all 59 CDs.
    """
    print("  Fetching SNAP enrollment by district...")
    data = api_get(DATASETS["snap_by_district"], {
        "$order": "month_year DESC",
        "$limit": "200",
    })
    print(f"     -> {len(data)} records returned")
    return data


def fetch_cash_assistance():
    """
    Monthly — Cash assistance recipients by community district.
    Proxy indicator for households with zero income buffer.
    """
    print("  Fetching cash assistance data...")
    data = api_get(DATASETS["cash_assistance"], {
        "$order": "month_year DESC",
        "$limit": "100",
    })
    print(f"     -> {len(data)} records returned")
    return data


def fetch_pantry_utilization():
    """
    Quarterly — CFC pantry meals and individuals served.
    Used to detect capacity stress before it becomes a crisis.
    """
    print("  Fetching pantry utilization data...")
    data = api_get(DATASETS["cfc_utilization"], {
        "$order": "quarter DESC",
        "$limit": "500",
    })
    print(f"     -> {len(data)} records returned")
    return data


def fetch_pantry_locations():
    """
    Quarterly — CFC pantry and soup kitchen locations.
    Used to update the map markers.
    """
    print("  Fetching pantry locations...")
    data = api_get(DATASETS["pantry_locations"], {
        "$limit": "2000",
        "$select": "facilityname, address, borough, latitude, longitude, "
                   "community_district, hours_of_operation",
    })
    print(f"     -> {len(data)} pantry locations returned")
    return data


def fetch_311_food_complaints():
    """
    Daily — 311 complaints related to food in last 24 hours.
    Early warning indicator — spikes precede formal data by weeks.
    """
    print("  Fetching 311 food complaints (last 24 hours)...")
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%dT00:00:00')
    data = api_get(DATASETS["complaints_311"], {
        "$where": f"created_date > '{yesterday}'",
        "$select": "community_board, borough, complaint_type, count(*) as count",
        "$group": "community_board, borough, complaint_type",
        "$having": "count(*) > 0",
        "$order": "count DESC",
        "$limit": "200",
    })
    print(f"     -> {len(data)} community board complaint groups returned")
    return data


# ── ALERT DETECTORS ───────────────────────────────────────────────────────────

def check_score_changes():
    """
    Compare current vulnerability scores to baseline.
    Fires on significant increases — district getting worse.
    """
    alerts = []

    if not os.path.exists(CURRENT_FILE):
        log_error("No current scores file found — run process_data.py first")
        return alerts

    if not os.path.exists(BASELINE_FILE):
        log_info("No baseline found — creating baseline from current scores")
        shutil.copy(CURRENT_FILE, BASELINE_FILE)
        return alerts

    with open(CURRENT_FILE) as f:
        current = json.load(f)
    with open(BASELINE_FILE) as f:
        baseline = json.load(f)

    baseline_map = {d["fips"]: d for d in baseline.get("districts", [])}

    for district in current.get("districts", []):
        fips     = district["fips"]
        prev     = baseline_map.get(fips, {})
        prev_score = prev.get("vulnerability_score", 0)
        curr_score = district["vulnerability_score"]
        change   = curr_score - prev_score

        if change >= SCORE_CRITICAL_THRESHOLD:
            alerts.append({
                "type":        "SCORE_SPIKE",
                "severity":    "Critical",
                "district":    district["cd_name"],
                "borough":     district["borough"],
                "prev_score":  prev_score,
                "curr_score":  curr_score,
                "change":      round(change, 1),
                "indicators":  district["indicators"],
                "message":     f"Vulnerability score increased +{round(change,1)} points",
                "timestamp":   datetime.now().isoformat(),
            })
        elif change >= SCORE_SPIKE_THRESHOLD:
            alerts.append({
                "type":        "SCORE_SPIKE",
                "severity":    "High",
                "district":    district["cd_name"],
                "borough":     district["borough"],
                "prev_score":  prev_score,
                "curr_score":  curr_score,
                "change":      round(change, 1),
                "indicators":  district["indicators"],
                "message":     f"Vulnerability score increased +{round(change,1)} points",
                "timestamp":   datetime.now().isoformat(),
            })

        # New Critical tier alert
        if (district["risk_tier"] == "Critical" and
                prev.get("risk_tier") not in ("Critical",)):
            alerts.append({
                "type":      "NEW_CRITICAL",
                "severity":  "Critical",
                "district":  district["cd_name"],
                "borough":   district["borough"],
                "curr_score": curr_score,
                "message":   f"District elevated to CRITICAL tier",
                "timestamp": datetime.now().isoformat(),
            })

    return alerts


def check_snap_surge(snap_data):
    """
    Detect month-over-month SNAP enrollment spikes by district.
    3%+ increase triggers HIGH alert.
    """
    alerts = []
    if not snap_data:
        return alerts

    # Group records by community district
    by_district = {}
    for row in snap_data:
        cd = row.get("community_district", "").strip()
        if not cd:
            continue
        if cd not in by_district:
            by_district[cd] = []
        by_district[cd].append(row)

    for cd, rows in by_district.items():
        # Sort by most recent month
        rows_sorted = sorted(
            rows,
            key=lambda x: x.get("month_year", ""),
            reverse=True
        )
        if len(rows_sorted) < 2:
            continue

        try:
            curr_val = int(rows_sorted[0].get("snap_individuals", 0) or 0)
            prev_val = int(rows_sorted[1].get("snap_individuals", 0) or 0)
            if prev_val == 0:
                continue

            pct_change = ((curr_val - prev_val) / prev_val) * 100

            if pct_change >= SNAP_SURGE_THRESHOLD:
                alerts.append({
                    "type":            "SNAP_SURGE",
                    "severity":        "High",
                    "district":        cd,
                    "borough":         rows_sorted[0].get("borough", ""),
                    "pct_change":      round(pct_change, 1),
                    "curr_enrollment": curr_val,
                    "prev_enrollment": prev_val,
                    "message":         f"SNAP enrollment up {round(pct_change,1)}% month-over-month",
                    "timestamp":       datetime.now().isoformat(),
                })
        except (ValueError, TypeError, ZeroDivisionError):
            continue

    return alerts


def check_pantry_capacity(pantry_data):
    """
    Detect pantries approaching or exceeding capacity.
    Fires when utilization >= 85%.
    """
    alerts = []
    if not pantry_data:
        return alerts

    for pantry in pantry_data:
        try:
            served   = int(pantry.get("individuals_served", 0) or 0)
            capacity = int(pantry.get("capacity", 0) or 0)
            if capacity == 0:
                continue

            util_pct = (served / capacity) * 100

            if util_pct >= PANTRY_CAPACITY_WARNING:
                severity = "Critical" if util_pct >= PANTRY_CAPACITY_CRITICAL else "High"
                alerts.append({
                    "type":        "PANTRY_CAPACITY",
                    "severity":    severity,
                    "district":    pantry.get("community_district", ""),
                    "borough":     pantry.get("borough", ""),
                    "pantry_name": pantry.get("facilityname", "Unknown Pantry"),
                    "utilization": round(util_pct, 1),
                    "message":     f"Pantry at {round(util_pct,1)}% capacity",
                    "timestamp":   datetime.now().isoformat(),
                })
        except (ValueError, TypeError, ZeroDivisionError):
            continue

    return alerts


def check_311_spikes(complaint_data):
    """
    Detect 311 complaint spikes by community board.
    More than COMPLAINTS_SPIKE per day triggers MEDIUM alert.
    """
    alerts = []
    if not complaint_data:
        return alerts

    for row in complaint_data:
        try:
            count = int(row.get("count", 0) or 0)
            if count >= COMPLAINTS_SPIKE:
                alerts.append({
                    "type":           "COMPLAINTS_SPIKE",
                    "severity":       "Medium",
                    "district":       row.get("community_board", ""),
                    "borough":        row.get("borough", ""),
                    "complaint_type": row.get("complaint_type", ""),
                    "count":          count,
                    "message":        f"{count} food complaints in 24 hours",
                    "timestamp":      datetime.now().isoformat(),
                })
        except (ValueError, TypeError):
            continue

    return alerts


# ── AI ALERT ANALYSIS ─────────────────────────────────────────────────────────

def generate_ai_analysis(alerts):
    """
    Send triggered alerts to Claude for plain-English interpretation
    and specific recommended actions for MOFP planners.
    Returns list of AI-enriched alert objects.
    """
    if not alerts or not ANTHROPIC_KEY:
        return None

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

        # Only send top 5 alerts to avoid token overuse
        alert_summary = json.dumps(alerts[:5], indent=2)

        prompt = f"""You are an AI analyst for NYC's Mayor's Office of Food Policy.
These automated alerts were just triggered by the data pipeline.

For EACH alert provide a JSON object with:
- alert_type: copy from input
- district: copy from input  
- one_line_summary: plain English, under 20 words
- likely_cause: most probable reason given federal SNAP cuts context
- recommended_action: one specific action a city planner can take TODAY

Context: Federal SNAP cuts of $186B incoming. Work requirements 
take effect March 2026. 1.8M NYC recipients at risk. 
8 Critical Bronx/Brooklyn districts already identified.

Alerts to analyze:
{alert_summary}

Return ONLY a valid JSON array. No other text."""

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}]
        )

        raw = message.content[0].text.strip()
        # Strip markdown code blocks if present
        raw = raw.replace("```json", "").replace("```", "").strip()
        return json.loads(raw)

    except ImportError:
        log_error("anthropic package not installed — pip install anthropic")
        return None
    except json.JSONDecodeError as e:
        log_error(f"AI response was not valid JSON: {e}")
        return None
    except Exception as e:
        log_error(f"AI analysis failed: {e}")
        return None


# ── SAVE / LOAD ───────────────────────────────────────────────────────────────

def save_alerts(alerts, source="manual", ai_analysis=None):
    """Prepend new alert batch to alerts.json. Keeps last 180 entries."""
    existing = []
    if os.path.exists(ALERTS_FILE):
        try:
            with open(ALERTS_FILE) as f:
                existing = json.load(f)
        except json.JSONDecodeError:
            existing = []

    entry = {
        "source":       source,
        "generated_at": datetime.now().isoformat(),
        "alert_count":  len(alerts),
        "alerts":       alerts,
        "ai_analysis":  ai_analysis,
    }
    existing.insert(0, entry)
    existing = existing[:180]  # rolling 180-batch window

    with open(ALERTS_FILE, "w") as f:
        json.dump(existing, f, indent=2)

    print(f"  Saved {len(alerts)} alerts -> {ALERTS_FILE}")


def save_pantry_locations(pantry_data):
    """Save live pantry locations as GeoJSON for the map."""
    if not pantry_data:
        return

    features = []
    for p in pantry_data:
        try:
            lat = float(p.get("latitude", 0) or 0)
            lng = float(p.get("longitude", 0) or 0)
            if lat == 0 or lng == 0:
                continue
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [lng, lat]
                },
                "properties": {
                    "name":     p.get("facilityname", "Food Pantry"),
                    "address":  p.get("address", ""),
                    "borough":  p.get("borough", ""),
                    "district": p.get("community_district", ""),
                    "hours":    p.get("hours_of_operation", ""),
                }
            })
        except (ValueError, TypeError):
            continue

    geojson = {
        "type": "FeatureCollection",
        "generated_at": datetime.now().isoformat(),
        "features": features
    }

    with open("pantry_locations.geojson", "w") as f:
        json.dump(geojson, f)

    print(f"  Saved {len(features)} pantry locations -> pantry_locations.geojson")


def log_event(event_type, message, data=None):
    """Append event to pipeline_log.json."""
    log = []
    if os.path.exists(PIPELINE_LOG):
        try:
            with open(PIPELINE_LOG) as f:
                log = json.load(f)
        except json.JSONDecodeError:
            log = []

    log.insert(0, {
        "timestamp":  datetime.now().isoformat(),
        "type":       event_type,
        "message":    message,
        "data":       data,
    })
    log = log[:500]  # keep last 500 log entries

    with open(PIPELINE_LOG, "w") as f:
        json.dump(log, f, indent=2)


def log_info(msg):
    print(f"  INFO: {msg}")
    log_event("INFO", msg)


def log_error(msg):
    print(f"  ERROR: {msg}")
    log_event("ERROR", msg)


def log_success(msg):
    print(f"  OK: {msg}")
    log_event("SUCCESS", msg)


# ── REFRESH JOBS ──────────────────────────────────────────────────────────────

def daily_refresh():
    """
    Runs every day at 7:00 AM.
    Pulls 311 complaints — fastest-moving leading indicator.
    """
    print(f"\nDAILY REFRESH — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 50)

    complaints = fetch_311_food_complaints()
    alerts     = check_311_spikes(complaints)

    if alerts:
        ai = generate_ai_analysis(alerts)
        save_alerts(alerts, source="311_daily", ai_analysis=ai)
        print(f"  {len(alerts)} complaint spike alerts generated")
    else:
        log_success("No 311 spikes detected")

    log_event("DAILY_REFRESH", f"Completed — {len(alerts)} alerts", {
        "complaints_checked": len(complaints),
        "alerts_generated":   len(alerts),
    })
    print(f"  Daily refresh complete\n")


def monthly_refresh():
    """
    Runs 1st of each month at 8:00 AM.
    Pulls SNAP + cash assistance, detects enrollment surges,
    then reruns the vulnerability scorer with fresh data.
    """
    print(f"\nMONTHLY REFRESH — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 50)

    # Fetch
    snap_data = fetch_snap_by_district()
    ca_data   = fetch_cash_assistance()

    # Detect alerts
    snap_alerts = check_snap_surge(snap_data)
    all_alerts  = snap_alerts

    if all_alerts:
        ai = generate_ai_analysis(all_alerts)
        save_alerts(all_alerts, source="monthly_snap", ai_analysis=ai)
        print(f"  {len(all_alerts)} monthly alerts generated")
    else:
        log_success("No SNAP surges detected this month")

    # Rescore vulnerability with fresh data
    print("  Rescoring vulnerability with fresh SNAP data...")
    result = os.system("python3 process_data.py")
    if result == 0:
        log_success("Vulnerability scores updated")
    else:
        log_error("Rescoring failed — check process_data.py")

    log_event("MONTHLY_REFRESH", f"Completed — {len(all_alerts)} alerts", {
        "snap_records":     len(snap_data),
        "ca_records":       len(ca_data),
        "alerts_generated": len(all_alerts),
    })
    print(f"  Monthly refresh complete\n")


def quarterly_refresh():
    """
    Runs every 90 days at 9:00 AM.
    Pulls pantry utilization, checks capacity stress,
    compares scores to baseline, updates pantry map layer,
    then resets the baseline.
    """
    print(f"\nQUARTERLY REFRESH — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 50)

    # Fetch
    pantry_util  = fetch_pantry_utilization()
    pantry_locs  = fetch_pantry_locations()

    # Detect alerts
    capacity_alerts = check_pantry_capacity(pantry_util)
    score_alerts    = check_score_changes()
    all_alerts      = capacity_alerts + score_alerts

    if all_alerts:
        ai = generate_ai_analysis(all_alerts)
        save_alerts(all_alerts, source="quarterly", ai_analysis=ai)
        print(f"  {len(all_alerts)} quarterly alerts generated")
        print(f"     -> {len(capacity_alerts)} pantry capacity alerts")
        print(f"     -> {len(score_alerts)} score change alerts")
    else:
        log_success("No significant changes detected this quarter")

    # Save live pantry locations for map
    if pantry_locs:
        save_pantry_locations(pantry_locs)

    # Reset baseline to current scores
    if os.path.exists(CURRENT_FILE):
        shutil.copy(CURRENT_FILE, BASELINE_FILE)
        log_success(f"Baseline updated -> {BASELINE_FILE}")

    log_event("QUARTERLY_REFRESH", f"Completed — {len(all_alerts)} alerts", {
        "pantry_util_records": len(pantry_util),
        "pantry_locations":    len(pantry_locs),
        "alerts_generated":    len(all_alerts),
    })
    print(f"  Quarterly refresh complete\n")


# ── SCHEDULER ─────────────────────────────────────────────────────────────────

def run_scheduler():
    """
    Sets up and runs the cron-style scheduler.
    Runs all refreshes once on startup, then on schedule.

    For Replit free tier: this process must stay running.
    Consider Replit Always On or deploy to Railway/Render.
    """
    print("NYC Food Insecurity Alert Pipeline — Starting")
    print("=" * 50)
    print(f"  NYC Open Data token: {'Set' if NYC_TOKEN else 'Missing — set NYC_OPEN_DATA_TOKEN in Secrets'}")
    print(f"  Anthropic API key:   {'Set' if ANTHROPIC_KEY else 'Missing — AI analysis disabled'}")
    print()

    # Schedule
    schedule.every().day.at("07:00").do(daily_refresh)
    schedule.every(30).days.do(monthly_refresh)
    schedule.every(90).days.do(quarterly_refresh)

    # Run all once immediately on startup
    print("Running initial refresh on startup...")
    daily_refresh()
    monthly_refresh()
    quarterly_refresh()

    print("Scheduler active — checking every 60 seconds")
    print("Press Ctrl+C to stop\n")

    while True:
        schedule.run_pending()
        time.sleep(60)


# ── API CONNECTION TEST ───────────────────────────────────────────────────────

def test_connection():
    """Test that NYC Open Data API is reachable and token works."""
    print("\nTesting NYC Open Data API connection...")
    data = api_get(DATASETS["snap_by_district"], {"$limit": "3"})
    if data:
        print(f"  Connected — got {len(data)} test records")
        print(f"  Sample: {json.dumps(data[0], indent=4)}")
    else:
        print("  Connection failed — check token and internet")

    if ANTHROPIC_KEY:
        print("\nTesting Anthropic API connection...")
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
            msg = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=30,
                messages=[{"role":"user","content":"Reply with: API connected"}]
            )
            print(f"  Claude: {msg.content[0].text}")
        except Exception as e:
            print(f"  Anthropic error: {e}")
    else:
        print("\n  ANTHROPIC_API_KEY not set — skipping AI test")


# ── ENTRY POINT ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    commands = {
        "daily":     daily_refresh,
        "monthly":   monthly_refresh,
        "quarterly": quarterly_refresh,
        "test":      test_connection,
    }

    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()
        if cmd in commands:
            commands[cmd]()
        else:
            print(f"Unknown command: {cmd}")
            print(f"Valid commands: {', '.join(commands.keys())}")
    else:
        run_scheduler()
