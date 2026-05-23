#!/usr/bin/env python
"""
Manual job runner — calls hourly_snapshot_job, reminder_job and/or report_job directly.

Usage:
    docker compose exec trackit python run_jobs.py --hourly
    docker compose exec trackit python run_jobs.py --reminder
    docker compose exec trackit python run_jobs.py --report
    docker compose exec trackit python run_jobs.py --all
"""
import os, sys, argparse, django

os.chdir('/app/trackit')
sys.path.insert(0, '/app/trackit')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

import logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s %(name)s: %(message)s')

from datetime import date
from scheduler.tasks import hourly_snapshot_job, reminder_job, report_job, clean_logs_job

SEP = "=" * 70

def run_hourly():
    print(f"\n{SEP}")
    print("RUNNING: hourly_snapshot_job")
    print(SEP)
    result = hourly_snapshot_job()
    print(f"\nResult: {result}")
    print(SEP)

def run_reminder():
    print(f"\n{SEP}")
    print("RUNNING: reminder_job")
    print(SEP)
    result = reminder_job()
    print(f"\nResult: {result}")
    print(SEP)

def run_report():
    print(f"\n{SEP}")
    print("RUNNING: report_job")
    print(SEP)
    result = report_job()
    print(f"\nResult: {result}")
    print(SEP)

def run_clean():
    from core.models import DailyReport, DailyAnalytics, TicketSnapshot
    from core.models import Filter

    today = date.today()
    print(f"\n{SEP}")
    print(f"CLEANING today's data ({today})")
    print(SEP)

    filters = list(Filter.objects.filter(active=True).values_list('name', flat=True))
    print(f"Active filters: {filters}")

    r, _ = DailyReport.objects.filter(report_date=today).delete()
    a, _ = DailyAnalytics.objects.filter(analytics_date=today).delete()
    s, _ = TicketSnapshot.objects.filter(snapshot_date=today).delete()

    print(f"  DailyReport deleted    : {r}")
    print(f"  DailyAnalytics deleted : {a}")
    print(f"  TicketSnapshot deleted : {s}")
    print(f"\n✓ Clean complete — ready to re-run jobs for {today}")
    print(SEP)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Manually trigger TrackIt jobs')
    parser.add_argument('--hourly',   action='store_true', help='Run hourly_snapshot_job')
    parser.add_argument('--reminder', action='store_true', help='Run reminder_job (6 PM emails)')
    parser.add_argument('--report',   action='store_true', help='Run report_job (9 PM report)')
    parser.add_argument('--all',      action='store_true', help='Run hourly → reminder → report')
    parser.add_argument('--clean',    action='store_true', help="Delete today's report, analytics, snapshots")
    parser.add_argument('--logs',     action='store_true', help='Remove log lines older than 3 days from all log files')
    args = parser.parse_args()

    if not any([args.hourly, args.reminder, args.report, args.all, args.clean, args.logs]):
        parser.print_help()
        sys.exit(1)

    if args.clean:
        run_clean()

    if args.logs:
        print(f"\n{SEP}")
        print("RUNNING: clean_logs_job")
        print(SEP)
        result = clean_logs_job()
        print(f"\nResult: {result}")
        print(SEP)

    if args.all or args.hourly:
        run_hourly()

    if args.all or args.reminder:
        run_reminder()

    if args.all or args.report:
        run_report()
