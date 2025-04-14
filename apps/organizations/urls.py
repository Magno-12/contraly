from django.urls import path, include
from rest_framework.routers import DefaultRouter

from apps.organizations.views.organizations_view import (
    OrganizationViewSet,
    OrganizationMemberViewSet,
    OrganizationInvitationViewSet
)

router = DefaultRouter()
router.register(r'organizations', OrganizationViewSet)
router.register(r'members', OrganizationMemberViewSet)
router.register(r'invitations', OrganizationInvitationViewSet)

urlpatterns = [
    path('', include(router.urls)),
]