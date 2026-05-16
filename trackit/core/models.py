from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import json

class Filter(models.Model):
    """Jira Filter Configuration"""
    name = models.CharField(max_length=255)
    jira_filter_id = models.CharField(max_length=255)
    snapshot_time = models.TimeField(help_text="Time to take snapshot (HH:MM format)")
    report_time = models.TimeField(help_text="Time to generate and send report (HH:MM format)")
    admin_email = models.EmailField()
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return self.name


class TicketSnapshot(models.Model):
    """Daily snapshot of Jira tickets"""
    
    filter = models.ForeignKey(Filter, on_delete=models.CASCADE, related_name='snapshots')
    ticket_id = models.CharField(max_length=100)
    title = models.CharField(max_length=500)
    assignee = models.CharField(max_length=255)
    status = models.CharField(max_length=100)
    priority = models.CharField(max_length=50, default='Medium')
    updated = models.DateTimeField()
    snapshot_date = models.DateField()
    snapshot_json = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-snapshot_date', '-created_at']
        indexes = [
            models.Index(fields=['filter', 'snapshot_date']),
            models.Index(fields=['ticket_id', 'snapshot_date']),
        ]
    
    def __str__(self):
        return f"{self.ticket_id} - {self.snapshot_date}"


class TicketUpdate(models.Model):
    """Assignee updates for tickets"""
    ticket_id = models.CharField(max_length=100)
    assignee = models.CharField(max_length=255)
    eta = models.CharField(max_length=255, blank=True, null=True)
    update_note = models.TextField(blank=True)
    blockers = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-submitted_at']
        indexes = [
            models.Index(fields=['ticket_id', 'submitted_at']),
            models.Index(fields=['assignee', 'submitted_at']),
        ]
    
    def __str__(self):
        return f"{self.ticket_id} - {self.assignee}"


class EmailToken(models.Model):
    """Secure tokenized email links"""
    assignee_email = models.EmailField()
    token = models.CharField(max_length=500, unique=True)
    filter = models.ForeignKey(Filter, on_delete=models.CASCADE, related_name='email_tokens')
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)
    used_at = models.DateTimeField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['token']),
            models.Index(fields=['expires_at']),
        ]
    
    def is_valid(self):
        """Check if token is still valid"""
        return not self.used and timezone.now() < self.expires_at
    
    def mark_used(self, ip_address=None):
        """Mark token as used"""
        self.used = True
        self.used_at = timezone.now()
        if ip_address:
            self.ip_address = ip_address
        self.save()
    
    def __str__(self):
        return f"{self.assignee_email} - {self.filter.name}"


class DailyAnalytics(models.Model):
    """Computed analytics for daily report"""
    filter = models.ForeignKey(Filter, on_delete=models.CASCADE, related_name='analytics')
    analytics_date = models.DateField()
    total_tickets = models.IntegerField(default=0)
    updated_count = models.IntegerField(default=0)
    missed_count = models.IntegerField(default=0)
    new_tickets_count = models.IntegerField(default=0)
    resolved_count = models.IntegerField(default=0)
    assignee_metrics = models.JSONField(default=dict)  # {assignee: {tickets: count, updated: bool, resolved: count}}
    no_update_assignees = models.JSONField(default=list)  # List of assignees who didn't update
    resolved_by_assignee = models.JSONField(default=dict)  # {assignee: count}
    analytics_data = models.JSONField(default=dict)  # Full analytics data
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-analytics_date']
        indexes = [
            models.Index(fields=['filter', 'analytics_date']),
        ]
    
    def __str__(self):
        return f"{self.filter.name} - {self.analytics_date}"


class DailyReport(models.Model):
    """Generated markdown report"""
    filter = models.ForeignKey(Filter, on_delete=models.CASCADE, related_name='reports')
    report_date = models.DateField()
    markdown_content = models.TextField()
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-report_date']
        indexes = [
            models.Index(fields=['filter', 'report_date']),
        ]
    
    def __str__(self):
        return f"{self.filter.name} - {self.report_date}"
