from django.urls import path, include
from rest_framework.routers import DefaultRouter

from apps.authentication.views.authtentication_view import AuthenticationViewSet

router = DefaultRouter()
router.register(r'', AuthenticationViewSet, basename='auth')

urlpatterns = [
    path('', include(router.urls)),
]
