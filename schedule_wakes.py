#!/usr/bin/env python3
"""
Schedule Wake Events for Claude Keepalive
Schedules 24 wake events at :55 for the next 24 hours to ensure Mac is awake when keepalive jobs run.
"""
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

LOG_FILE = Path("~/logs/claude_keepalive.log").expanduser()


def log(message: str) -> None:
    """Write timestamped log message to both console and log file."""
    timestamp = datetime.now(timezone.utc).isoformat()
    log_message = f"{timestamp} - [wake-scheduler] {message}"

    # Print to console
    print(log_message)

    # Write to log file
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(f"{log_message}\n")


def clear_existing_wakes() -> bool:
    """Clear all existing scheduled wake events."""
    try:
        log("Clearing existing wake events...")
        subprocess.run(
            ["sudo", "pmset", "schedule", "cancelall"],
            check=True,
            capture_output=True,
            text=True,
        )
        log("✓ Cleared existing wake events")
        return True
    except subprocess.CalledProcessError as e:
        log(f"✗ Failed to clear wake events: {e.stderr}")
        return False


def schedule_wake_event(wake_time: datetime) -> bool:
    """Schedule a single wake event at the specified time."""
    # Format: MM/DD/YY HH:MM:SS
    time_str = wake_time.strftime("%m/%d/%y %H:%M:%S")

    try:
        subprocess.run(
            ["sudo", "pmset", "schedule", "wake", time_str],
            check=True,
            capture_output=True,
            text=True,
        )
        return True
    except subprocess.CalledProcessError as e:
        log(f"✗ Failed to schedule wake at {time_str}: {e.stderr}")
        return False


def schedule_24_hours() -> None:
    """Schedule wake events at :55 for the next 24 hours."""
    log("Starting wake event scheduling for next 24 hours")

    # Clear existing events first
    if not clear_existing_wakes():
        log("✗ Failed to clear existing events, aborting")
        return

    now = datetime.now()
    current_hour = now.replace(minute=55, second=0, microsecond=0)

    # If we're past :55 this hour, start with next hour
    if now.minute >= 55:
        current_hour += timedelta(hours=1)

    scheduled_count = 0
    failed_count = 0

    log(f"Scheduling 24 wake events starting from {current_hour.strftime('%m/%d/%y %H:%M:%S')}")

    for i in range(24):
        wake_time = current_hour + timedelta(hours=i)
        if schedule_wake_event(wake_time):
            scheduled_count += 1
        else:
            failed_count += 1

    log(f"✓ Scheduled {scheduled_count} wake events")
    if failed_count > 0:
        log(f"✗ Failed to schedule {failed_count} wake events")

    log("Wake event scheduling complete")
    log("Verify with: pmset -g sched")


if __name__ == "__main__":
    schedule_24_hours()
