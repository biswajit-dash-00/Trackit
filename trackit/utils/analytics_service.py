"""Analytics Service for computing metrics and generating insights"""
import logging
import pytz
from datetime import date
from django.utils import timezone
from django.conf import settings
from typing import Dict, Any, List
from core.models import (
    TicketUpdate, 
    DailyAnalytics, DailyReport
)
logger = logging.getLogger(__name__)


class AnalyticsService:
    """Service to compute analytics and generate reports"""
    
    @staticmethod
    def compute_daily_analytics(filter_instance, yesterday_snapshots, hourly_snapshots, today_snapshots, analytics_date=None) -> Dict[str, Any]:
        """
        Compute analytics for a specific day using pre-fetched snapshot data.
        
        Args:
            filter_instance: Filter object
            yesterday_snapshots: Queryset/list of yesterday's 9 PM TicketSnapshot records
            hourly_snapshots: Queryset/list of today's intermediate hourly TicketSnapshot records
            today_snapshots: Queryset/list of today's 9 PM TicketSnapshot records
            analytics_date: Date to compute analytics for (defaults to today)
            
        Returns:
            Dictionary with computed metrics
        """
        try:
            if analytics_date is None:
                analytics_date = timezone.now().date()

            # --- Build in-memory lookup structures (single pass each, no extra DB calls) ---

            # Yesterday 9PM: ticket_id -> snapshot
            yesterday_dict = {s.ticket_id: s for s in yesterday_snapshots}
            yesterday_ids = set(yesterday_dict.keys())

            # Today 9PM: ticket_id -> snapshot (deduplicate — keep latest)
            today_dict = {s.ticket_id: s for s in today_snapshots}
            today_9pm_ids = set(today_dict.keys())

            # Today hourly: just need ticket_ids for set operations
            today_hourly_dict = {s.ticket_id: s for s in hourly_snapshots}
            today_hourly_ids = set(s.ticket_id for s in hourly_snapshots)

            # --- Core ticket sets ---

            # NEW: appeared today (9PM or hourly) but NOT in yesterday 9PM
            new_ticket_ids = (today_9pm_ids | today_hourly_ids) - yesterday_ids

            # RESOLVED: in yesterday 9PM, seen in today's hourly, but gone from today's 9PM
            resolved_ticket_ids = (yesterday_ids | today_hourly_ids) - today_9pm_ids

            # PENDING = tickets in today's 9PM (active right now)
            pending_count = len(today_9pm_ids)

            # TOTAL = Pending + Resolved
            total_tickets = pending_count + len(resolved_ticket_ids)

            # --- ONE DB call for all today's updates ---
            all_relevant_ids = list(today_9pm_ids)
            all_updates = list(
                TicketUpdate.objects.filter(
                    ticket_id__in=all_relevant_ids,
                    submitted_at__date=analytics_date
                ).values('ticket_id', 'assignee')
            )
            updated_ticket_ids = set(u['ticket_id'] for u in all_updates)

            # UPDATED = updates on currently active (9PM) tickets only
            updated_count = len(updated_ticket_ids)

            # AWAITING UPDATE = in today's 9PM with no update logged
            awaiting_ticket_ids = today_9pm_ids - updated_ticket_ids

            # --- Assignee metrics (all in-memory) ---
            # Group today's 9PM tickets by assignee
            assignee_9pm_tickets: Dict[str, set] = {}
            for ticket_id, snapshot in today_dict.items():
                assignee = snapshot.assignee
                if assignee not in assignee_9pm_tickets:
                    assignee_9pm_tickets[assignee] = set()
                assignee_9pm_tickets[assignee].add(ticket_id)

            # Resolved tickets per assignee (look up in yesterday_dict)
            resolved_tickets_by_assignee: Dict[str, List] = {}
            for ticket_id in resolved_ticket_ids:
                if ticket_id in yesterday_dict:
                    assignee = yesterday_dict[ticket_id].assignee
                elif ticket_id in today_hourly_dict:
                    assignee = today_hourly_dict[ticket_id].assignee
                else:
                    continue
                if assignee not in resolved_tickets_by_assignee:
                    resolved_tickets_by_assignee[assignee] = []
                resolved_tickets_by_assignee[assignee].append(ticket_id)

            # Awaiting updates per assignee (for report section)
            awaiting_by_assignee: Dict[str, List] = {}
            for ticket_id in awaiting_ticket_ids:
                if ticket_id in today_dict:
                    assignee = today_dict[ticket_id].assignee
                    if assignee not in awaiting_by_assignee:
                        awaiting_by_assignee[assignee] = []
                    awaiting_by_assignee[assignee].append(ticket_id)

            # Assignees who logged at least one update today
            assignees_with_updates = set(u['assignee'] for u in all_updates)

            # Build full assignee_metrics
            assignee_metrics: Dict[str, Any] = {}
            no_update_assignees = []
            all_assignees = set(assignee_9pm_tickets.keys()) | set(resolved_tickets_by_assignee.keys())

            for assignee in all_assignees:
                active_tickets = assignee_9pm_tickets.get(assignee, set())
                resolved_for_assignee = len(resolved_tickets_by_assignee.get(assignee, []))
                has_update = assignee in assignees_with_updates

                assignee_metrics[assignee] = {
                    'tickets': len(active_tickets),
                    'resolved': resolved_for_assignee,
                    # Contributor count = active + resolved (total managed today)
                    'contributor_count': len(active_tickets) + resolved_for_assignee,
                    'updated': has_update,
                }

                if not has_update and len(active_tickets) > 0:
                    no_update_assignees.append({
                        'assignee': assignee,
                        'tickets': len(active_tickets)
                    })

            compliance_rate = (updated_count / pending_count * 100) if pending_count > 0 else 0

            analytics_data = {
                'total_tickets': total_tickets,
                'pending_count': pending_count,
                'updated_count': updated_count,
                'missed_count': pending_count - updated_count,
                'new_tickets_count': len(new_ticket_ids),
                'resolved_count': len(resolved_ticket_ids),
                'compliance_rate': compliance_rate,
                'assignee_count': len(assignee_metrics),
                # Store for report generation — avoids re-querying SnapshotComparison
                'new_tickets': sorted(new_ticket_ids),
                'resolved_tickets': sorted(resolved_ticket_ids),
                'awaiting_by_assignee': {k: sorted(v) for k, v in awaiting_by_assignee.items()},
                # Store today's 9PM ticket details for the report table (ticket_id -> {fields})
                'today_tickets': {
                    ticket_id: {
                        'assignee': s.assignee,
                        'priority': s.priority,
                        'status': s.status,
                    }
                    for ticket_id, s in today_dict.items()
                },
            }

            # Save analytics
            DailyAnalytics.objects.update_or_create(
                filter=filter_instance,
                analytics_date=analytics_date,
                defaults={
                    'total_tickets': total_tickets,
                    'updated_count': updated_count,
                    'missed_count': pending_count - updated_count,
                    'new_tickets_count': len(new_ticket_ids),
                    'resolved_count': len(resolved_ticket_ids),
                    'assignee_metrics': assignee_metrics,
                    'no_update_assignees': no_update_assignees,
                    'resolved_by_assignee': resolved_tickets_by_assignee,
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
            
            # Get comparison data from analytics_data (pre-computed, no extra DB call)
            comparison_result = {
                'new_tickets': analytics.analytics_data.get('new_tickets', []),
                'resolved_tickets': analytics.analytics_data.get('resolved_tickets', []),
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
            total_all_tickets = analytics.total_tickets
            pending_count = analytics.analytics_data.get("pending_count")
            
            report_lines.append("## 📊 OVERVIEW")
            report_lines.append("")
            report_lines.append(f"- ✅ **Total Tickets:** {total_all_tickets}")
            report_lines.append(f"- 🟢 **Updated:** {analytics.updated_count}")
            report_lines.append(f"- 🟡 **Pending:** {pending_count}")
            report_lines.append(f"- 🆕 **New Today:** {analytics.analytics_data.get('new_tickets_count')}")
            report_lines.append(f"- ✔️ **Resolved:** {analytics.resolved_count}")
            report_lines.append(f"- 🎯 **Compliance:** {compliance:.0f}%")
            report_lines.append("")
            
            # Top assignees section with emojis
            if analytics.assignee_metrics:
                report_lines.append("---")
                report_lines.append("")
                report_lines.append("## 🏆 TOP CONTRIBUTORS")
                report_lines.append("")
                
                # Build contributor metrics from analytics_data (no extra DB call)
                # contributor_count = active (9PM) tickets + resolved tickets
                contributor_metrics = {
                    assignee: metrics.get('contributor_count', metrics['tickets'])
                    for assignee, metrics in analytics.assignee_metrics.items()
                }
                
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
            
            # Tickets awaiting updates — use pre-computed data from analytics_data (no extra DB call)
            awaiting_by_assignee = analytics.analytics_data.get('awaiting_by_assignee', {})

            if awaiting_by_assignee:
                report_lines.append("---")
                report_lines.append("")
                report_lines.append("## 🚩 AWAITING UPDATES (NO SUBMISSION)")
                report_lines.append("")

                for assignee in sorted(awaiting_by_assignee.keys()):
                    unique_tickets = sorted(set(awaiting_by_assignee[assignee]))
                    if len(unique_tickets) > 3:
                        tickets_str = ", ".join(unique_tickets[:3]) + " ..."
                    else:
                        tickets_str = ", ".join(unique_tickets)
                    report_lines.append(f"- 🚩 {assignee}: {tickets_str} ({len(unique_tickets)} tickets)")
                report_lines.append("")
            
            # Resolved/Moved tickets section — grouped by assignee, truncated at 3
            resolved_tickets_by_assignee = analytics.analytics_data.get('resolved_tickets_by_assignee', {})
            if resolved_tickets_by_assignee:
                report_lines.append("---")
                report_lines.append("")
                report_lines.append("## ✅ RESOLVED/MOVED")
                report_lines.append("")

                for assignee in sorted(resolved_tickets_by_assignee.keys()):
                    unique_tickets = sorted(set(resolved_tickets_by_assignee[assignee]))
                    if len(unique_tickets) > 3:
                        tickets_str = ", ".join(unique_tickets[:3]) + " ..."
                    else:
                        tickets_str = ", ".join(unique_tickets)
                    report_lines.append(f"- ✅ {assignee}: {tickets_str} ({len(unique_tickets)} tickets)")
                report_lines.append("")
            
            # Build markdown table with ticket details (including resolved tickets from intermediate snapshots)
            report_lines.append("---")
            report_lines.append("")
            report_lines.append("## 📝 DETAILED TICKET UPDATES")
            report_lines.append("")
            
            # Build detailed ticket table from pre-computed analytics_data (no snapshot re-fetch)
            jira_base_url = getattr(settings, 'JIRA_BASE_URL', '').rstrip('/')
            today_tickets = analytics.analytics_data.get('today_tickets', {})
            new_ticket_ids = set(comparison_result['new_tickets'])

            # ONE batched DB call for all updates today
            active_ticket_ids = [tid for tid in today_tickets]
            all_updates_qs = TicketUpdate.objects.filter(
                ticket_id__in=active_ticket_ids,
                submitted_at__date=analytics_date
            ).order_by('-submitted_at').values('ticket_id', 'assignee', 'eta', 'update_note', 'blockers')

            # Build update lookup: ticket_id -> update row (latest per ticket)
            update_lookup: Dict[str, Any] = {}
            for upd in all_updates_qs:
                if upd['ticket_id'] not in update_lookup:
                    update_lookup[upd['ticket_id']] = upd

            if today_tickets:
                report_lines.append("| Ticket | Assignee | Priority | Status | ETA | Update | Blockers |")
                report_lines.append("|--------|----------|----------|--------|-----|--------|----------|")

                # Sort by assignee name then ticket_id (all in-memory)
                sorted_tickets = sorted(
                    [(tid, info) for tid, info in today_tickets.items()],
                    key=lambda x: (x[1]['assignee'].lower(), x[0])
                )

                for ticket_id, info in sorted_tickets:
                    upd = update_lookup.get(ticket_id)
                    eta = upd['eta'] if upd and upd['eta'] else "—"
                    note = upd['update_note'] if upd and upd['update_note'] else "—"
                    blockers = upd['blockers'] if upd and upd['blockers'] else "—"
                    ticket_link = f"[{ticket_id}]({jira_base_url}/browse/{ticket_id})"
                    ticket_label = f"{ticket_link} 🆕" if ticket_id in new_ticket_ids else ticket_link
                    report_lines.append(
                        f"| {ticket_label} | {info['assignee']} | {info['priority']} "
                        f"| {info['status']} | {eta} | {note} | {blockers} |"
                    )
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
