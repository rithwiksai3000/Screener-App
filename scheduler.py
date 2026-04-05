# scheduler.py
# Nightly batch scan scheduler.
# Run this once: python scheduler.py
# It will run the full S&P 500 scan every day at 6:30 PM (after US market close).

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
from src.batch_scanner import run_full_batch, retry_failed
from src.db_setup import setup_database

scheduler = BlockingScheduler(timezone="America/New_York")


def nightly_scan_job():
    print(f"\n[Scheduler] Nightly scan triggered at {datetime.now()}")
    summary = run_full_batch()

    # Auto-retry failures after a 10-min gap
    if summary.get("failed", 0) > 0:
        import time
        print(f"[Scheduler] Waiting 10 min before retrying {summary['failed']} failures...")
        time.sleep(600)
        retry_failed()

    print(f"[Scheduler] Nightly job complete.")


def manual_run():
    """Call this to trigger a scan right now without waiting for the schedule."""
    print("[Manual] Running full batch scan now...")
    run_full_batch()


if __name__ == "__main__":
    import sys

    # First-time setup: ensure all tables exist
    print("[Scheduler] Verifying database tables...")
    setup_database()

    if len(sys.argv) > 1 and sys.argv[1] == "now":
        # python scheduler.py now  →  runs immediately
        manual_run()
    else:
        # Scheduled mode: runs every weekday at 6:30 PM ET
        scheduler.add_job(
            nightly_scan_job,
            trigger=CronTrigger(
                day_of_week="mon-fri",
                hour=18,
                minute=30,
                timezone="America/New_York"
            ),
            id="nightly_scan",
            name="Nightly S&P 500 KPI Scan",
            misfire_grace_time=3600,
        )

        print("\n[Scheduler] Running. Next scan: weekdays at 6:30 PM ET.")
        print("[Scheduler] To run immediately instead: python scheduler.py now")
        print("[Scheduler] Press Ctrl+C to stop.\n")

        try:
            scheduler.start()
        except KeyboardInterrupt:
            print("\n[Scheduler] Stopped.")
