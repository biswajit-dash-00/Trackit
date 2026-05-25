"""Snapshot Service for managing ticket snapshots"""
import logging
from datetime import datetime
from django.utils import timezone
from core.models import TicketSnapshot
from utils.jira_service import JiraService

logger = logging.getLogger(__name__)


class SnapshotService:
    """Service to manage ticket snapshots and comparisons"""
    
    @staticmethod
    def create_snapshot(filter_instance, jira_service: JiraService, yesterday_snapshots=None):
        """
        Create a snapshot of current Jira tickets for a filter
        
        Args:
            filter_instance: Filter object
            jira_service: JiraService instance
            yesterday_snapshots: Optional queryset/list of yesterday's TicketSnapshot records
                                 used to carry forward the age counter.
            
        Returns:
            Tuple of (snapshot_count, first_snapshot_instance)
        """
        try:
            # Build age lookup from yesterday's snapshots: ticket_id -> age (int)
            yesterday_age_dict = {}
            if yesterday_snapshots is not None:
                for s in yesterday_snapshots:
                    yesterday_age_dict[s.ticket_id] = s.age

            # Fetch tickets from Jira
            use_qa = 'QA' in filter_instance.name.upper()
            tickets = jira_service.fetch_filter_tickets(filter_instance.jira_filter_id, use_qa_tester=use_qa)
            
            snapshot_count = 0
            first_ticket_id = None
            
            # Create snapshot records
            snapshots = []
            for ticket in tickets:
                if first_ticket_id is None:
                    first_ticket_id = ticket['ticket_id']

                # Compute age: carry forward yesterday's age + 1, or start at 1 for new tickets
                yesterday_age = yesterday_age_dict.get(ticket['ticket_id'])
                age = (yesterday_age + 1) if yesterday_age is not None else 1
                
                snapshot = TicketSnapshot(
                    filter=filter_instance,
                    ticket_id=ticket['ticket_id'],
                    title=ticket['title'],
                    assignee=ticket['assignee'],
                    assignee_email=ticket.get('assignee_email', ''),
                    issue_type=ticket.get('issue_type', ''),
                    status=ticket['status'],
                    priority=ticket.get('priority', 'Unknown'),
                    updated=datetime.fromisoformat(ticket['updated'].replace('Z', '+00:00')),
                    snapshot_date=timezone.now().date(),
                    age=age,
                )
                snapshots.append(snapshot)
                snapshot_count += 1
            
            # Bulk create snapshots
            TicketSnapshot.objects.bulk_create(snapshots, batch_size=100)
            
            # Fetch the first created snapshot instance
            first_snapshot = None
            if first_ticket_id:
                first_snapshot = TicketSnapshot.objects.filter(
                    filter=filter_instance,
                    ticket_id=first_ticket_id,
                    snapshot_date=timezone.now().date()
                ).first()
            
            logger.info(f"Created snapshot with {snapshot_count} tickets for filter {filter_instance.name}")
            return snapshot_count, first_snapshot
        
        except Exception as e:
            logger.error(f"Failed to create snapshot: {str(e)}")
            raise
