"""
NYC Food Insecurity Data Pipeline
===================================
Scheduled refresh pipeline for the NYC Food Insecurity Vulnerability Dashboard.
Fetches fresh data from public APIs and re-runs vulnerability scoring.

Run once:    python data_pipeline.py --once
Run on schedule: python data_pipeline.py
"""

import json
import os
import schedule
import time
import requests
import argparse
from datetime import datetime


# NYC Open Data endpoints
SNAP_API = "https://data.cityofnewyork.us/resource/jye8-w4d7.json"
PANTRIES_API = "https://data.cityofnewyork.us/resource/if26-z6xq.json"

OUTPUT_DIR = "."


def log(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")


def fetch_snap_data():
    """Fetch latest SNAP enrollment data from NYC Open Data."""
    log("Fetching SNAP data from NYC Open Data...")
    try:
        resp = requests.get(SNAP_API, params={"$limit": 500}, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        log(f"  Fetched {len(data)} SNAP records")
        return data
    except Exception as e:
        log(f"  WARNING: Could not fetch SNAP data: {e}")
        return None


def fetch_pantry_locations():
    """Fetch food pantry locations from NYC Open Data."""
    log("Fetching pantry locations from NYC Open Data...")
    try:
        resp = requests.get(PANTRIES_API, params={"$limit": 1000}, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        log(f"  Fetched {len(data)} pantry locations")
        return data
    except Exception as e:
        log(f"  WARNING: Could not fetch pantry data: {e}")
        return None


def run_vulnerability_scorer():
    """Run the vulnerability scoring script if data files are present."""
    data_dir = "data"
    required_files = [
        "SNAP (Food Stamps).csv",
        "Citizenship.csv",
        "NYC_EH_Rent-burdened_households.csv",
        "NYC_EH_Child_poverty_under_age_5.csv",
        "NYC_EH_Unemployment.csv",
    ]

    missing = [f for f in required_files if not os.path.exists(os.path.join(data_dir, f))]
    if missing:
        log(f"  Skipping scorer — missing data files: {missing}")
        log("  Upload CSV files to /data directory to enable auto-scoring")
        return False

    log("Running vulnerability scorer...")
    import subprocess
    result = subprocess.run(["python", "process_data.py"], capture_output=True, text=True)
    if result.returncode == 0:
        log("  Vulnerability scores updated successfully")
        return True
    else:
        log(f"  ERROR running scorer: {result.stderr[:200]}")
        return False


def update_pipeline_status(snap_data, pantry_data):
    """Write pipeline status metadata."""
    status = {
        "last_run": datetime.now().isoformat(),
        "snap_records": len(snap_data) if snap_data else 0,
        "pantry_locations": len(pantry_data) if pantry_data else 0,
        "status": "success" if (snap_data or pantry_data) else "partial",
    }
    status_path = os.path.join(OUTPUT_DIR, "pipeline_status.json")
    with open(status_path, "w") as f:
        json.dump(status, f, indent=2)
    log(f"  Pipeline status saved to {status_path}")


def run_pipeline():
    """Main pipeline execution."""
    log("=" * 50)
    log("NYC Food Insecurity Data Pipeline — Starting")
    log("=" * 50)

    snap_data = fetch_snap_data()
    pantry_data = fetch_pantry_locations()

    if pantry_data:
        pantry_path = os.path.join(OUTPUT_DIR, "pantry_locations.json")
        with open(pantry_path, "w") as f:
            json.dump(pantry_data, f, indent=2)
        log(f"  Pantry locations saved to {pantry_path}")

    run_vulnerability_scorer()
    update_pipeline_status(snap_data, pantry_data)

    log("Pipeline complete.")


def main():
    parser = argparse.ArgumentParser(description="NYC Food Insecurity Data Pipeline")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--interval", type=int, default=24, help="Refresh interval in hours (default: 24)")
    args = parser.parse_args()

    if args.once:
        run_pipeline()
        return

    log(f"Pipeline scheduler started — refreshing every {args.interval} hours")
    run_pipeline()

    schedule.every(args.interval).hours.do(run_pipeline)

    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    main()
