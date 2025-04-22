from django.urls import path, include
from rest_framework.routers import DefaultRouter

from apps.invoices.views import (
    InvoiceViewSet,
    InvoiceItemViewSet,
    InvoiceStatusViewSet,
    InvoiceApprovalViewSet,
    InvoiceScheduleViewSet
)

router = DefaultRouter()
router.register(r'invoices', InvoiceViewSet)
router.register(r'invoice-items', InvoiceItemViewSet)
router.register(r'invoice-statuses', InvoiceStatusViewSet)
router.register(r'invoice-approvals', InvoiceApprovalViewSet)
router.register(r'invoice-schedules', InvoiceScheduleViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
