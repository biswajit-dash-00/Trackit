"""Django REST Framework serializers"""
from rest_framework import serializers
from core.models import Filter, TicketSnapshot, TicketUpdate, DailyReport


class FilterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Filter
        fields = [
            'id', 'name', 'jira_filter_id', 'snapshot_time',
            'report_time', 'admin_email', 'active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class TicketSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = TicketSnapshot
        fields = [
            'id', 'filter', 'ticket_id', 'title', 'assignee',
            'status', 'priority', 'updated', 'snapshot_date'
        ]


class TicketUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = TicketUpdate
        fields = [
            'id', 'ticket_id', 'assignee', 'eta',
            'update_note', 'blockers', 'submitted_at'
        ]
        read_only_fields = ['id', 'submitted_at']


class DailyReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyReport
        fields = [
            'id', 'filter', 'report_date', 'markdown_content',
            'sent_at', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
