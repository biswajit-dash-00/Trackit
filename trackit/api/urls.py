"""API URL configuration"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from api.views import (
    FilterViewSet, TicketSnapshotViewSet,
    TicketUpdateViewSet, DailyReportViewSet
)

router = DefaultRouter()
router.register(r'filters', FilterViewSet)
router.register(r'snapshots', TicketSnapshotViewSet)
router.register(r'updates', TicketUpdateViewSet)
router.register(r'reports', DailyReportViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
