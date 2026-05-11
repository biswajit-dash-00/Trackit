"""Django REST Framework views"""
import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.shortcuts import get_object_or_404
from core.models import (
    Filter, TicketSnapshot, TicketUpdate, DailyReport, EmailToken
)
from api.serializers import (
    FilterSerializer, TicketSnapshotSerializer,
    TicketUpdateSerializer, DailyReportSerializer
)
from utils.jira_service import JiraService
from utils.token_service import TokenService

logger = logging.getLogger(__name__)


class FilterViewSet(viewsets.ModelViewSet):
    """ViewSet for managing Jira filters"""
    queryset = Filter.objects.all()
    serializer_class = FilterSerializer
    permission_classes = [IsAuthenticated]
    
    @action(detail=True, methods=['post'])
    def validate_jira_filter(self, request, pk=None):
        """Validate if a Jira filter exists and is accessible"""
        try:
            filter_instance = self.get_object()
            jira_service = JiraService()
            
            is_valid = jira_service.validate_filter(filter_instance.jira_filter_id)
            
            return Response({
                'valid': is_valid,
                'message': 'Filter is valid' if is_valid else 'Filter not found or not accessible'
            })
        except Exception as e:
            logger.error(f"Filter validation failed: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['get'])
    def snapshots(self, request, pk=None):
        """Get snapshots for a filter"""
        try:
            filter_instance = self.get_object()
            
            snapshots = TicketSnapshot.objects.filter(
                filter=filter_instance
            ).order_by('-snapshot_date')[:100]
            
            serializer = TicketSnapshotSerializer(snapshots, many=True)
            return Response(serializer.data)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['get'])
    def latest_report(self, request, pk=None):
        """Get latest report for a filter"""
        try:
            filter_instance = self.get_object()
            
            report = DailyReport.objects.filter(
                filter=filter_instance
            ).latest('report_date')
            
            serializer = DailyReportSerializer(report)
            return Response(serializer.data)
        except DailyReport.DoesNotExist:
            return Response(
                {'message': 'No report found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class TicketSnapshotViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for viewing ticket snapshots"""
    queryset = TicketSnapshot.objects.all()
    serializer_class = TicketSnapshotSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter snapshots by filter ID"""
        filter_id = self.request.query_params.get('filter_id')
        if filter_id:
            return self.queryset.filter(filter_id=filter_id)
        return self.queryset


class TicketUpdateViewSet(viewsets.ModelViewSet):
    """ViewSet for managing ticket updates"""
    queryset = TicketUpdate.objects.all()
    serializer_class = TicketUpdateSerializer
    
    @action(detail=False, methods=['post'])
    def submit_updates(self, request):
        """
        Submit updates from secure token
        
        Expected body:
        {
            'token': 'jwt_token',
            'updates': [
                {
                    'ticket_id': 'BUG-101',
                    'eta': 'Tomorrow EOD',
                    'update_note': 'Fixed issue',
                    'blockers': ''
                }
            ]
        }
        """
        try:
            token = request.data.get('token')
            updates = request.data.get('updates', [])
            
            if not token:
                return Response(
                    {'error': 'Token required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Validate token
            try:
                payload = TokenService.validate_token(token)
            except Exception as e:
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            filter_id = payload.get('filter_id')
            assignee_email = payload.get('assignee_email')
            
            # Mark token as used
            try:
                email_token = EmailToken.objects.get(token=token)
                email_token.mark_used(ip_address=self._get_client_ip(request))
            except EmailToken.DoesNotExist:
                pass
            
            # Save updates
            from django.utils import timezone
            created_count = 0
            for update_data in updates:
                try:
                    # Delete any previous update for this ticket today
                    TicketUpdate.objects.filter(
                        ticket_id=update_data['ticket_id'],
                        assignee=assignee_email,
                        submitted_at__date=timezone.now().date()
                    ).delete()
                    
                    # Create the new update
                    TicketUpdate.objects.create(
                        ticket_id=update_data['ticket_id'],
                        assignee=assignee_email,
                        eta=update_data.get('eta', ''),
                        update_note=update_data.get('update_note', ''),
                        blockers=update_data.get('blockers', ''),
                    )
                    created_count += 1
                except Exception as e:
                    logger.error(f"Failed to save update: {str(e)}")
                    continue
            
            return Response({
                'message': f'{created_count} updates saved',
                'count': created_count
            })
        
        except Exception as e:
            logger.error(f"Update submission failed: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @staticmethod
    def _get_client_ip(request):
        """Get client IP from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class DailyReportViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for viewing daily reports"""
    queryset = DailyReport.objects.all()
    serializer_class = DailyReportSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter reports by filter ID"""
        filter_id = self.request.query_params.get('filter_id')
        if filter_id:
            return self.queryset.filter(filter_id=filter_id)
        return self.queryset
