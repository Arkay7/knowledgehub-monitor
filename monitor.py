"""
monitor.py - Week 2 (Task 10)
Continued Scripting (Application Basic)

Command-line monitoring application. Configuration (which system to
monitor and which metrics to track) is supplied via a JSON config file -
the application never pauses to ask for interactive input, so it can be
scheduled or scripted.

Usage:
    python monitor.py record --config config.json
    python monitor.py record --config config.json --reset
    python monitor.py report --config config.json
    python monitor.py report --start 2026-10-01T00:00:00 --end 2026-10-04T23:59:59 --stats
"""

import argparse
import csv
import json
import os
from datetime import datetime

import psutil

DATA_FILE = "data/measurements.csv"
FIELDNAMES = ["timestamp", "hostname", "ip_address", "metric", "value"]

# Maps a metric name (as entered by the user in the config file) to the
# function that measures it. New metrics can be added here.
METRIC_FUNCTIONS = {
    "cpu_usage": lambda: psutil.cpu_percent(interval=1),
    "memory_usage": lambda: psutil.virtual_memory().percent,
    "disk_root_usage": lambda: psutil.disk_usage("/").percent,
}


def load_config(path):
    """Load the monitoring configuration (host info + metrics) from JSON."""
    with open(path, "r", encoding="utf-8") as config_file:
        return json.load(config_file)


def ensure_data_file(reset=False):
    """Create the data file (with header) if it doesn't exist yet,
    or if the caller explicitly asked for a clean slate."""
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    if reset or not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", newline="", encoding="utf-8") as data_file:
            writer = csv.DictWriter(data_file, fieldnames=FIELDNAMES)
            writer.writeheader()


def record_measurements(config, reset=False):
    """Measure every configured metric once and append the results
    to permanent storage (disk). Existing data is never overwritten,
    unless --reset was explicitly given."""
    ensure_data_file(reset=reset)
    host = config["host"]
    timestamp = datetime.now().isoformat(timespec="seconds")

    rows = []
    for metric in config["metrics"]:
        measure = METRIC_FUNCTIONS.get(metric)
        if measure is None:
            print(f"Warning: unknown metric '{metric}', skipping.")
            continue
        value = measure()
        rows.append({
            "timestamp": timestamp,
            "hostname": host["hostname"],
            "ip_address": host["ip_address"],
            "metric": metric,
            "value": value,
        })

    with open(DATA_FILE, "a", newline="", encoding="utf-8") as data_file:
        writer = csv.DictWriter(data_file, fieldnames=FIELDNAMES)
        writer.writerows(rows)

    print(f"Recorded {len(rows)} measurement(s) at {timestamp}.")


def _in_range(row, start, end):
    row_time = datetime.fromisoformat(row["timestamp"])
    if start and row_time < start:
        return False
    if end and row_time > end:
        return False
    return True


def report_measurements(start=None, end=None, show_stats=False):
    """Read stored measurements from disk, optionally filter them by a
    start/end time window, and display them in a well-formatted table."""
    if not os.path.exists(DATA_FILE):
        print("No data recorded yet.")
        return

    with open(DATA_FILE, "r", newline="", encoding="utf-8") as data_file:
        rows = list(csv.DictReader(data_file))

    filtered = [row for row in rows if _in_range(row, start, end)]

    print(f"{'Timestamp':20} {'Hostname':15} {'Metric':20} {'Value':>10}")
    print("-" * 68)
    for row in filtered:
        print(f"{row['timestamp']:20} {row['hostname']:15} {row['metric']:20} {row['value']:>10}")

    if show_stats and filtered:
        by_metric = {}
        for row in filtered:
            by_metric.setdefault(row["metric"], []).append(float(row["value"]))
        print("\nStatistics:")
        for metric, values in by_metric.items():
            average = sum(values) / len(values)
            print(f"  {metric}: count={len(values)} avg={average:.2f} total={sum(values):.2f}")


def parse_args():
    parser = argparse.ArgumentParser(description="Knowledge Hub system monitor")
    subparsers = parser.add_subparsers(dest="mode", required=True)

    record_parser = subparsers.add_parser("record", help="Perform and store measurements")
    record_parser.add_argument("--config", required=True, help="Path to JSON config file")
    record_parser.add_argument("--reset", action="store_true", help="Start with a clean data file")

    report_parser = subparsers.add_parser("report", help="Retrieve and display stored measurements")
    report_parser.add_argument("--start", help="Start date/time (YYYY-MM-DDTHH:MM:SS)")
    report_parser.add_argument("--end", help="End date/time (YYYY-MM-DDTHH:MM:SS)")
    report_parser.add_argument("--stats", action="store_true", help="Show average/total per metric")

    return parser.parse_args()


def main():
    args = parse_args()
    if args.mode == "record":
        config = load_config(args.config)
        record_measurements(config, reset=args.reset)
    elif args.mode == "report":
        start = datetime.fromisoformat(args.start) if args.start else None
        end = datetime.fromisoformat(args.end) if args.end else None
        report_measurements(start=start, end=end, show_stats=args.stats)


if __name__ == "__main__":
    main()
