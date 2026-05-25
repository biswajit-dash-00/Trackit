"""Core app URL configuration"""
from django.urls import path
from django.views.generic import RedirectView
from core.views import (
    UpdatePageView, AdminDashboardView,
    FilterDetailView, ReportDetailView,
    FilterCreateView, FilterEditView
)
from core.health import health_check, detailed_health_check

urlpatterns = [
    path('', RedirectView.as_view(url='/dashboard/', permanent=False)),
    path('health/', health_check, name='health_check'),
    path('health/detailed/', detailed_health_check, name='detailed_health_check'),
    path('update/<str:token>/', UpdatePageView.as_view(), name='update_page'),
    path('dashboard/', AdminDashboardView.as_view(), name='admin_dashboard'),
    path('filters/create/', FilterCreateView.as_view(), name='filter_create'),
    path('filters/<int:filter_id>/edit/', FilterEditView.as_view(), name='filter_edit'),
    path('filters/<int:filter_id>/', FilterDetailView.as_view(), name='filter_detail'),
    path('reports/<int:report_id>/', ReportDetailView.as_view(), name='report_detail'),
]
