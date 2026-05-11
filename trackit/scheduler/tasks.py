"""Celery task scheduler for snapshot and report jobs"""
import logging, os
from datetime import datetime, timedelta
from celery import shared_task
from django.utils import timezone
from django.db.models import Q, Max
from core.models import Filter, TicketSnapshot, EmailToken
from utils.jira_service import JiraService
from utils.snapshot_service import SnapshotService
from utils.analytics_service import AnalyticsService
from utils.email_service import EmailService
from utils.token_service import TokenService
from django.conf import settings
logger = logging.getLogger(__name__)


@shared_task
def hourly_snapshot_job():
    """
    Hourly Job: Capture ONLY NEW tickets that appeared since yesterday 9 PM
    
    Purpose: Catch tickets that are created AND closed within 24 hours
    These tickets would be lost if we only compare 9 PM snapshots.
    
    Process:
    1. Get yesterday's 9 PM baseline snapshot
    2. Fetch current tickets from Jira
    3. Find tickets NOT in yesterday's baseline (truly new)
    4. Create snapshots ONLY for these new tickets
    5. This prevents duplicate tracking of existing tickets
    """
    try:
        logger.info("Starting hourly snapshot job...")
        
        from datetime import timedelta, date
        
        filters = Filter.objects.filter(active=True)
        new_tickets_captured = 0
        
        today = date.today()
        yesterday = today - timedelta(days=1)
        
        for filter_instance in filters:
            try:
                # Get yesterday's 9 PM baseline
                yesterday_snapshot = TicketSnapshot.objects.filter(
                    filter=filter_instance,
                    created_at__date=yesterday
                ).order_by('-created_at').first()
                
                if not yesterday_snapshot:
                    logger.info(f"⏭️  No baseline for {filter_instance.name}, skipping hourly snapshot")
                    continue
                
                # Get baseline ticket IDs
                yesterday_baseline = set(
                    TicketSnapshot.objects.filter(
                        filter=filter_instance,
                        created_at__date=yesterday
                    ).values_list('ticket_id', flat=True)
                )
                
                # Fetch current tickets from Jira
                jira_service = JiraService()
                current_tickets = jira_service.fetch_filter_tickets(filter_instance.jira_filter_id)
                
                # Find NEW tickets (not in yesterday's baseline)
                current_ids = set(t['ticket_id'] for t in current_tickets)
                new_ticket_ids = current_ids - yesterday_baseline
                
                if not new_ticket_ids:
                    logger.info(f"✓ No new tickets for {filter_instance.name} this hour")
                    continue
                
                # Create snapshots ONLY for new tickets
                new_snapshots = []
                for ticket in current_tickets:
                    if ticket['ticket_id'] in new_ticket_ids:
                        snapshot = TicketSnapshot(
                            filter=filter_instance,
                            ticket_id=ticket['ticket_id'],
                            title=ticket['title'],
                            assignee=ticket['assignee'],
                            status=ticket['status'],
                            priority=ticket.get('priority', 'Unknown'),
                            updated=datetime.fromisoformat(ticket['updated'].replace('Z', '+00:00')),
                            snapshot_date=timezone.now().date(),
                            snapshot_json=ticket,
                        )
                        new_snapshots.append(snapshot)
                
                # Bulk create only new tickets
                TicketSnapshot.objects.bulk_create(new_snapshots, batch_size=100)
                new_tickets_captured += len(new_snapshots)
                logger.info(f"✓ Hourly snapshot: {len(new_snapshots)} NEW tickets for {filter_instance.name}")
                
            except Exception as e:
                logger.error(f"Failed hourly snapshot for {filter_instance.name}: {str(e)}")
                continue
        
        logger.info(f"Hourly snapshot job completed: {new_tickets_captured} new tickets captured")
        return {
            'status': 'success',
            'new_tickets': new_tickets_captured,
        }
        
    except Exception as e:
        logger.error(f"Hourly snapshot job failed: {str(e)}")
        return {'status': 'error', 'message': str(e)}


