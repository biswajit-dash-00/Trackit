"""Core app URL configuration"""
from django.urls import path
from core.views import (
    UpdatePageView, AdminDashboardView,
    FilterDetailView, ReportDetailView
)
from core.health import health_check, detailed_health_check

urlpatterns = [
    path('health/', health_check, name='health_check'),
    path('health/detailed/', detailed_health_check, name='detailed_health_check'),
    path('update/<str:token>/', UpdatePageView.as_view(), name='update_page'),
    path('dashboard/', AdminDashboardView.as_view(), name='admin_dashboard'),
    path('filters/<int:filter_id>/', FilterDetailView.as_view(), name='filter_detail'),
    path('reports/<int:report_id>/', ReportDetailView.as_view(), name='report_detail'),
]
