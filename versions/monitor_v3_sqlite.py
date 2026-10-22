"""
monitor.py - Week 3 (Task 11)
Python Monitoring Scripting (Application Basic)

Command-line monitoring application with SQLite3-backed persistent
storage. Configuration (which system to monitor and which metrics to
track) is supplied via a JSON config file - the application never
pauses to ask for interactive input, so it can be scheduled or scripted.

See README.md for the full data model, output/log format and usage
instructions.

Usage:
    python monitor.py record --config config.json
    python monitor.py record --config config.json --reset
    python monitor.py report
    python monitor.py report --start 2026-10-01T00:00:00 --end 2026-10-04T23:59:59 --stats
"""

import argparse
import json
import os
import sqlite3
from datetime import datetime

import psutil

DB_FILE = "data/monitoring.db"

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


def get_connection():
    """Open the SQLite3 database, creating the table if needed."""
    os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
    connection = sqlite3.connect(DB_FILE)
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS measurements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            hostname TEXT NOT NULL,
            ip_address TEXT NOT NULL,
            metric TEXT NOT NULL,
            value REAL NOT NULL
        )
        """
    )
    return connection


def reset_database():
    """Delete the existing database so recording starts with a clean slate."""
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)
    print("Database reset - starting with a clean slate.")


def record_measurements(config, reset=False):
    """Measure every configured metric once and insert the results into
    the SQLite3 database. Existing data is never overwritten, unless
    --reset was explicitly given."""
    if reset:
        reset_database()

    connection = get_connection()
    host = config["host"]
    timestamp = datetime.now().isoformat(timespec="seconds")

    count = 0
    for metric in config["metrics"]:
        measure = METRIC_FUNCTIONS.get(metric)
        if measure is None:
            print(f"Warning: unknown metric '{metric}', skipping.")
            continue
        value = measure()
        connection.execute(
            "INSERT INTO measurements (timestamp, hostname, ip_address, metric, value) "
            "VALUES (?, ?, ?, ?, ?)",
            (timestamp, host["hostname"], host["ip_address"], metric, value),
        )
        count += 1

    connection.commit()
    connection.close()
    print(f"Recorded {count} measurement(s) at {timestamp}.")


def report_measurements(start=None, end=None, show_stats=False):
    """Query stored measurements from the database, optionally filtered
    by a start/end time window, and display them in a well-formatted
    table."""
    connection = get_connection()
    query = "SELECT timestamp, hostname, metric, value FROM measurements WHERE 1=1"
    params = []
    if start:
        query += " AND timestamp >= ?"
        params.append(start.isoformat(timespec="seconds"))
    if end:
        query += " AND timestamp <= ?"
        params.append(end.isoformat(timespec="seconds"))
    query += " ORDER BY timestamp"

    rows = connection.execute(query, params).fetchall()
    connection.close()

    if not rows:
        print("No data found for the given period.")
        return

    print(f"{'Timestamp':20} {'Hostname':15} {'Metric':20} {'Value':>10}")
    print("-" * 68)
    for timestamp, hostname, metric, value in rows:
        print(f"{timestamp:20} {hostname:15} {metric:20} {value:>10.2f}")

    if show_stats:
        by_metric = {}
        for _, _, metric, value in rows:
            by_metric.setdefault(metric, []).append(value)
        print("\nStatistics:")
        for metric, values in by_metric.items():
            average = sum(values) / len(values)
            print(f"  {metric}: count={len(values)} avg={average:.2f} total={sum(values):.2f}")


def parse_args():
    parser = argparse.ArgumentParser(description="Knowledge Hub system monitor")
    subparsers = parser.add_subparsers(dest="mode", required=True)

    record_parser = subparsers.add_parser("record", help="Perform and store measurements")
    record_parser.add_argument("--config", required=True, help="Path to JSON config file")
    record_parser.add_argument("--reset", action="store_true", help="Start with a clean database")

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
