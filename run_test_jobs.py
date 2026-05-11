#!/usr/bin/env python
"""
Direct test of snapshot and report jobs (bypassing Celery queue)
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.insert(0, '/app/trackit')
django.setup()

from scheduler.tasks import hourly_snapshot_job, reminder_job, report_job
from core.models import Filter, TicketSnapshot, DailyReport
from django.utils import timezone

# print("\n" + "="*60)
# print("  TrackIt Manual Job Testing (Direct Execution)")
# print("="*60)

# # Check if any filters exist
# filters = Filter.objects.filter(active=True)
# if not filters.exists():
#     print("\n⚠️  No active filters found!")
#     print("Please create a filter first via the dashboard.")
#     print("="*60 + "\n")
#     sys.exit(1)

# print(f"\n✓ Found {filters.count()} active filter(s):")
# for f in filters:
#     print(f"  - {f.name} (ID: {f.jira_filter_id})")


# # Test Reminder Job
# print("\n" + "="*60)
# print("  Testing Reminder Job (Send Reminders)")
# print("="*60)
# print("\nThis will:")
# print("  1. Get all tickets with pending status (no submission)") 
# print("  2. Send consolidated reminder email per assignee")
# print("  3. Include all their pending tickets\n")

# try:
#     print("Running reminder_job()...")
#     result = reminder_job()
#     print(f"✓ Reminder job completed!")
#     print(f"  Result: {result}\n")
    
# except Exception as e:
#     print(f"✗ Reminder job failed!")
#     print(f"  Error: {str(e)}")
#     import traceback
#     traceback.print_exc()

# # Test Report Job
# print("\n" + "="*60)
# print("  Testing Report Job")
# print("="*60)

try:
    print("Running report_job()...")
    hourly_snapshot_job()
    import time 
    time.sleep(30)
    result = report_job()
    print(f"✓ Report job completed!")
    print(f"  Result: {result}\n")
    
    # Show what was created
    reports = DailyReport.objects.filter(
        report_date=timezone.now().date()
    )
    print(f"✓ Reports generated today: {reports.count()}")
    for r in reports:
        status = "✓ Sent" if r.sent_at else "⏳ Pending"
        print(f"  - {r.filter.name} {status}")
        
except Exception as e:
    print(f"✗ Report job failed!")
    print(f"  Error: {str(e)}")
    import traceback
    traceback.print_exc()

print("\n" + "="*60)
print("  Testing Complete!")
print("="*60)
print("\nNext steps:")
print("  1. Check the Dashboard to see new snapshots")
print("  2. View filter details page to see tickets")
print("  3. Check email inbox for reminder emails (if SMTP configured)")
print("  4. View reports in the dashboard\n")
