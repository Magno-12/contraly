from django.urls import path, include
from rest_framework.routers import DefaultRouter

from apps.payments.views import (
    PaymentViewSet,
    PaymentMethodViewSet,
    PaymentScheduleViewSet,
    PaymentStatusViewSet,
    WithholdingViewSet
)

router = DefaultRouter()
router.register(r'payments', PaymentViewSet)
router.register(r'payment-methods', PaymentMethodViewSet)
router.register(r'payment-schedules', PaymentScheduleViewSet)
router.register(r'payment-statuses', PaymentStatusViewSet)
router.register(r'withholdings', WithholdingViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
