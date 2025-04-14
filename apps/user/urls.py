from django.urls import path, include
from rest_framework.routers import DefaultRouter

from apps.user.views.role_view import RoleViewSet, PermissionViewSet
from apps.user.views.user_view import UserViewSet
from apps.user.views.activity_view import (
    LoginAttemptViewSet,
    UserActivityViewSet,
    UserSessionViewSet
)

router = DefaultRouter()
router.register(r'users', UserViewSet)
router.register(r'permissions', PermissionViewSet)
router.register(r'roles', RoleViewSet)
router.register(r'login-attempts', LoginAttemptViewSet)
router.register(r'activities', UserActivityViewSet)
router.register(r'sessions', UserSessionViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
