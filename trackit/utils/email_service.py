"""Email Service for sending emails"""
import logging
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.utils.html import strip_tags
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class EmailService:
    """Service to send emails"""
    
    @staticmethod
    def send_reminder_email(
        assignee_name: str,
        assignee_email: str,
        tickets: List[Dict[str, str]],
        update_link: str,
        filter_name: str
    ) -> bool:
        """
        Send daily reminder email to assignee
        
        Args:
            assignee_name: Name of assignee
            assignee_email: Email of assignee
            tickets: List of ticket dicts with ticket_id
            update_link: Secure update link
            filter_name: Name of the filter
            
        Returns:
            True if email sent successfully, False otherwise
        """
        try:
            subject = f"Daily Ticket Update Required - {filter_name}"
            
            context = {
                'assignee_name': assignee_name,
                'ticket_count': len(tickets),
                'tickets': tickets,
                'update_link': update_link,
                'filter_name': filter_name,
                'token_validity_hours': settings.TOKEN_VALIDITY_HOURS,
            }
            
            html_message = render_to_string('emails/reminder.html', context)
            text_message = render_to_string('emails/reminder.txt', context)
            
            email = EmailMultiAlternatives(
                subject=subject,
                body=text_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=["biswajit.dash@solytics-partners.com"] # for tesing
            )
            email.attach_alternative(html_message, "text/html")
            email.send(fail_silently=False)
            logger.info(f"Reminder email sent to {assignee_email}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to send reminder email to {assignee_email}: {str(e)}")
            return False
    
    @staticmethod
    def send_report_email(
        admin_email: str,
        filter_name: str,
        markdown_content: str,
        report_date: str
    ) -> bool:
        """
        Send daily report email to admin with HTML-rendered markdown
        
        Args:
            admin_email: Admin email address
            filter_name: Name of the filter
            markdown_content: Markdown report content
            report_date: Date of the report
            
        Returns:
            True if email sent successfully, False otherwise
        """
        try:
            from core.models import Filter, TicketSnapshot, TicketUpdate
            from markdown import markdown
            
            subject = f"TrackIt Daily Jira Report - {filter_name} - {report_date}"
            
            # Get filter and snapshots
            filter_obj = Filter.objects.get(name=filter_name)
            snapshots = TicketSnapshot.objects.filter(
                filter=filter_obj,
                snapshot_date=report_date
            ).order_by('priority', 'ticket_id')
            
            
            # Create plaintext body
            text_message = f"""TrackIt Daily Report - {filter_name}

{markdown_content}

"""
         
            # Convert markdown to HTML and add CSS styling
            html_content = markdown(markdown_content, extensions=['tables'])
            
            # Add CSS styling for better email rendering
            html_message = f"""
            <html>
                <head>
                    <style>
                        body {{
                            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
                            line-height: 1.6;
                            color: #333;
                        }}
                        h1, h2, h3 {{
                            color: #2c3e50;
                            margin-top: 20px;
                            margin-bottom: 10px;
                        }}
                        h1 {{
                            border-bottom: 2px solid #3498db;
                            padding-bottom: 10px;
                            font-size: 24px;
                        }}
                        h2 {{
                            font-size: 18px;
                        }}
                        table {{
                            border-collapse: collapse;
                            width: 100%;
                            margin: 15px 0;
                            background: white;
                        }}
                        th {{
                            background-color: #34495e;
                            color: white;
                            padding: 12px;
                            text-align: left;
                            font-weight: bold;
                        }}
                        td {{
                            padding: 12px;
                            border-bottom: 1px solid #ecf0f1;
                        }}
                        tr:nth-child(even) {{
                            background-color: #f8f9fa;
                        }}
                        tr:hover {{
                            background-color: #ecf0f1;
                        }}
                        ul, ol {{
                            margin: 10px 0;
                            padding-left: 25px;
                        }}
                        li {{
                            margin: 5px 0;
                        }}
                        hr {{
                            border: none;
                            border-top: 1px solid #e0e0e0;
                            margin: 20px 0;
                        }}
                        .footer {{
                            color: #7f8c8d;
                            font-size: 12px;
                            margin-top: 30px;
                            border-top: 1px solid #ecf0f1;
                            padding-top: 10px;
                        }}
                    </style>
                </head>
                <body>
                    <h1>TrackIt Daily Report - {filter_name}</h1>
                    {html_content}
                    <div class="footer">
                        <p>This report was automatically generated. Please do not reply to this email.</p>
                    </div>
                </body>
            </html>
            """
            
            # Send email with HTML alternative
            email = EmailMultiAlternatives(
                subject=subject,
                body=text_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[admin_email]
            )
            
            # Attach HTML version
            email.attach_alternative(html_message, "text/html")
            email.send(fail_silently=False)
            
            logger.info(f"Report email sent to {admin_email}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to send report email to {admin_email}: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
    
    @staticmethod
    def send_admin_notification(
        admin_email: str,
        filter_name: str,
        subject_line: str,
        message: str
    ) -> bool:
        """
        Send admin notification email (simple text email)
        
        Args:
            admin_email: Admin email address
            filter_name: Name of the filter
            subject_line: Email subject
            message: Email body message
            
        Returns:
            True if email sent successfully, False otherwise
        """
        try:
            email = EmailMultiAlternatives(
                subject=subject_line,
                body=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[admin_email]
            )
            email.send(fail_silently=False)
            
            logger.info(f"Admin notification sent to {admin_email}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to send admin notification to {admin_email}: {str(e)}")
            return False
