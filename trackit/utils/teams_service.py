"""Microsoft Teams Integration Service"""
import requests
import logging
from django.conf import settings
from typing import Dict, Any, Optional
from datetime import datetime
import json

logger = logging.getLogger(__name__)


class TeamsService:
    """Service to send messages to Microsoft Teams via Incoming Webhooks"""
    
    def __init__(self):
        self.webhook_url = getattr(settings, 'TEAMS_WEBHOOK_URL', None)
        self.enabled = bool(self.webhook_url)
    
    def _send_message(self, payload: Dict[str, Any]) -> bool:
        """
        Send a message to Teams via webhook
        
        Args:
            payload: Message payload
            
        Returns:
            True if message sent successfully, False otherwise
        """
        if not self.enabled:
            logger.warning("Teams webhook URL not configured. Skipping Teams notification.")
            return False
        
        try:
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=10
            )
            response.raise_for_status()
            logger.info("Message sent to Teams successfully")
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send message to Teams: {str(e)}")
            return False
    
    def send_report_card(
        self,
        filter_name: str,
        report_date: str,
        total_tickets: int,
        updated_count: int,
        pending_count: int,
        new_tickets: int,
        resolved_count: int,
        compliance: float,
        top_contributors: list,
        awaiting_assignees: list
    ) -> bool:
        """
        Send a formatted report card to Teams with adaptive card format
        
        Args:
            filter_name: Name of the filter
            report_date: Date of the report
            total_tickets: Total number of tickets
            updated_count: Number of tickets updated
            pending_count: Number of pending tickets
            new_tickets: Number of new tickets
            resolved_count: Number of resolved tickets
            compliance: Compliance percentage
            top_contributors: List of (name, count) tuples
            awaiting_assignees: List of dicts with assignee and tickets
            
        Returns:
            True if sent successfully, False otherwise
        """
        
        # Build top contributors section
        contributors_md = ""
        for idx, (name, count) in enumerate(top_contributors[:3], 1):
            medals = ["🥇", "🥈", "🥉"]
            medal = medals[idx - 1] if idx <= 3 else "•"
            contributors_md += f"\n- {medal} {name} — {count} tickets"
        
        # Build awaiting updates section
        awaiting_md = ""
        for item in awaiting_assignees[:5]:  # Limit to top 5
            assignee = item['assignee']
            count = item.get('tickets', 0)
            awaiting_md += f"\n- 🚩 {assignee}: {count} tickets"
        
        # Create adaptive card with better formatting
        payload = {
            "@type": "MessageCard",
            "@context": "https://schema.org/extensions",
            "summary": f"TrackIt Report - {filter_name} - {report_date}",
            "themeColor": "0078D4",
            "sections": [
                {
                    "activityTitle": f"📋 DAILY JIRA REPORT — {filter_name}",
                    "activitySubtitle": f"📅 {report_date}",
                    "text": f"**Report Generated:** {datetime.now().strftime('%d %B %Y at %H:%M %Z')}",
                },
                {
                    "activityTitle": "📊 OVERVIEW",
                    "facts": [
                        {
                            "name": "✅ Total Tickets",
                            "value": str(total_tickets)
                        },
                        {
                            "name": "🟢 Updated",
                            "value": str(updated_count)
                        },
                        {
                            "name": "🟡 Pending",
                            "value": str(pending_count)
                        },
                        {
                            "name": "🆕 New Today",
                            "value": str(new_tickets)
                        },
                        {
                            "name": "✔️ Resolved",
                            "value": str(resolved_count)
                        },
                        {
                            "name": "🎯 Compliance",
                            "value": f"{compliance:.0f}%"
                        }
                    ]
                }
            ]
        }
        
        # Add contributors section if available
        if contributors_md:
            payload["sections"].append({
                "activityTitle": "🏆 TOP CONTRIBUTORS",
                "text": contributors_md
            })
        
        # Add awaiting section if available
        if awaiting_md:
            payload["sections"].append({
                "activityTitle": "🚩 AWAITING UPDATES",
                "text": awaiting_md
            })
        
        # Add action button to view full report
        payload["potentialAction"] = [
            {
                "@type": "OpenUri",
                "name": "View Full Report",
                "targets": [
                    {
                        "os": "default",
                        "uri": f"{getattr(settings, 'SITE_URL', 'http://localhost:8000')}/reports/"
                    }
                ]
            }
        ]
        
        return self._send_message(payload)
    
    def send_simple_report(
        self,
        filter_name: str,
        report_date: str,
        markdown_content: str
    ) -> bool:
        """
        Send a simple text report to Teams
        
        Args:
            filter_name: Name of the filter
            report_date: Date of the report
            markdown_content: Markdown formatted report
            
        Returns:
            True if sent successfully, False otherwise
        """
        
        if not self.enabled:
            return False
        
        payload = {
            "@type": "MessageCard",
            "@context": "https://schema.org/extensions",
            "summary": f"TrackIt Report - {filter_name}",
            "themeColor": "0078D4",
            "sections": [
                {
                    "activityTitle": f"📋 TrackIt Report - {filter_name}",
                    "activitySubtitle": f"📅 {report_date}",
                    "text": markdown_content
                }
            ]
        }
        
        return self._send_message(payload)
    
    def send_notification(
        self,
        title: str,
        message: str,
        color: str = "0078D4"
    ) -> bool:
        """
        Send a simple notification to Teams
        
        Args:
            title: Notification title
            message: Notification message
            color: Card color (hex code)
            
        Returns:
            True if sent successfully, False otherwise
        """
        
        if not self.enabled:
            return False
        
        payload = {
            "@type": "MessageCard",
            "@context": "https://schema.org/extensions",
            "summary": title,
            "themeColor": color,
            "sections": [
                {
                    "activityTitle": title,
                    "text": message
                }
            ]
        }
        
        return self._send_message(payload)