@shared_task
def snapshot_job():
    """DEPRECATED: This job is no longer used.
    
    All snapshot and reporting is now done by report_job at 9 PM.
    report_job compares yesterday's 9 PM snapshot with today's 9 PM snapshot
    for a full 24-hour comparison.
    """
    logger.info("snapshot_job is deprecated - all snapshots taken at report time")
    return {
        'status': 'skipped',
        'message': 'snapshot_job deprecated - report_job handles all snapshots',
    }


@shared_task
def reminder_job():
    """
    6 PM Job: Send reminders to assignees with CURRENT active tickets
    - Fetch current tickets from Jira (not baseline from 10 AM)
    - This ensures moved/resolved tickets are excluded
    - Send one consolidated email per assignee
    """
    try:
        logger.info("Starting reminder job at 6 PM...")
        
        filters = Filter.objects.filter(active=True)
        email_count = 0
        
        for filter_instance in filters:
            try:
                # Fetch CURRENT tickets from Jira (not baseline snapshots)
                # This ensures we only remind about tickets still in the filter
                from utils.jira_service import JiraService
                jira_service = JiraService()
                current_tickets = jira_service.fetch_filter_tickets(filter_instance.jira_filter_id)
                
                if not current_tickets:
                    logger.warning(f"No current tickets found for filter {filter_instance.name}")
                    continue
                
                # Group tickets by assignee
                assignees_tickets = {}
                for ticket in current_tickets:
                    assignee = ticket['assignee']
                    if assignee not in assignees_tickets:
                        assignees_tickets[assignee] = []
                    assignees_tickets[assignee].append(ticket)
                
                logger.info(f"Filter {filter_instance.name}: Found {len(assignees_tickets)} assignees with tickets")
                
                # Track sent emails to avoid duplicates
                sent_emails = set()
                
                for assignee, tickets in assignees_tickets.items():
                    # Skip if already sent email to this assignee
                    if assignee in sent_emails:
                        logger.info(f"Skipping duplicate email for {assignee}")
                        continue
                    
                    try:
                        ticket_count = len(tickets)
                        logger.info(f"Assignee {assignee}: {ticket_count} tickets")
                        
                        if ticket_count == 0:
                            continue
                        
                        # Build consolidated ticket list from CURRENT Jira tickets
                        ticket_list = [
                            {
                                'ticket_id': t['ticket_id'], 
                                'title': t['title'],
                                'status': t['status'],
                                'priority': t.get('priority', 'Unknown')
                            }
                            for t in tickets
                        ]
                        
                        # Generate SINGLE token for this assignee
                        from utils.token_service import TokenService
                        token = TokenService.generate_token(filter_instance.id, assignee)
                        
                        # Save token - delete old ones first to avoid duplicates
                        from datetime import timedelta
                        from core.models import EmailToken
                        
                        # Delete any stale tokens for this assignee/filter to avoid duplicates
                        old_tokens = EmailToken.objects.filter(
                            assignee_email=assignee,
                            filter=filter_instance
                        )
                        old_count = old_tokens.count()
                        if old_count > 0:
                            old_tokens.delete()
                            logger.info(f"Deleted {old_count} old tokens for {assignee}")
                        
                        # Create fresh token
                        email_token = EmailToken.objects.create(
                            assignee_email=assignee,
                            token=token,
                            filter=filter_instance,
                            expires_at=timezone.now() + timedelta(hours=15),
                        )
                        logger.info(f"Created token for {assignee}: {token[:10]}...")
                        
                        # Build update link
                        update_link = f"{os.environ.get('UI_DOMAIN','http://localhost:8000')}/update/{token}"
                        
                        # Send ONE consolidated email with ALL CURRENT tickets
                        logger.info(f"Sending reminder email to {assignee} with {ticket_count} tickets")
                        success = EmailService.send_reminder_email(
                            assignee_name=assignee,
                            assignee_email=assignee,
                            tickets=ticket_list,
                            update_link=update_link,
                            filter_name=filter_instance.name
                        )
                        
                        if success:
                            email_count += 1
                            sent_emails.add(assignee)  # Mark as sent
                            logger.info(f"✓ Reminder email sent to {assignee}")
                        else:
                            logger.error(f"✗ Reminder email failed for {assignee}")
                    
                    except Exception as e:
                        logger.error(f"Failed to send reminder to {assignee}: {str(e)}")
                        import traceback
                        traceback.print_exc()
                        continue
            
            except Exception as e:
                logger.error(f"Failed to process filter {filter_instance.name}: {str(e)}")
                continue
        
        logger.info(f"Reminder job completed: {email_count} reminder emails sent")
        return {
            'status': 'success',
            'reminders': email_count,
        }
    
    except Exception as e:
        logger.error(f"Reminder job failed: {str(e)}")
        return {'status': 'error', 'message': str(e)}


