"""
monitor.py - Week 1 (Task 5)
Python Environment Setup & Initial Scripting

Allows the user to interactively enter details about the system that
should be monitored, and the metrics that should be tracked for it.

For this first iteration, everything is kept in memory only - there is
no permanent storage yet. That is added in later weeks (Task 10/11).
"""


def get_system_info():
    """Ask the user for the identity of the system to be monitored."""
    hostname = input("Enter the hostname of the system to monitor: ").strip()
    ip_address = input("Enter the IP address of the system to monitor: ").strip()
    return {"hostname": hostname, "ip_address": ip_address}


def get_metrics():
    """Ask the user for the list of metrics that should be tracked."""
    print("Enter the metrics you want to monitor, separated by commas.")
    print("Example: cpu_usage, memory_usage, disk_root_usage")
    raw_input_value = input("Metrics: ").strip()
    metrics = [metric.strip() for metric in raw_input_value.split(",") if metric.strip()]
    return metrics


def display_summary(system_info, metrics):
    """Print everything the user entered in a well-formatted way."""
    print("\n" + "=" * 40)
    print("MONITORING CONFIGURATION SUMMARY")
    print("=" * 40)
    print(f"Hostname:    {system_info['hostname']}")
    print(f"IP address:  {system_info['ip_address']}")
    print("Metrics to monitor:")
    if metrics:
        for metric in metrics:
            print(f"  - {metric}")
    else:
        print("  (none entered)")
    print("=" * 40)


def main():
    print("Knowledge Hub - System Monitor (Week 1 prototype)\n")
    system_info = get_system_info()
    metrics = get_metrics()
    display_summary(system_info, metrics)


if __name__ == "__main__":
    main()
