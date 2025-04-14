from django.urls import path, include
from rest_framework.routers import DefaultRouter

from apps.core.views.configuration_view import ConfigurationSettingViewSet
from apps.core.views.audit_view import (
    AuditLogViewSet,
    SystemLogViewSet
)

router = DefaultRouter()
router.register(r'configuration', ConfigurationSettingViewSet)
router.register(r'audit-logs', AuditLogViewSet)
router.register(r'system-logs', SystemLogViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
