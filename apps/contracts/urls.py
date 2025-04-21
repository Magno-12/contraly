from django.urls import path, include
from rest_framework.routers import DefaultRouter

from apps.contracts.views import (
    ContractViewSet,
    ContractPartyViewSet,
    ContractDocumentViewSet,
    ContractRevisionViewSet,
    ContractStatusViewSet,
    ContractTypeViewSet
)

router = DefaultRouter()
router.register(r'contracts', ContractViewSet)
router.register(r'contract-parties', ContractPartyViewSet)
router.register(r'contract-documents', ContractDocumentViewSet)
router.register(r'contract-revisions', ContractRevisionViewSet)
router.register(r'contract-statuses', ContractStatusViewSet)
router.register(r'contract-types', ContractTypeViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
