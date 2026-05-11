"""Snapshot Service for managing ticket snapshots"""
import logging
from datetime import datetime, date, timedelta
from django.utils import timezone
from typing import List, Dict, Any
from core.models import TicketSnapshot, SnapshotComparison
from utils.jira_service import JiraService

logger = logging.getLogger(__name__)


class SnapshotService:
    """Service to manage ticket snapshots and comparisons"""
    
    @staticmethod
    def create_snapshot(filter_instance, jira_service: JiraService) -> int:
        """
        Create a snapshot of current Jira tickets for a filter
        
        Args:
            filter_instance: Filter object
            jira_service: JiraService instance
            
        Returns:
            Number of tickets snapshotted
        """
        try:
            # Fetch tickets from Jira
            tickets = jira_service.fetch_filter_tickets(filter_instance.jira_filter_id)
            
            snapshot_count = 0
            
            # Create snapshot records
            snapshots = []
            for ticket in tickets:
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
                snapshots.append(snapshot)
                snapshot_count += 1
            
            # Bulk create snapshots
            TicketSnapshot.objects.bulk_create(snapshots, batch_size=100)
            
            logger.info(f"Created snapshot with {snapshot_count} tickets for filter {filter_instance.name}")
            return snapshot_count
        
        except Exception as e:
            logger.error(f"Failed to create snapshot: {str(e)}")
            raise
            raise
    
    @staticmethod
    def create_fresh_snapshot(filter_instance, jira_service: JiraService) -> int:
        """REMOVED - No longer needed. All snapshots are now identical."""
        raise NotImplementedError("create_fresh_snapshot is deprecated. Use create_snapshot instead.")
    
    @staticmethod
    def compare_snapshots(filter_instance, snapshot_date: date = None) -> Dict[str, Any]:
        """
        Compare today's snapshot with yesterday's
        
        Args:
            filter_instance: Filter object
            snapshot_date: Date to compare (defaults to today)
            
        Returns:
            Dictionary with comparison results
        """
        try:
            if snapshot_date is None:
                snapshot_date = timezone.now().date()
            
            # Get today's and yesterday's snapshots
            from datetime import timedelta
            yesterday = snapshot_date - timedelta(days=1)
            
            today_snapshots = TicketSnapshot.objects.filter(
                filter=filter_instance,
                snapshot_date=snapshot_date
            )
            
            yesterday_snapshots = TicketSnapshot.objects.filter(
                filter=filter_instance,
                snapshot_date=yesterday
            )
            
            # Extract ticket IDs
            today_tickets = {s.ticket_id: s for s in today_snapshots}
            yesterday_tickets = {s.ticket_id: s for s in yesterday_snapshots}
            
            today_ids = set(today_tickets.keys())
            yesterday_ids = set(yesterday_tickets.keys())
            
            # Find differences
            new_tickets = list(today_ids - yesterday_ids)
            removed_tickets = list(yesterday_ids - today_ids)
            
            # Find status changes
            status_changes = {}
            for ticket_id in today_ids & yesterday_ids:
                today_status = today_tickets[ticket_id].status
                yesterday_status = yesterday_tickets[ticket_id].status
                
                if today_status != yesterday_status:
                    status_changes[ticket_id] = {
                        'yesterday': yesterday_status,
                        'today': today_status,
                    }
            
            result = {
                'new_tickets': new_tickets,
                'removed_tickets': removed_tickets,
                'status_changes': status_changes,
                'total_today': len(today_ids),
                'total_yesterday': len(yesterday_ids),
            }
            
            # Save comparison
            SnapshotComparison.objects.update_or_create(
                filter=filter_instance,
                comparison_date=snapshot_date,
                defaults={
                    'new_tickets': new_tickets,
                    'removed_tickets': removed_tickets,
                    'status_changes': status_changes,
                }
            )
            
            logger.info(f"Comparison created: New={len(new_tickets)}, Removed={len(removed_tickets)}, Changes={len(status_changes)}")
            return result
        
        except Exception as e:
            logger.error(f"Failed to compare snapshots: {str(e)}")
            raise
    
    @staticmethod
    def get_assignee_tickets(filter_instance, assignee: str, snapshot_date: date = None) -> List[Dict[str, Any]]:
        """
        Get all tickets for a specific assignee
        
        Args:
            filter_instance: Filter object
            assignee: Assignee name
            snapshot_date: Date to fetch from (defaults to today)
            
        Returns:
            List of ticket dictionaries
        """
        try:
            if snapshot_date is None:
                snapshot_date = timezone.now().date()
            
            snapshots = TicketSnapshot.objects.filter(
                filter=filter_instance,
                assignee=assignee,
                snapshot_date=snapshot_date
            )
            
            tickets = []
            for snapshot in snapshots:
                tickets.append({
                    'ticket_id': snapshot.ticket_id,
                    'title': snapshot.title,
                    'status': snapshot.status,
                    'priority': snapshot.priority,
                    'updated': snapshot.updated,
                })
            
            return tickets
        
        except Exception as e:
            logger.error(f"Failed to get assignee tickets: {str(e)}")
            raise
    
    @staticmethod
    def compare_24hour_snapshots(filter_instance, yesterday_snapshot: TicketSnapshot, today_snapshot: TicketSnapshot) -> Dict[str, Any]:
        """
        Compare yesterday's snapshot (9 PM) with today's snapshot (9 PM)
        - NEW TICKETS: in today's snapshot but not in yesterday's
        - RESOLVED TICKETS: in yesterday's snapshot but not in today's
        - STATUS CHANGES: tickets in both with status change
        
        Args:
            filter_instance: Filter object
            yesterday_snapshot: Yesterday's TicketSnapshot object
            today_snapshot: Today's TicketSnapshot object
            
        Returns:
            Dictionary with comparison results
        """
        try:
            # Get all tickets from both snapshots
            yesterday_tickets = TicketSnapshot.objects.filter(
                filter=filter_instance,
                created_at__date=yesterday_snapshot.created_at.date(),
                id=yesterday_snapshot.id
            ).first()
            
            today_tickets = TicketSnapshot.objects.filter(
                filter=filter_instance,
                created_at__date=today_snapshot.created_at.date(),
                id=today_snapshot.id
            ).first()
            
            if not yesterday_tickets or not today_tickets:
                logger.error("One of the snapshots is missing")
                return {
                    'new_tickets': [],
                    'resolved_tickets': [],
                    'status_changes': {},
                    'yesterday_total': 0,
                    'today_total': 0,
                }
            
            # Get all tickets for the dates
            yesterday_records = TicketSnapshot.objects.filter(
                filter=filter_instance,
                created_at__date=yesterday_snapshot.created_at.date()
            )
            
            today_records = TicketSnapshot.objects.filter(
                filter=filter_instance,
                created_at__date=today_snapshot.created_at.date()
            )
            
            # Extract ticket IDs and status
            yesterday_dict = {s.ticket_id: s for s in yesterday_records}
            today_dict = {s.ticket_id: s for s in today_records}
            
            yesterday_ids = set(yesterday_dict.keys())
            today_ids = set(today_dict.keys())
            
            # Find differences
            new_tickets = list(today_ids - yesterday_ids)  # In today but not yesterday
            resolved_tickets = list(yesterday_ids - today_ids)  # In yesterday but not today
            
            # Find status changes
            status_changes = {}
            for ticket_id in yesterday_ids & today_ids:
                yesterday_status = yesterday_dict[ticket_id].status
                today_status = today_dict[ticket_id].status
                
                if yesterday_status != today_status:
                    status_changes[ticket_id] = {
                        'yesterday': yesterday_status,
                        'today': today_status,
                    }
            
            result = {
                'new_tickets': new_tickets,
                'resolved_tickets': resolved_tickets,
                'status_changes': status_changes,
                'yesterday_total': len(yesterday_ids),
                'today_total': len(today_ids),
            }
            
            # Save comparison
            from datetime import date
            report_date = today_snapshot.created_at.date()
            SnapshotComparison.objects.update_or_create(
                filter=filter_instance,
                comparison_date=report_date,
                defaults={
                    'new_tickets': new_tickets,
                    'removed_tickets': resolved_tickets,
                    'status_changes': status_changes,
                }
            )
            
            logger.info(f"24-hour comparison: New={len(new_tickets)}, Resolved={len(resolved_tickets)}, Changes={len(status_changes)}")
            return result
        
        except Exception as e:
            logger.error(f"Failed to compare 24-hour snapshots: {str(e)}")
            raise
    
    @staticmethod
    def compare_24hour_snapshots_with_tracking(
        filter_instance, 
        yesterday_snapshot: TicketSnapshot, 
        today_snapshot: TicketSnapshot,
        yesterday_9pm,
        today_9pm
    ) -> Dict[str, Any]:
        """
        Compare snapshots with tracking of tickets created between 9 PM windows
        
        This prevents losing tickets that are created AND closed within 24 hours.
        
        Algorithm:
        1. Get all snapshots from yesterday 9 PM to today 9 PM
        2. Find tickets that first appeared AFTER yesterday's 9 PM (new tickets)
        3. Find tickets that appeared yesterday 9 PM but NOT today 9 PM (resolved)
        
        Args:
            filter_instance: Filter object
            yesterday_snapshot: Yesterday's 9 PM snapshot
            today_snapshot: Today's 9 PM snapshot
            yesterday_9pm: Datetime of yesterday's 9 PM snapshot
            today_9pm: Datetime of today's 9 PM snapshot
            
        Returns:
            Dictionary with comparison results
        """
        try:
            # Get baseline: tickets present at yesterday 9 PM (within 1 second window)
            yesterday_records = TicketSnapshot.objects.filter(
                filter=filter_instance,
                created_at__gte=yesterday_9pm - timedelta(seconds=1),
                created_at__lte=yesterday_9pm + timedelta(seconds=1)
            )
            yesterday_dict = {s.ticket_id: s for s in yesterday_records}
            yesterday_ids = set(yesterday_dict.keys())
            
            # Get all snapshots between yesterday 9 PM and today 9 PM (inclusive)
            all_intermediate_snapshots = TicketSnapshot.objects.filter(
                filter=filter_instance,
                created_at__gte=yesterday_9pm,
                created_at__lte=today_9pm
            ).order_by('created_at')
            
            # Track first appearance of each ticket
            ticket_first_appearance = {}  # ticket_id -> snapshot_datetime
            ticket_appeared_during_day = set()  # tickets that appeared after yesterday 9 PM
            
            for snapshot in all_intermediate_snapshots:
                if snapshot.ticket_id not in ticket_first_appearance:
                    ticket_first_appearance[snapshot.ticket_id] = snapshot.created_at
                    # If it appeared AFTER yesterday 9 PM, track it as new candidate
                    if snapshot.created_at > yesterday_9pm:
                        ticket_appeared_during_day.add(snapshot.ticket_id)
            
            # Get today's final state (only from 9 PM snapshot, within 1 second window)
            # This ensures we don't include intermediate hourly snapshots
            today_records = TicketSnapshot.objects.filter(
                filter=filter_instance,
                created_at__gte=today_9pm - timedelta(seconds=1),
                created_at__lte=today_9pm + timedelta(seconds=1)
            )
            today_dict = {s.ticket_id: s for s in today_records}
            today_ids = set(today_dict.keys())
            
            # Calculate truly new tickets (appeared today, not in yesterday baseline)
            truly_new_appeared = ticket_appeared_during_day - yesterday_ids
            
            # NEW tickets: any ticket that appeared during day AND NOT in yesterday baseline
            # (even if resolved by 9 PM - we count appearance, not final state)
            new_tickets = list(truly_new_appeared)
            
            # RESOLVED tickets: Any ticket that appeared at any point (yesterday or during day) 
            # but is gone by today 9 PM (includes baseline resolutions AND same-day creations resolved)
            all_appeared = yesterday_ids | ticket_appeared_during_day
            resolved_tickets = list(all_appeared - today_ids)
            
            # Find status changes (between yesterday 9 PM and today 9 PM)
            status_changes = {}
            for ticket_id in yesterday_ids & today_ids:
                yesterday_status = yesterday_dict[ticket_id].status
                today_status = today_dict[ticket_id].status
                
                if yesterday_status != today_status:
                    status_changes[ticket_id] = {
                        'yesterday': yesterday_status,
                        'today': today_status,
                    }
            
            result = {
                'new_tickets': new_tickets,
                'resolved_tickets': resolved_tickets,
                'status_changes': status_changes,
                'yesterday_total': len(yesterday_ids),
                'today_total': len(today_ids),
            }
            
            # Save comparison
            from datetime import date
            report_date = today_snapshot.created_at.date()
            SnapshotComparison.objects.update_or_create(
                filter=filter_instance,
                comparison_date=report_date,
                defaults={
                    'new_tickets': new_tickets,
                    'removed_tickets': resolved_tickets,
                    'status_changes': status_changes,
                }
            )
            
            logger.info(
                f"24-hour tracking comparison: New={len(new_tickets)}, "
                f"Resolved={len(resolved_tickets)} (includes baseline + same-day resolutions), "
                f"Changes={len(status_changes)}, "
                f"Intermediate snapshots tracked={len(all_intermediate_snapshots)}"
            )
            return result
        
        except Exception as e:
            logger.error(f"Failed to compare 24-hour snapshots with tracking: {str(e)}")
            # Fallback to basic comparison if tracking fails
            return SnapshotService.compare_24hour_snapshots(filter_instance, yesterday_snapshot, today_snapshot)
