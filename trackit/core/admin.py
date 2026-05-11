"""Django admin configuration"""
from django.contrib import admin
from django.utils.html import format_html
from core.models import (
    Filter, TicketSnapshot, TicketUpdate, EmailToken,
    SnapshotComparison, DailyAnalytics, DailyReport
)


@admin.register(Filter)
class FilterAdmin(admin.ModelAdmin):
    list_display = ('name', 'jira_filter_id', 'snapshot_time', 'report_time', 'active_status', 'created_at')
    list_filter = ('active', 'created_at')
    search_fields = ('name', 'jira_filter_id', 'admin_email')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('Filter Information', {
            'fields': ('name', 'jira_filter_id', 'active')
        }),
        ('Schedule', {
            'fields': ('snapshot_time', 'report_time')
        }),
        ('Contact', {
            'fields': ('admin_email',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def active_status(self, obj):
        if obj.active:
            return format_html('<span style="color: green;">✓ Active</span>')
        return format_html('<span style="color: red;">✗ Inactive</span>')
    active_status.short_description = 'Status'


@admin.register(TicketSnapshot)
class TicketSnapshotAdmin(admin.ModelAdmin):
    list_display = ('ticket_id', 'filter', 'assignee', 'status_badge', 'priority_badge', 'snapshot_date')
    list_filter = ('filter', 'status', 'priority', 'snapshot_date')
    search_fields = ('ticket_id', 'assignee', 'title')
    readonly_fields = ('created_at', 'snapshot_json')
    date_hierarchy = 'snapshot_date'
    fieldsets = (
        ('Ticket Details', {
            'fields': ('filter', 'ticket_id', 'title', 'assignee')
        }),
        ('Status', {
            'fields': ('status', 'priority', 'updated')
        }),
        ('Snapshot', {
            'fields': ('snapshot_date', 'created_at')
        }),
        ('Raw Data', {
            'fields': ('snapshot_json',),
            'classes': ('collapse',)
        }),
    )
    
    def status_badge(self, obj):
        colors = {
            'Open': '#0066cc',
            'In Progress': '#ff9800',
            'Done': '#28a745',
            'Closed': '#6c757d',
        }
        color = colors.get(obj.status, '#999')
        return format_html(f'<span style="background-color: {color}; color: white; padding: 4px 8px; border-radius: 3px;">{obj.status}</span>')
    status_badge.short_description = 'Status'
    
    def priority_badge(self, obj):
        colors = {
            'High': '#dc3545',
            'Medium': '#ffc107',
            'Low': '#28a745',
        }
        color = colors.get(obj.priority, '#999')
        return format_html(f'<span style="background-color: {color}; color: white; padding: 4px 8px; border-radius: 3px;">{obj.priority}</span>')
    priority_badge.short_description = 'Priority'


@admin.register(TicketUpdate)
class TicketUpdateAdmin(admin.ModelAdmin):
    list_display = ('ticket_id', 'assignee', 'eta_display', 'submitted_at')
    list_filter = ('submitted_at', 'assignee')
    search_fields = ('ticket_id', 'assignee')
    readonly_fields = ('submitted_at',)
    date_hierarchy = 'submitted_at'
    fieldsets = (
        ('Ticket', {
            'fields': ('ticket_id', 'assignee')
        }),
        ('Update Details', {
            'fields': ('eta', 'update_note', 'blockers')
        }),
        ('Submission', {
            'fields': ('submitted_at',)
        }),
    )
    
    def eta_display(self, obj):
        return obj.eta if obj.eta else '-'
    eta_display.short_description = 'ETA'


@admin.register(EmailToken)
class EmailTokenAdmin(admin.ModelAdmin):
    list_display = ('assignee_email', 'filter', 'used_status', 'expires_at', 'created_at')
    list_filter = ('used', 'filter', 'created_at', 'expires_at')
    search_fields = ('assignee_email', 'token')
    readonly_fields = ('token', 'created_at', 'used_at')
    fieldsets = (
        ('Token', {
            'fields': ('token', 'assignee_email', 'filter')
        }),
        ('Validity', {
            'fields': ('expires_at', 'used', 'used_at')
        }),
        ('Security', {
            'fields': ('ip_address',)
        }),
        ('Timestamps', {
            'fields': ('created_at',)
        }),
    )
    
    def used_status(self, obj):
        if obj.used:
            return format_html('<span style="color: green;">✓ Used</span>')
        elif obj.is_valid():
            return format_html('<span style="color: blue;">→ Valid</span>')
        else:
            return format_html('<span style="color: red;">✗ Expired</span>')
    used_status.short_description = 'Status'


@admin.register(SnapshotComparison)
class SnapshotComparisonAdmin(admin.ModelAdmin):
    list_display = ('filter', 'comparison_date', 'new_count', 'removed_count', 'changes_count')
    list_filter = ('filter', 'comparison_date')
    readonly_fields = ('new_tickets', 'removed_tickets', 'status_changes', 'created_at')
    fieldsets = (
        ('Comparison', {
            'fields': ('filter', 'comparison_date')
        }),
        ('Results', {
            'fields': ('new_tickets', 'removed_tickets', 'status_changes')
        }),
        ('Timestamps', {
            'fields': ('created_at',)
        }),
    )
    
    def new_count(self, obj):
        return len(obj.new_tickets)
    new_count.short_description = 'New'
    
    def removed_count(self, obj):
        return len(obj.removed_tickets)
    removed_count.short_description = 'Removed'
    
    def changes_count(self, obj):
        return len(obj.status_changes)
    changes_count.short_description = 'Changes'


@admin.register(DailyAnalytics)
class DailyAnalyticsAdmin(admin.ModelAdmin):
    list_display = ('filter', 'analytics_date', 'total_tickets', 'updated_count', 'compliance')
    list_filter = ('filter', 'analytics_date')
    readonly_fields = ('assignee_metrics', 'no_update_assignees', 'resolved_by_assignee', 'analytics_data', 'created_at')
    fieldsets = (
        ('Analytics', {
            'fields': ('filter', 'analytics_date')
        }),
        ('Metrics', {
            'fields': ('total_tickets', 'updated_count', 'missed_count', 'new_tickets_count', 'resolved_count')
        }),
        ('Details', {
            'fields': ('assignee_metrics', 'no_update_assignees', 'resolved_by_assignee'),
            'classes': ('collapse',)
        }),
        ('Full Data', {
            'fields': ('analytics_data',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at',)
        }),
    )
    
    def compliance(self, obj):
        if obj.total_tickets > 0:
            rate = (obj.updated_count / obj.total_tickets) * 100
            return f'{rate:.1f}%'
        return '-'
    compliance.short_description = 'Compliance'


@admin.register(DailyReport)
class DailyReportAdmin(admin.ModelAdmin):
    list_display = ('filter', 'report_date', 'sent_status', 'created_at')
    list_filter = ('filter', 'report_date', 'sent_at')
    readonly_fields = ('markdown_content', 'created_at', 'sent_at')
    fieldsets = (
        ('Report', {
            'fields': ('filter', 'report_date')
        }),
        ('Content', {
            'fields': ('markdown_content',)
        }),
        ('Delivery', {
            'fields': ('sent_at',)
        }),
        ('Timestamps', {
            'fields': ('created_at',)
        }),
    )
    
    def sent_status(self, obj):
        if obj.sent_at:
            return format_html(f'<span style="color: green;">✓ Sent</span>')
        return format_html('<span style="color: orange;">⧖ Pending</span>')
    sent_status.short_description = 'Status'

# Customize admin site
admin.site.site_header = "TrackIt Administration"
admin.site.site_title = "TrackIt Admin"
admin.site.index_title = "Welcome to TrackIt Admin"
