from rest_framework import status, permissions, filters
from rest_framework.viewsets import GenericViewSet
from rest_framework.response import Response
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Count
from django.utils import timezone

from apps.users.models import LoginAttempt, UserActivity, UserSession
from apps.users.serializers import (
    LoginAttemptSerializer, UserActivitySerializer, UserSessionSerializer
)
from apps.core.permissions import IsAdministrator
from apps.core.utils import get_client_ip


class LoginAttemptViewSet(GenericViewSet):
    """
    API endpoint that allows login attempts to be viewed.
    """
    queryset = LoginAttempt.objects.all()
    serializer_class = LoginAttemptSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdministrator]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['successful', 'tenant']
    search_fields = ['email', 'ip_address']
    ordering_fields = ['created_at']
    ordering = ['-created_at']
    
    def list(self, request):
        """
        List all login attempts with pagination.
        """
        queryset = self.filter_queryset(self.get_queryset())
        
        # Filter by tenant if user has one
        if not request.user.is_superuser and request.user.tenant:
            queryset = queryset.filter(tenant=request.user.tenant)
        
        # Filter by date range
        start_date = request.query_params.get('start_date', None)
        end_date = request.query_params.get('end_date', None)
        
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    def retrieve(self, request, pk=None):
        """
        Retrieve a login attempt instance.
        """
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """
        Get statistics about login attempts.
        """
        queryset = self.get_queryset()
        
        # Filter by tenant if user has one
        if not request.user.is_superuser and request.user.tenant:
            queryset = queryset.filter(tenant=request.user.tenant)
        
        # Filter by date range
        start_date = request.query_params.get('start_date', None)
        end_date = request.query_params.get('end_date', None)
        
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)
        
        # Get statistics
        total = queryset.count()
        successful = queryset.filter(successful=True).count()
        failed = queryset.filter(successful=False).count()
        
        # Get recent fails by IP
        recent_fails = queryset.filter(
            successful=False,
            created_at__gte=timezone.now() - timezone.timedelta(days=1)
        ).values('ip_address').annotate(
            count=Count('ip_address')
        ).order_by('-count')[:10]
        
        # Get fails by email
        fail_by_email = queryset.filter(
            successful=False
        ).values('email').annotate(
            count=Count('email')
        ).order_by('-count')[:10]
        
        return Response({
            'total': total,
            'successful': successful,
            'failed': failed,
            'success_rate': (successful / total * 100) if total > 0 else 0,
            'recent_fails_by_ip': recent_fails,
            'fails_by_email': fail_by_email
        })


class UserActivityViewSet(GenericViewSet):
    """
    API endpoint that allows user activities to be viewed.
    """
    queryset = UserActivity.objects.all()
    serializer_class = UserActivitySerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['activity_type', 'module', 'tenant']
    search_fields = ['description', 'user__email']
    ordering_fields = ['created_at', 'activity_type']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """
        Restrict to activities the user is allowed to see.
        """
        queryset = super().get_queryset()
        user = self.request.user
        
        # Admins can see all activities in their tenant
        if user.is_superuser or (
            hasattr(user, 'user_roles') and
            user.user_roles.filter(
                role__name='Administrator',
                is_active=True,
                is_deleted=False
            ).exists()
        ):
            if user.tenant and not user.is_superuser:
                return queryset.filter(tenant=user.tenant)
            return queryset
        
        # Regular users can only see their own activities
        return queryset.filter(user=user)
    
    def list(self, request):
        """
        List user activities with pagination.
        """
        queryset = self.filter_queryset(self.get_queryset())
        
        # Filter by user if provided
        user_id = request.query_params.get('user_id', None)
        if user_id and (request.user.is_superuser or (
            hasattr(request.user, 'user_roles') and
            request.user.user_roles.filter(
                role__name='Administrator',
                is_active=True,
                is_deleted=False
            ).exists()
        )):
            queryset = queryset.filter(user_id=user_id)
        
        # Filter by date range
        start_date = request.query_params.get('start_date', None)
        end_date = request.query_params.get('end_date', None)
        
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    def retrieve(self, request, pk=None):
        """
        Retrieve a user activity instance.
        """
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def my_activity(self, request):
        """
        Get the current user's activity.
        """
        queryset = UserActivity.objects.filter(user=request.user).order_by('-created_at')
        
        # Filter by type if provided
        activity_type = request.query_params.get('activity_type', None)
        if activity_type:
            queryset = queryset.filter(activity_type=activity_type)
        
        # Filter by date range
        start_date = request.query_params.get('start_date', None)
        end_date = request.query_params.get('end_date', None)
        
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def activity_types(self, request):
        """
        Get list of all activity types.
        """
        types = [choice[0] for choice in UserActivity.ACTIVITY_TYPES]
        return Response(types)
    
    @action(detail=False, methods=['get'])
    def modules(self, request):
        """
        Get list of all modules with user activity.
        """
        modules = UserActivity.objects.values_list('module', flat=True).distinct()
        return Response(sorted(list(set(modules))))


