"""Analytics Service for computing metrics and generating insights"""
import logging
import pytz
from datetime import datetime, date, timedelta
from django.utils import timezone
from typing import Dict, Any, List
from core.models import (
    TicketSnapshot, TicketUpdate, SnapshotComparison, 
    DailyAnalytics, DailyReport
)
from markdown import markdown as md_to_html

logger = logging.getLogger(__name__)


class AnalyticsService:
    """Service to compute analytics and generate reports"""
    
    @staticmethod
    def compute_daily_analytics(filter_instance, analytics_date: date = None) -> Dict[str, Any]:
        """
        Compute analytics for a specific day
        
        Args:
            filter_instance: Filter object
            analytics_date: Date to compute analytics for (defaults to today)
            
        Returns:
            Dictionary with computed metrics
        """
        try:
            if analytics_date is None:
                analytics_date = timezone.now().date()
            
            # Get only the FINAL 9 PM snapshot (not intermediate hourly snapshots)
            # This ensures accurate active ticket count
            latest_snapshot = TicketSnapshot.objects.filter(
                filter=filter_instance,
                created_at__date=analytics_date
            ).order_by('-created_at').first()
            
            # Get the latest batch (within 5 seconds of each other = 9 PM batch)
            if latest_snapshot:
                latest_time = latest_snapshot.created_at
                snapshots = TicketSnapshot.objects.filter(
                    filter=filter_instance,
                    created_at__date=analytics_date,
                    created_at__gte=latest_time - timedelta(seconds=5)
                )
            else:
                snapshots = TicketSnapshot.objects.filter(
                    filter=filter_instance,
                    created_at__date=analytics_date
                )
            
            # Get all updates for the day
            updates = TicketUpdate.objects.filter(
                submitted_at__date=analytics_date
            )
            
            # Get comparison data
            try:
                comparison = SnapshotComparison.objects.get(
                    filter=filter_instance,
                    comparison_date=analytics_date
                )
            except SnapshotComparison.DoesNotExist:
                comparison = None
            
            # Basic metrics - use unique tickets from baseline
            all_ticket_ids = list(snapshots.values_list('ticket_id', flat=True).distinct())
            
            # Use set to ensure unique assignees (no duplicates)
            unique_assignees = set(snapshots.values_list('assignee', flat=True))
            
            # Update compliance - count unique tickets with updates
            ticket_ids_with_updates = set(updates.filter(
                ticket_id__in=all_ticket_ids
            ).values_list('ticket_id', flat=True))
            updated_count = len(ticket_ids_with_updates)
            
            # Get comparison result
            try:
                comparison_result = SnapshotComparison.objects.get(
                    filter=filter_instance,
                    comparison_date=analytics_date
                )
            except SnapshotComparison.DoesNotExist:
                comparison_result = None
            
            # Calculate fresh/active ticket count and total (all touched tickets)
            if comparison_result:
                # Use ticket lists directly from comparison model
                resolved_count = len(comparison_result.removed_tickets) if comparison_result.removed_tickets else 0
                # Fresh total = today's tickets (all_ticket_ids) minus resolved tickets
                fresh_total = len(all_ticket_ids) - resolved_count
                # Total = all tickets involved = fresh + resolved
                total_tickets = len(all_ticket_ids)
            else:
                total_tickets = len(all_ticket_ids)
                fresh_total = total_tickets
                resolved_count = 0
            
            # Pending = active/fresh tickets - updated
            missed_count = fresh_total - updated_count
            
            # Status metrics - use baseline tickets for status counts
            status_counts = {}
            for ticket_id in all_ticket_ids:
                # Get the latest status for each ticket
                ticket_snapshots = snapshots.filter(ticket_id=ticket_id).order_by('-created_at')
                if ticket_snapshots.exists():
                    status = ticket_snapshots.first().status
                    status_counts[status] = status_counts.get(status, 0) + 1
            
            # New and resolved tickets (from comparison)
            new_tickets_count = len(comparison_result.new_tickets) if comparison_result and comparison_result.new_tickets else 0
            resolved_final_count = resolved_count
            
            # Assignee metrics - count unique tickets per assignee
            # Use ONLY final 9 PM snapshot batch (not mix with hourly snapshots)
            latest_snapshot = TicketSnapshot.objects.filter(
                filter=filter_instance,
                created_at__date=analytics_date
            ).order_by('-created_at').first()
            
            if latest_snapshot:
                latest_time = latest_snapshot.created_at
                threshold = latest_time - timedelta(seconds=5)
                logger.info(f"Analytics: Latest time={latest_time}, Threshold={threshold}")
                
                all_day_snapshots = TicketSnapshot.objects.filter(
                    filter=filter_instance,
                    created_at__date=analytics_date,
                    created_at__gte=threshold
                )
                logger.info(f"Analytics: Final 9PM batch count={all_day_snapshots.count()}")
            else:
                all_day_snapshots = TicketSnapshot.objects.filter(
                    filter=filter_instance,
                    snapshot_date=analytics_date
                )
                logger.info(f"Analytics: Using snapshot_date fallback, count={all_day_snapshots.count()}")
            
            if all_day_snapshots.exists():
                # Get unique assignees from final 9 PM snapshots only
                all_unique_assignees = set(all_day_snapshots.values_list('assignee', flat=True))
            else:
                all_unique_assignees = unique_assignees
            
            assignee_metrics = {}
            no_update_assignees = []
            
            # Count tickets per assignee
            for assignee in all_unique_assignees:
                assignee_ticket_ids = list(all_day_snapshots.filter(
                    assignee=assignee
                ).values_list('ticket_id', flat=True).distinct())
                
                assignee_update_count = updates.filter(
                    assignee=assignee,
                    ticket_id__in=assignee_ticket_ids
                ).count()
                
                tickets_count = len(assignee_ticket_ids)
                resolved = all_day_snapshots.filter(
                    assignee=assignee,
                    status='Done'
                ).values('ticket_id').distinct().count()
                
                assignee_metrics[assignee] = {
                    'tickets': tickets_count,
                    'updated': assignee_update_count > 0,
                    'resolved': resolved,
                }
                
                if assignee_update_count == 0 and tickets_count > 0:
                    no_update_assignees.append({
                        'assignee': assignee,
                        'tickets': tickets_count
                    })
            
            # Resolved by assignee - count unique tickets per assignee with Done status
            resolved_by_assignee = {}
            for assignee in unique_assignees:
                resolved = snapshots.filter(
                    assignee=assignee,
                    status='Done'
                ).values('ticket_id').distinct().count()
                if resolved > 0:
                    resolved_by_assignee[assignee] = resolved
            
            analytics_data = {
                'total_tickets': total_tickets,
                'updated_count': updated_count,
                'missed_count': missed_count,
                'new_tickets_count': new_tickets_count,
                'resolved_count': resolved_final_count,
                'status_counts': status_counts,
                'assignee_count': len(assignee_metrics),
                'compliance_rate': (updated_count / total_tickets * 100) if total_tickets > 0 else 0,
            }
            
            # Save analytics
            DailyAnalytics.objects.update_or_create(
                filter=filter_instance,
                analytics_date=analytics_date,
                defaults={
                    'total_tickets': total_tickets,
                    'updated_count': updated_count,
                    'missed_count': missed_count,
                    'new_tickets_count': new_tickets_count,
                    'resolved_count': resolved_final_count,
                    'assignee_metrics': assignee_metrics,
                    'no_update_assignees': no_update_assignees,
                    'resolved_by_assignee': resolved_by_assignee,
                    'analytics_data': analytics_data,
                }
            )
            
            return analytics_data
        
        except Exception as e:
            logger.error(f"Failed to compute analytics: {str(e)}")
            raise
    
    @staticmethod
    def generate_markdown_report(filter_instance, analytics_date: date = None) -> str:
        """
        Generate a beautiful markdown report
        
        Args:
            filter_instance: Filter object
            analytics_date: Date to generate report for (defaults to today)
            
        Returns:
            Markdown report string
        """
        try:
            if analytics_date is None:
                analytics_date = timezone.now().date()
            
            # Get analytics
            try:
                analytics = DailyAnalytics.objects.get(
                    filter=filter_instance,
                    analytics_date=analytics_date
                )
            except DailyAnalytics.DoesNotExist:
                logger.warning(f"No analytics found for {analytics_date}")
                return "**Daily Report**\n\nNo data available"
            
            # Get comparison data from stored SnapshotComparison
            try:
                comparison = SnapshotComparison.objects.get(
                    filter=filter_instance,
                    comparison_date=analytics_date
                )
                comparison_result = {
                    'new_tickets': comparison.new_tickets or [],
                    'resolved_tickets': comparison.removed_tickets or [],
                    'status_changes': comparison.status_changes or {},
                }
            except SnapshotComparison.DoesNotExist:
                comparison_result = {
                    'new_tickets': [],
                    'resolved_tickets': [],
                    'status_changes': {},
                }
            
            # Build markdown report with emojis and formatting
            report_lines = []
            
            # Header with emojis and markdown
            report_lines.append(f"📋 **DAILY JIRA REPORT — {filter_instance.name}**")
            report_lines.append(f"📅 {analytics_date.strftime('%d %B %Y')}")
            report_lines.append("")
            report_lines.append("---")
            report_lines.append("")
            
            # Overview section with emojis and markdown
            compliance = analytics.analytics_data.get('compliance_rate', 0)
            # Fresh total = active tickets only (not resolved)
            fresh_total = analytics.total_tickets
            # Total all = active + resolved tickets
            total_all_tickets = analytics.total_tickets + len(comparison_result['resolved_tickets'])
            # Pending = active tickets - updated
            pending_count = fresh_total - analytics.updated_count
            
            report_lines.append("## 📊 OVERVIEW")
            report_lines.append("")
            report_lines.append(f"- ✅ **Total Tickets:** {total_all_tickets}")
            report_lines.append(f"- 🟢 **Updated:** {analytics.updated_count}")
            report_lines.append(f"- 🟡 **Pending:** {pending_count}")
            report_lines.append(f"- 🆕 **New Today:** {len(comparison_result['new_tickets'])}")
            report_lines.append(f"- ✔️ **Resolved:** {len(comparison_result['resolved_tickets'])}")
            report_lines.append(f"- 🎯 **Compliance:** {compliance:.0f}%")
            report_lines.append("")
            
            # Top assignees section with emojis
            if analytics.assignee_metrics:
                report_lines.append("---")
                report_lines.append("")
                report_lines.append("## 🏆 TOP CONTRIBUTORS")
                report_lines.append("")
                
                # Build contributor metrics including resolved tickets
                contributor_metrics = {}
                
                # Start with active tickets
                for assignee, metrics in analytics.assignee_metrics.items():
                    contributor_metrics[assignee] = metrics['tickets']
                
                # Add resolved tickets by getting assignee from snapshots
                if comparison_result['resolved_tickets']:
                    yesterday = analytics_date - timedelta(days=1)
                    yesterday_snapshots = TicketSnapshot.objects.filter(
                        filter=filter_instance,
                        snapshot_date=yesterday,
                        ticket_id__in=comparison_result['resolved_tickets']
                    )
                    
                    for snapshot in yesterday_snapshots:
                        if snapshot.assignee not in contributor_metrics:
                            contributor_metrics[snapshot.assignee] = 0
                        contributor_metrics[snapshot.assignee] += 1
                
                # Sort and display top 3
                sorted_assignees = sorted(
                    contributor_metrics.items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:3]
                
                medals = ["🥇", "🥈", "🥉"]
                for idx, (assignee, ticket_count) in enumerate(sorted_assignees):
                    medal = medals[idx] if idx < len(medals) else "•"
                    report_lines.append(f"{idx + 1}. {medal} {assignee} — {ticket_count} tickets")
                report_lines.append("")
            
            # Tickets awaiting updates (no submission) - RED FLAG - ONLY ACTIVE TICKETS (batch 2)
            if filter_instance and analytics_date:
                from core.models import TicketUpdate
                
                # Get ONLY the final 9 PM snapshot - tickets still in filter
                final_snapshots = TicketSnapshot.objects.filter(
                    filter=filter_instance,
                    snapshot_date=analytics_date
                ).order_by('-created_at')
                
                if final_snapshots.exists():
                    latest_time = final_snapshots.first().created_at
                    day_tickets = TicketSnapshot.objects.filter(
                        filter=filter_instance,
                        snapshot_date=analytics_date,
                        created_at__gte=latest_time - timedelta(seconds=5)
                    )
                else:
                    day_tickets = final_snapshots
                
                if day_tickets.exists():
                    day_ticket_ids = list(day_tickets.values_list('ticket_id', flat=True).distinct())
                    
                    # Exclude resolved tickets
                    resolved_ticket_ids = set(comparison_result['resolved_tickets']) if comparison_result else set()
                    active_ticket_ids = [tid for tid in day_ticket_ids if tid not in resolved_ticket_ids]
                    
                    # Get ticket IDs with submissions TODAY ONLY
                    submitted_tickets = set(TicketUpdate.objects.filter(
                        ticket_id__in=active_ticket_ids,
                        submitted_at__date=analytics_date
                    ).values_list('ticket_id', flat=True).distinct())
                    
                    # Find active tickets without submissions (grouped by assignee)
                    awaiting_by_assignee = {}
                    for snapshot in day_tickets:
                        if snapshot.ticket_id in active_ticket_ids and snapshot.ticket_id not in submitted_tickets:
                            if snapshot.assignee not in awaiting_by_assignee:
                                awaiting_by_assignee[snapshot.assignee] = []
                            awaiting_by_assignee[snapshot.assignee].append(snapshot.ticket_id)
                    
                    if awaiting_by_assignee:
                        report_lines.append("---")
                        report_lines.append("")
                        report_lines.append("## 🚩 AWAITING UPDATES (NO SUBMISSION)")
                        report_lines.append("")
                        
                        for assignee, tickets in sorted(awaiting_by_assignee.items()):
                            unique_tickets = sorted(set(tickets))
                            # Limit to 3 tickets, add "..." if more
                            if len(unique_tickets) > 3:
                                tickets_str = ", ".join(unique_tickets[:3]) + " ..."
                            else:
                                tickets_str = ", ".join(unique_tickets)
                            report_lines.append(f"- 🚩 {assignee}: {tickets_str} ({len(set(tickets))} tickets)")
                        report_lines.append("")
            
            # New tickets section
            if comparison_result and comparison_result['new_tickets']:
                report_lines.append("---")
                report_lines.append("")
                report_lines.append("## 🆕 NEW TICKETS")
                report_lines.append("")
                
                for ticket_id in comparison_result['new_tickets']:
                    report_lines.append(f"- {ticket_id}")
                report_lines.append("")
            
            # Status changes section (10 AM → 9 PM)
            if comparison_result and comparison_result['status_changes']:
                report_lines.append("---")
                report_lines.append("")
                report_lines.append("## 🔄 STATUS CHANGES")
                report_lines.append("")
                
                for ticket_id, changes in comparison_result['status_changes'].items():
                    report_lines.append(f"- {ticket_id}: {changes['yesterday']} → {changes['today']}")
                report_lines.append("")
            
            # Resolved/Moved tickets section
            if comparison_result and comparison_result['resolved_tickets']:
                report_lines.append("---")
                report_lines.append("")
                report_lines.append("## ✅ RESOLVED/MOVED")
                report_lines.append("")
                
                for ticket_id in comparison_result['resolved_tickets']:
                    report_lines.append(f"- {ticket_id}")
                report_lines.append("")
            
            # Build markdown table with ticket details (including resolved tickets from intermediate snapshots)
            report_lines.append("---")
            report_lines.append("")
            report_lines.append("## 📝 DETAILED TICKET UPDATES")
            report_lines.append("")
            
            # Get ONLY the final 9 PM snapshot for accurate ticket list
            final_9pm_snapshots = TicketSnapshot.objects.filter(
                filter=filter_instance,
                snapshot_date=analytics_date
            ).order_by('-created_at')
            
            if final_9pm_snapshots.exists():
                latest_time = final_9pm_snapshots.first().created_at
                all_day_snapshots = TicketSnapshot.objects.filter(
                    filter=filter_instance,
                    snapshot_date=analytics_date,
                    created_at__gte=latest_time - timedelta(seconds=5)
                ).order_by('priority', 'ticket_id')
            else:
                all_day_snapshots = final_9pm_snapshots
            
            # Get resolved tickets (these only come from baseline, not same-day resolutions)
            resolved_tickets = comparison_result.get('resolved_tickets', []) if comparison_result else []
            resolved_ticket_ids = set(resolved_tickets)
            
            if all_day_snapshots.exists():
                report_lines.append("| Ticket | Assignee | Status | ETA | Update | Blockers |")
                report_lines.append("|--------|----------|--------|-----|--------|----------|")
                
                # Track unique tickets to avoid duplicates
                shown_tickets = set()
                new_ticket_ids = set(comparison_result.get('new_tickets', []) if comparison_result else [])
                
                # Sort snapshots by assignee name, then by ticket_id
                sorted_snapshots = sorted(all_day_snapshots, key=lambda x: (x.assignee.lower(), x.ticket_id))
                
                # Add only ACTIVE tickets (exclude resolved ones)
                for snapshot in sorted_snapshots:
                    # Skip resolved tickets - they shouldn't appear in active ticket table
                    if snapshot.ticket_id in resolved_ticket_ids:
                        continue
                        
                    if snapshot.ticket_id not in shown_tickets:
                        shown_tickets.add(snapshot.ticket_id)
                        
                        # Get update for this ticket submitted TODAY ONLY
                        update = TicketUpdate.objects.filter(
                            ticket_id=snapshot.ticket_id,
                            assignee=snapshot.assignee,
                            submitted_at__date=analytics_date
                        ).order_by('-submitted_at').first()
                        
                        eta = update.eta if update else "—"
                        note = update.update_note if update and update.update_note else "—"
                        blockers = update.blockers if update and update.blockers else "—"
                        
                        # Add marker for new tickets so assignee knows to submit update
                        ticket_label = f"{snapshot.ticket_id} 🆕" if snapshot.ticket_id in new_ticket_ids else snapshot.ticket_id
                        
                        report_lines.append(f"| {ticket_label} | {snapshot.assignee} | {snapshot.status} | {eta} | {note} | {blockers} |")
            
            # Resolved tickets are shown in the "RESOLVED" section above, not in the detail table
            else:
                report_lines.append("No active tickets in filter.")
            
            report_lines.append("")
            report_lines.append("---")
            report_lines.append("")
            
            # Get IST timezone
            ist = pytz.timezone('Asia/Kolkata')
            generated_time = timezone.now().astimezone(ist).strftime('%H:%M')
            
            report_lines.append(f"🕒 Generated: {analytics_date.strftime('%d %B %Y')} at {generated_time} IST")
            
            # Convert to markdown
            markdown_report = "\n".join(report_lines)
            
            # Save report
            DailyReport.objects.update_or_create(
                filter=filter_instance,
                report_date=analytics_date,
                defaults={
                    'markdown_content': markdown_report,
                }
            )
            
            return markdown_report
        
        except Exception as e:
            logger.error(f"Failed to generate report: {str(e)}")
            raise