@shared_task
def report_job():
    """
    9 PM Job: Generate and send comprehensive reports
    """
    try:
        logger.info("Starting report job at 9 PM...")
        
        from datetime import date, timedelta, datetime
        from core.models import DailyReport, TicketSnapshot
        
        filters = Filter.objects.filter(active=True)
        report_count = 0
        
        today = date.today()
        yesterday = today - timedelta(days=1)
        
        for filter_instance in filters:
            try:
                logger.info(f"Processing report for filter: {filter_instance.name}")
                
                # Check if report already created today (idempotency check)
                existing_report = DailyReport.objects.filter(
                    filter=filter_instance,
                    report_date=today
                ).first()
                
                if existing_report:
                    logger.warning(f"Report already exists for {filter_instance.name} on {today}, skipping")
                    continue
                
                # Get yesterday's snapshot (baseline from 9 PM yesterday)
                yesterday_snapshot = TicketSnapshot.objects.filter(
                    filter=filter_instance,
                    created_at__date=yesterday
                ).order_by('-created_at').first()
                
                if not yesterday_snapshot:
                    # Skip report if yesterday's baseline is missing
                    # But still create today's snapshot for tomorrow's use
                    logger.warning(f"Yesterday's snapshot missing for {filter_instance.name} ({yesterday}), skipping report but creating today's snapshot")
                    jira_service = JiraService()
                    today_count = SnapshotService.create_snapshot(filter_instance, jira_service)
                    logger.info(f"✓ Created today's snapshot with {today_count} tickets for {filter_instance.name} (baseline for tomorrow)")
                    continue
                
                # Track which tickets had hourly snapshots (for later cleanup)
                hourly_ticket_ids = set(TicketSnapshot.objects.filter(
                    filter=filter_instance,
                    created_at__date=today
                ).values_list('ticket_id', flat=True))
                
                # Create today's snapshot (final state at 9 PM today)
                jira_service = JiraService()
                today_count = SnapshotService.create_snapshot(filter_instance, jira_service)
                logger.info(f"✓ Created today's snapshot with {today_count} tickets for {filter_instance.name}")
                
                # Get today's snapshot just created
                today_snapshot = TicketSnapshot.objects.filter(
                    filter=filter_instance,
                    created_at__date=today
                ).order_by('-created_at').first()
                
                if not today_snapshot:
                    logger.error(f"Failed to create today's snapshot for {filter_instance.name}")
                    continue
                
                # Compare yesterday vs today snapshots with intermediate tracking
                logger.info(f"Comparing snapshots: {yesterday_snapshot.id} (yesterday) vs {today_snapshot.id} (today)")
                
                # Also capture any tickets that appeared in intermediate snapshots
                # These are tickets created after yesterday's 9 PM but before today's 9 PM
                yesterday_9pm = yesterday_snapshot.created_at
                today_9pm = today_snapshot.created_at
                
                SnapshotService.compare_24hour_snapshots_with_tracking(
                    filter_instance, 
                    yesterday_snapshot, 
                    today_snapshot,
                    yesterday_9pm,
                    today_9pm
                )
                logger.info(f"✓ 24-hour snapshots compared for {filter_instance.name}")
                
                # Compute daily analytics (BEFORE cleanup so it can use all snapshots)
                AnalyticsService.compute_daily_analytics(filter_instance, analytics_date=today)
                logger.info(f"✓ Analytics computed for {filter_instance.name}")
                
                # Cleanup: Remove hourly snapshots, keep only latest 9 PM snapshots
                # Delete all snapshots of tickets that had hourly snapshots
                if hourly_ticket_ids:
                    deleted_count = TicketSnapshot.objects.filter(
                        filter=filter_instance,
                        created_at__date=today,
                        ticket_id__in=hourly_ticket_ids
                    ).exclude(
                        # Keep only the latest snapshot for each ticket (from 9 PM batch)
                        id__in=TicketSnapshot.objects.filter(
                            filter=filter_instance,
                            created_at__date=today,
                            ticket_id__in=hourly_ticket_ids
                        ).values('ticket_id').annotate(max_id=Max('id')).values('max_id')
                    ).count()
                    
                    TicketSnapshot.objects.filter(
                        filter=filter_instance,
                        created_at__date=today,
                        ticket_id__in=hourly_ticket_ids
                    ).exclude(
                        # Keep only the latest snapshot for each ticket (from 9 PM batch)
                        id__in=TicketSnapshot.objects.filter(
                            filter=filter_instance,
                            created_at__date=today,
                            ticket_id__in=hourly_ticket_ids
                        ).values('ticket_id').annotate(max_id=Max('id')).values('max_id')
                    ).delete()
                    logger.info(f"✓ Deleted {deleted_count} hourly snapshots for new tickets: {list(hourly_ticket_ids)}")
                
                # Cleanup: Remove Done/Resolved tickets from final 9 PM snapshot
                # Only keep active tickets (status != 'Done')
                done_tickets = TicketSnapshot.objects.filter(
                    filter=filter_instance,
                    created_at__date=today,
                    status='Done'
                )
                done_ticket_ids = set(done_tickets.values_list('ticket_id', flat=True))
                
                if done_ticket_ids:
                    deleted_done_count = done_tickets.count()
                    done_tickets.delete()
                    logger.info(f"✓ Cleaned up {deleted_done_count} Done ticket snapshots from 9 PM: {list(done_ticket_ids)}")
                else:
                    logger.info("No Done tickets to cleanup")
                
                # Cleanup: Remove tickets no longer in current Jira filter
                # Get current tickets from Jira filter
                current_jira_tickets = jira_service.fetch_filter_tickets(filter_instance.jira_filter_id)
                current_ticket_ids = set(t['ticket_id'] for t in current_jira_tickets)
                
                # Find snapshots for tickets not in current filter
                snapshot_ticket_ids = set(
                    TicketSnapshot.objects.filter(
                        filter=filter_instance,
                        created_at__date=today
                    ).values_list('ticket_id', flat=True).distinct()
                )
                
                removed_from_filter = snapshot_ticket_ids - current_ticket_ids
                if removed_from_filter:
                    deleted_removed_count = TicketSnapshot.objects.filter(
                        filter=filter_instance,
                        created_at__date=today,
                        ticket_id__in=removed_from_filter
                    ).count()
                    
                    TicketSnapshot.objects.filter(
                        filter=filter_instance,
                        created_at__date=today,
                        ticket_id__in=removed_from_filter
                    ).delete()
                    logger.info(f"✓ Cleaned up {deleted_removed_count} tickets no longer in filter: {list(removed_from_filter)}")
                else:
                    logger.info("No tickets removed from filter")
                
                # Generate markdown report
                markdown_report = AnalyticsService.generate_markdown_report(filter_instance, analytics_date=today)
                logger.info(f"✓ Markdown report generated for {filter_instance.name}")
                
                # Send comprehensive report to admin
                success = EmailService.send_report_email(
                    admin_email=filter_instance.admin_email,
                    filter_name=filter_instance.name,
                    markdown_content=markdown_report,
                    report_date=today.isoformat()
                )
                
                if success:
                    report_count += 1
                    logger.info(f"✓ Report email sent to {filter_instance.admin_email}")
                    
                    # Mark report as sent
                    DailyReport.objects.filter(
                        filter=filter_instance,
                        report_date=today
                    ).update(sent_at=timezone.now())
                else:
                    logger.error(f"✗ Failed to send report email for {filter_instance.name}")
                
                # Send report to Microsoft Teams (if configured)
                if settings.TEAMS_WEBHOOK_URL:
                    try:
                        from core.models import DailyAnalytics, SnapshotComparison
                        from utils.teams_service import TeamsService
                        
                        analytics = DailyAnalytics.objects.filter(
                            filter=filter_instance,
                            analytics_date=today
                        ).first()
                        
                        comparison = SnapshotComparison.objects.filter(
                            filter=filter_instance,
                            comparison_date=today
                        ).first()
                        
                        if analytics and comparison:
                            teams_service = TeamsService()
                            
                            # Extract top contributors and awaiting assignees from analytics
                            top_contributors = sorted(
                                [(name, metrics['tickets']) for name, metrics in analytics.assignee_metrics.items()],
                                key=lambda x: x[1],
                                reverse=True
                            )[:3]
                            
                            # Send formatted Teams card
                            teams_success = teams_service.send_report_card(
                                filter_name=filter_instance.name,
                                report_date=today.strftime('%d %B %Y'),
                                total_tickets=analytics.total_tickets,
                                updated_count=analytics.updated_count,
                                pending_count=analytics.missed_count,
                                new_tickets=len(comparison.new_tickets or []),
                                resolved_count=len(comparison.removed_tickets or []),
                                compliance=analytics.analytics_data.get('compliance_rate', 0),
                                top_contributors=top_contributors,
                                awaiting_assignees=analytics.no_update_assignees
                            )
                            
                            if teams_success:
                                logger.info(f"✓ Report sent to Teams for {filter_instance.name}")
                            else:
                                logger.info(f"Teams notification skipped or failed for {filter_instance.name}")
                    
                    except Exception as e:
                        logger.warning(f"Failed to send Teams notification for {filter_instance.name}: {str(e)}")
            
            except Exception as e:
                logger.error(f"Failed to generate report for {filter_instance.name}: {str(e)}")
                import traceback
                traceback.print_exc()
                continue
        
        logger.info(f"Report job completed: {report_count} reports sent")
        
        # Expire all tokens after report is sent (no more updates allowed)
        try:
            from core.models import EmailToken
            from django.utils import timezone as tz
            expired_count = EmailToken.objects.filter(
                expires_at__gt=tz.now()
            ).update(expires_at=tz.now())
            logger.info(f"✓ Expired {expired_count} tokens after report generation")
        except Exception as e:
            logger.error(f"Failed to expire tokens: {str(e)}")
        
        return {
            'status': 'success',
            'reports': report_count,
        }
    
    except Exception as e:
        logger.error(f"Report job failed: {str(e)}")
        return {'status': 'error', 'message': str(e)}
        return {'status': 'error', 'message': str(e)}


@shared_task
def cleanup_expired_tokens():
    """Clean up expired tokens"""
    try:
        from datetime import timedelta
        expired_threshold = timezone.now() - timedelta(days=1)
        
        deleted_count, _ = EmailToken.objects.filter(
            expires_at__lt=expired_threshold
        ).delete()
        
        logger.info(f"Cleaned up {deleted_count} expired tokens")
        return {'status': 'success', 'deleted': deleted_count}
    
    except Exception as e:
        logger.error(f"Token cleanup failed: {str(e)}")
        return {'status': 'error', 'message': str(e)}
