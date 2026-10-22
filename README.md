# Knowledge Hub - System Monitor

A command-line Python application for monitoring system metrics (CPU,
memory, disk usage, etc.) on the Knowledge Hub infrastructure, built
incrementally across Tasks 5, 10 and 11.

## What it does

The script has two modes, chosen on the command line:

- **`record`** - measures each configured metric once (using the
  `psutil` library) and stores the result permanently, together with a
  timestamp, hostname and IP address.
- **`report`** - reads stored measurements back out, optionally
  filtered by a start/end time window, displays them in a table, and
  can show average/total statistics per metric.

The application never asks for interactive input - all configuration
comes from a JSON config file (`--config`) or command-line flags, so it
can be run unattended or on a schedule (e.g. a cron job / scheduled
task that calls `monitor.py record` every few minutes).

## How data is collected

Metrics are measured using the `psutil` module:

| Metric name        | How it's measured                        |
|---------------------|-------------------------------------------|
| `cpu_usage`         | `psutil.cpu_percent(interval=1)`           |
| `memory_usage`      | `psutil.virtual_memory().percent`          |
| `disk_root_usage`   | `psutil.disk_usage("/").percent`           |

New metrics can be added by extending the `METRIC_FUNCTIONS` dictionary
at the top of `monitor.py`.

## Output / storage format

All measurements are stored permanently in a local **SQLite3**
database at `data/monitoring.db`, in a single table:

```sql
CREATE TABLE measurements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,     -- ISO 8601, e.g. 2026-10-04T15:42:00
    hostname TEXT NOT NULL,
    ip_address TEXT NOT NULL,
    metric TEXT NOT NULL,
    value REAL NOT NULL
);
```

Recording only ever **appends** new rows - existing data is never
overwritten unless `--reset` is explicitly passed, in which case the
database file is deleted and recreated empty before the new
measurements are written.

The `report` command prints a formatted table to the terminal, for
example:

```
Timestamp            Hostname        Metric                    Value
--------------------------------------------------------------------
2026-10-04T15:42:00  monitor-server  cpu_usage                  4.20
2026-10-04T15:42:00  monitor-server  memory_usage               38.50
2026-10-04T15:42:00  monitor-server  disk_root_usage            61.00

Statistics:
  cpu_usage: count=1 avg=4.20 total=4.20
  memory_usage: count=1 avg=38.50 total=38.50
  disk_root_usage: count=1 avg=61.00 total=61.00
```

## How to run

1. Install dependencies (Python 3.12+ required):
   ```bash
   pip install -r requirements.txt
   ```

2. Copy and edit the example config to describe the system and metrics
   to monitor:
   ```bash
   cp config.example.json config.json
   ```

3. Record a set of measurements:
   ```bash
   python monitor.py record --config config.json
   ```
   Add `--reset` to start the database from a clean slate.

4. View stored measurements:
   ```bash
   python monitor.py report
   python monitor.py report --start 2026-10-01T00:00:00 --end 2026-10-04T23:59:59 --stats
   ```

## Project history (Tasks 5 -> 10 -> 11)

- **Task 5** - interactive prototype, in-memory only (see git history,
  first commit).
- **Task 10** - rewritten as a non-interactive, config-driven CLI app
  with append-only CSV file storage and a `report` mode.
- **Task 11** - storage migrated from CSV to a local SQLite3 database,
  documentation added (this file).