class UserSessionViewSet(GenericViewSet):
    """
    API endpoint that allows user sessions to be viewed.
    """
    queryset = UserSession.objects.all()
    serializer_class = UserSessionSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_expired', 'tenant']
    search_fields = ['user__email', 'ip_address', 'browser']
    ordering_fields = ['created_at', 'expires_at']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """
        Restrict to sessions the user is allowed to see.
        """
        queryset = super().get_queryset()
        user = self.request.user
        
        # Admins can see all sessions in their tenant
        if user.is_superuser or (
            hasattr(user, 'user_roles') and
            user.user_roles.filter(
                role__name='Administrator',
                is_active=True,
                is_deleted=False
            ).exists()
        ):
            if user.tenant and not user.is_superuser:
                return queryset.filter(tenant=user.tenant)
            return queryset
        
        # Regular users can only see their own sessions
        return queryset.filter(user=user)
    
    def list(self, request):
        """
        List user sessions with pagination.
        """
        queryset = self.filter_queryset(self.get_queryset())
        
        # Filter by user if provided
        user_id = request.query_params.get('user_id', None)
        if user_id and (request.user.is_superuser or (
            hasattr(request.user, 'user_roles') and
            request.user.user_roles.filter(
                role__name='Administrator',
                is_active=True,
                is_deleted=False
            ).exists()
        )):
            queryset = queryset.filter(user_id=user_id)
        
        # Filter by active/expired sessions
        active_only = request.query_params.get('active_only', None)
        if active_only and active_only.lower() == 'true':
            queryset = queryset.filter(is_expired=False, expires_at__gt=timezone.now())
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    def retrieve(self, request, pk=None):
        """
        Retrieve a user session instance.
        """
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def my_sessions(self, request):
        """
        Get the current user's active sessions.
        """
        queryset = UserSession.objects.filter(
            user=request.user,
            is_expired=False,
            expires_at__gt=timezone.now()
        ).order_by('-created_at')
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def terminate(self, request, pk=None):
        """
        Terminate a user session.
        """
        session = self.get_object()
        
        # Check if user has permission to terminate this session
        if str(session.user.id) != str(request.user.id) and not (
            request.user.is_superuser or (
                hasattr(request.user, 'user_roles') and
                request.user.user_roles.filter(
                    role__name='Administrator',
                    is_active=True,
                    is_deleted=False
                ).exists()
            )
        ):
            return Response(
                {"detail": "You do not have permission to terminate this session."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Terminate session
        session.is_expired = True
        session.logout_time = timezone.now()
        session.save()
        
        # Create activity log
        UserActivity.objects.create(
            user=request.user,
            activity_type='LOGOUT',
            description=f"Terminated session from {session.ip_address}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            module='USERS',
            tenant=request.user.tenant
        )
        
        return Response({"detail": "Session terminated successfully."})
    
    @action(detail=False, methods=['post'])
    def terminate_all(self, request):
        """
        Terminate all sessions for a user except the current one.
        """
        user_id = request.data.get('user_id', None)
        
        # If user_id is provided, check if current user has admin privileges
        if user_id and user_id != str(request.user.id):
            if not (
                request.user.is_superuser or (
                    hasattr(request.user, 'user_roles') and
                    request.user.user_roles.filter(
                        role__name='Administrator',
                        is_active=True,
                        is_deleted=False
                    ).exists()
                )
            ):
                return Response(
                    {"detail": "You do not have permission to terminate sessions for other users."},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Get target user's sessions
            from apps.users.models import User
            try:
                target_user = User.objects.get(id=user_id)
                sessions = UserSession.objects.filter(
                    user=target_user,
                    is_expired=False,
                    expires_at__gt=timezone.now()
                )
            except User.DoesNotExist:
                return Response(
                    {"detail": "User not found."},
                    status=status.HTTP_404_NOT_FOUND
                )
        else:
            # Get current user's sessions except the current one
            current_session_key = request.data.get('current_session_key', None)
            sessions = UserSession.objects.filter(
                user=request.user,
                is_expired=False,
                expires_at__gt=timezone.now()
            )
            if current_session_key:
                sessions = sessions.exclude(session_key=current_session_key)
        
        # Terminate sessions
        terminated_count = sessions.count()
        sessions.update(is_expired=True, logout_time=timezone.now())
        
        # Create activity log
        UserActivity.objects.create(
            user=request.user,
            activity_type='LOGOUT',
            description=f"Terminated {terminated_count} sessions",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            module='USERS',
            tenant=request.user.tenant
        )
        
        return Response({
            "detail": f"{terminated_count} sessions terminated successfully."
        })
