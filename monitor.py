"""
monitor.py - Week 3 (version 4)
Knowledge Hub system monitor.

Measures CPU, memory and disk usage, stores them in a SQLite3 database
and reports stored measurements over a chosen time period. The tool never
asks for input, so it can run on a schedule. Everything it does is also
written to monitor.log.

Usage:
    python monitor.py record --config config.json
    python monitor.py record --config config.json --reset
    python monitor.py report
    python monitor.py report --start 2026-10-01T00:00:00 --stats
    python monitor.py --help
"""

import argparse
import json
import logging
import os
import sqlite3
import sys
from datetime import datetime

import psutil

DB_FILE = "data/monitoring.db"
LOG_FILE = "monitor.log"

# Maps a metric name (as used in the config file) to the function that
# measures it. A new metric only needs one new line here.
METRIC_FUNCTIONS = {
    "cpu_usage": lambda: psutil.cpu_percent(interval=1),
    "memory_usage": lambda: psutil.virtual_memory().percent,
    "disk_root_usage": lambda: psutil.disk_usage("/").percent,
}


def setup_logging():
    """Write log lines with date, time and level to monitor.log."""
    logging.basicConfig(
        filename=LOG_FILE,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )


def load_config(path):
    """Load the host information and metric list from a JSON file."""
    with open(path, "r", encoding="utf-8") as config_file:
        return json.load(config_file)


def get_connection():
    """Open the SQLite3 database and create the table if needed."""
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
    """Delete the database so recording starts with a clean slate."""
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)
    logging.warning("Database reset, all stored data deleted")
    print("Database reset - starting with a clean slate.")


def record_measurements(config, reset=False):
    """Measure every configured metric once and add it to the database.

    Existing data is never overwritten, unless --reset is given.
    """
    if reset:
        reset_database()

    connection = get_connection()
    host = config["host"]
    timestamp = datetime.now().isoformat(timespec="seconds")

    count = 0
    for metric in config["metrics"]:
        measure = METRIC_FUNCTIONS.get(metric)
        if measure is None:
            logging.warning("Unknown metric '%s' skipped", metric)
            print(f"Warning: unknown metric '{metric}', skipping.")
            continue
        value = measure()
        connection.execute(
            "INSERT INTO measurements "
            "(timestamp, hostname, ip_address, metric, value) "
            "VALUES (?, ?, ?, ?, ?)",
            (timestamp, host["hostname"], host["ip_address"], metric, value),
        )
        logging.info("Recorded %s = %.2f on %s", metric, value,
                     host["hostname"])
        count += 1

    connection.commit()
    connection.close()
    print(f"Recorded {count} measurement(s) at {timestamp}.")


def report_measurements(start=None, end=None, show_stats=False):
    """Show stored measurements, optionally between a start and end time."""
    connection = get_connection()
    query = ("SELECT timestamp, hostname, metric, value "
             "FROM measurements WHERE 1=1")
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
    logging.info("Report requested, %d rows found", len(rows))

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
            print(f"  {metric}: count={len(values)} "
                  f"avg={average:.2f} total={sum(values):.2f}")


def parse_time(text, option):
    """Turn user input into a datetime, or stop with a clear message."""
    try:
        return datetime.fromisoformat(text) if text else None
    except ValueError:
        logging.error("Invalid date for %s: %s", option, text)
        print(f"Error: {option} must look like 2026-10-01T00:00:00 "
              f"(got '{text}').")
        sys.exit(1)


def parse_args():
    """Define the command-line options (argparse also builds --help)."""
    parser = argparse.ArgumentParser(
        description="Knowledge Hub system monitor")
    subparsers = parser.add_subparsers(dest="mode", required=True)

    record = subparsers.add_parser(
        "record", help="Measure and store the configured metrics")
    record.add_argument("--config", required=True,
                        help="Path to the JSON config file")
    record.add_argument("--reset", action="store_true",
                        help="Delete all stored data first")

    report = subparsers.add_parser(
        "report", help="Show stored measurements")
    report.add_argument("--start", help="From (YYYY-MM-DDTHH:MM:SS)")
    report.add_argument("--end", help="Until (YYYY-MM-DDTHH:MM:SS)")
    report.add_argument("--stats", action="store_true",
                        help="Show average and total per metric")
    return parser.parse_args()


def main():
    """Run the chosen mode and report errors clearly."""
    setup_logging()
    args = parse_args()
    try:
        if args.mode == "record":
            record_measurements(load_config(args.config), reset=args.reset)
        else:
            report_measurements(
                start=parse_time(args.start, "--start"),
                end=parse_time(args.end, "--end"),
                show_stats=args.stats)
    except FileNotFoundError:
        logging.error("Config file not found: %s", args.config)
        print(f"Error: config file '{args.config}' not found.")
        sys.exit(1)
    except (KeyError, json.JSONDecodeError) as error:
        logging.error("Config file problem: %s", error)
        print(f"Error: the config file is not valid ({error}).")
        sys.exit(1)


if __name__ == "__main__":
    main()
