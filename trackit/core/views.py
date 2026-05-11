"""Django template views for frontend pages"""
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.views.generic import TemplateView, ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.utils import timezone
from django.conf import settings
from core.models import (
    Filter, TicketSnapshot, EmailToken, TicketUpdate, DailyReport
)
from utils.token_service import TokenService

logger = logging.getLogger(__name__)


class UpdatePageView(View):
    """Secure page for assignees to submit updates"""
    
    def get(self, request, token):
        """Display update form"""
        try:
            # Validate token
            try:
                payload = TokenService.validate_token(token)
            except Exception as e:
                return render(request, 'update_error.html', {
                    'error': 'Invalid or expired link',
                    'is_update_page': True,
                    'token_validity_hours': settings.TOKEN_VALIDITY_HOURS,
                })
            
            filter_id = payload.get('filter_id')
            assignee_email = payload.get('assignee_email')
            
            # Get filter
            filter_instance = get_object_or_404(Filter, id=filter_id)
            
            # Check if token is already used or expired
            try:
                email_token = EmailToken.objects.get(token=token)
                if email_token.used:
                    return render(request, 'update_error.html', {
                        'error': 'This link has already been used',
                        'is_update_page': True,
                        'token_validity_hours': settings.TOKEN_VALIDITY_HOURS,
                    })
                # Check if token has expired (expires_at is in the past)
                if email_token.expires_at and email_token.expires_at <= timezone.now():
                    return render(request, 'update_error.html', {
                        'error': 'This link has expired. The update window has closed.',
                        'is_update_page': True,
                        'token_validity_hours': settings.TOKEN_VALIDITY_HOURS,
                    })
            except EmailToken.DoesNotExist:
                pass
            
            # Get assignee's tickets - only show CURRENT active tickets
            # First try fresh snapshot (batch=2), if not available fetch current from Jira
            fresh_snapshots = TicketSnapshot.objects.filter(
                filter=filter_instance,
                assignee=assignee_email,
                snapshot_date=timezone.now().date(),
                snapshot_batch=2  # Fresh snapshot with current tickets
            ).values('ticket_id', 'title', 'status', 'priority')
            
            if fresh_snapshots.exists():
                # Use fresh snapshots if available (after 9 PM)
                tickets = fresh_snapshots
            else:
                # Fetch CURRENT tickets from Jira (same as reminder job does)
                # This ensures only active tickets are shown, not moved ones
                from utils.jira_service import JiraService
                jira_service = JiraService()
                current_jira_tickets = jira_service.fetch_filter_tickets(filter_instance.jira_filter_id)
                
                # Filter to only this assignee's tickets
                tickets = [
                    {
                        'ticket_id': t['ticket_id'],
                        'title': t['title'],
                        'status': t['status'],
                        'priority': t.get('priority', 'Unknown')
                    }
                    for t in current_jira_tickets
                    if t['assignee'] == assignee_email
                ]
            
            context = {
                'filter': filter_instance,
                'assignee': assignee_email,
                'ticket_count': len(tickets) if isinstance(tickets, list) else tickets.count(),
                'tickets': list(tickets),
                'token': token,
                'is_update_page': True,  # Hide nav buttons on update page
            }
            
            return render(request, 'update_page.html', context)
        
        except Exception as e:
            logger.error(f"Update page error: {str(e)}")
            return render(request, 'update_error.html', {
                'error': 'An error occurred',
                'is_update_page': True,
                'token_validity_hours': settings.TOKEN_VALIDITY_HOURS,
            })
    
    def post(self, request, token):
        """Submit updates"""
        try:
            # Validate token
            try:
                payload = TokenService.validate_token(token)
            except Exception as e:
                logger.error(f"Token validation failed: {str(e)}")
                return JsonResponse({'error': 'Invalid or expired token'}, status=401)
            
            filter_id = payload.get('filter_id')
            assignee_email = payload.get('assignee_email')
            
            # Check if token has expired before processing submission
            try:
                email_token = EmailToken.objects.get(token=token)
                if email_token.expires_at and email_token.expires_at <= timezone.now():
                    return JsonResponse({
                        'error': 'This link has expired. The update window has closed.'
                    }, status=401)
                if email_token.used:
                    return JsonResponse({
                        'error': 'This link has already been used'
                    }, status=401)
            except EmailToken.DoesNotExist:
                logger.warning(f"Token {token[:10]}... not found in database during submission")
                pass
            
            logger.info(f"Processing updates for {assignee_email} on filter {filter_id}")
            
            # Get updates - they're sent as a single JSON string (not a list)
            import json
            updates_json_str = request.POST.get('updates', '[]')
            
            logger.info(f"Received updates JSON: {updates_json_str[:100]}...")
            
            created_count = 0
            
            try:
                # Parse JSON string to list of updates
                updates_list = json.loads(updates_json_str)
                logger.info(f"Parsed {len(updates_list)} updates")
                
                from django.utils import timezone
                today = timezone.now().date()
                
                # Create TicketUpdate record for each ticket
                for update in updates_list:
                    try:
                        # Delete any previous update for this ticket today (same assignee)
                        TicketUpdate.objects.filter(
                            ticket_id=update.get('ticket_id', ''),
                            assignee=assignee_email,
                            submitted_at__date=today
                        ).delete()
                        
                        # Create the new update
                        ticket_update = TicketUpdate.objects.create(
                            ticket_id=update.get('ticket_id', ''),
                            assignee=assignee_email,
                            eta=update.get('eta', ''),
                            update_note=update.get('update_note', ''),
                            blockers=update.get('blockers', ''),
                        )
                        logger.info(f"✓ Created update for {update.get('ticket_id')}")
                        created_count += 1
                    except Exception as e:
                        logger.error(f"Failed to save update for {update.get('ticket_id')}: {str(e)}")
                        import traceback
                        traceback.print_exc()
                        continue
            
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON: {str(e)}")
                return JsonResponse({'error': 'Invalid JSON format'}, status=400)
            
            logger.info(f"Successfully created {created_count} updates")
            
            # Mark token as used
            try:
                email_token = EmailToken.objects.get(token=token)
                email_token.mark_used(ip_address=self._get_client_ip(request))
                logger.info(f"Marked token {token[:10]}... as used")
            except EmailToken.DoesNotExist:
                logger.warning(f"Token {token[:10]}... not found in database")
                pass
            
            return render(request, 'update_success.html', {
                'count': created_count,
                'filter': filter_id,
                'is_update_page': True,  # Hide nav buttons
            })
        
        except Exception as e:
            logger.error(f"Update submission error: {str(e)}")
            import traceback
            traceback.print_exc()
            return JsonResponse({'error': str(e)}, status=400)
    
    @staticmethod
    def _get_client_ip(request):
        """Get client IP from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class AdminDashboardView(LoginRequiredMixin, TemplateView):
    """Admin dashboard for managing filters and viewing reports"""
    template_name = 'admin_dashboard.html'
    login_url = '/admin/login/'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        try:
            # Get all filters
            filters = Filter.objects.all()
            
            # Get latest reports
            latest_reports = {}
            for filter_instance in filters:
                try:
                    report = DailyReport.objects.filter(
                        filter=filter_instance
                    ).latest('report_date')
                    latest_reports[filter_instance.id] = report
                except DailyReport.DoesNotExist:
                    latest_reports[filter_instance.id] = None
            
            context['filters'] = filters
            context['latest_reports'] = latest_reports
            context['total_filters'] = filters.count()
            
            # Get statistics
            context['total_snapshots'] = TicketSnapshot.objects.count()
            context['total_updates'] = TicketUpdate.objects.count()
        
        except Exception as e:
            logger.error(f"Dashboard context error: {str(e)}")
        
        return context


class FilterDetailView(LoginRequiredMixin, TemplateView):
    """Detailed view of a filter"""
    template_name = 'filter_detail.html'
    login_url = '/admin/login/'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        try:
            filter_id = kwargs.get('filter_id')
            if not filter_id:
                raise ValueError("filter_id not provided")
                
            filter_instance = get_object_or_404(Filter, id=filter_id)
            logger.info(f"Loading filter: {filter_instance.id} - {filter_instance.name}")
            
            # Get all snapshots queryset (without slicing yet)
            all_snapshots = TicketSnapshot.objects.filter(
                filter=filter_instance
            ).order_by('-snapshot_date', '-created_at')
            
            # Get statistics BEFORE slicing (important!)
            total_tickets = all_snapshots.values('ticket_id').distinct().count()
            unique_assignees = all_snapshots.values_list('assignee', flat=True).distinct().count()
            
            # Now slice for display (latest 50)
            snapshots = all_snapshots[:50]
            
            # Get recent reports
            reports = DailyReport.objects.filter(
                filter=filter_instance
            ).order_by('-report_date')[:10]
            
            logger.info(f"Filter stats - Tickets: {total_tickets}, Assignees: {unique_assignees}, Snapshots: {snapshots.count()}")
            
            context['filter'] = filter_instance
            context['snapshots'] = snapshots
            context['reports'] = reports
            context['total_tickets'] = total_tickets
            context['unique_assignees'] = unique_assignees
        
        except Exception as e:
            logger.error(f"Filter detail error: {str(e)}", exc_info=True)
        
        return context


class ReportDetailView(LoginRequiredMixin, TemplateView):
    """View full markdown report"""
    template_name = 'report_detail.html'
    login_url = '/admin/login/'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        try:
            report_id = kwargs.get('report_id')
            report = get_object_or_404(DailyReport, id=report_id)
            
            context['report'] = report
            context['filter'] = report.filter
            
            # Convert markdown to HTML for preview
            try:
                import markdown
                html_content = markdown.markdown(report.markdown_content)
                context['html_content'] = html_content
            except:
                context['html_content'] = report.markdown_content
        
        except Exception as e:
            logger.error(f"Report detail error: {str(e)}")
        
        return context
