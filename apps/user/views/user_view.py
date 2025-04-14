from rest_framework import status, permissions, filters
from rest_framework.viewsets import GenericViewSet
from rest_framework.response import Response
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q
from django.utils import timezone

from apps.users.models import User, UserProfile, UserRole, UserActivity
from apps.users.serializers import (
    UserListSerializer, UserDetailSerializer, UserCreateSerializer,
    PasswordChangeSerializer, UserProfileSerializer
)
from apps.core.permissions import IsAdministrator
from apps.core.utils import create_audit_log, get_client_ip


class UserViewSet(GenericViewSet):
    """
    API endpoint that allows users to be viewed or edited.
    """
    queryset = User.objects.filter(is_deleted=False)
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active', 'tenant']
    search_fields = ['email', 'first_name', 'last_name', 'phone_number']
    ordering_fields = ['email', 'first_name', 'last_name', 'date_joined', 'last_login']
    ordering = ['-date_joined']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return UserListSerializer
        elif self.action == 'create':
            return UserCreateSerializer
        elif self.action == 'change_password':
            return PasswordChangeSerializer
        else:
            return UserDetailSerializer
    
    def get_permissions(self):
        """
        Instantiates and returns the list of permissions that this view requires.
        """
        if self.action in ['retrieve', 'update', 'partial_update', 'destroy', 'change_password']:
            permission_classes = [permissions.IsAuthenticated]
        else:
            permission_classes = [permissions.IsAuthenticated, IsAdministrator]
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        """
        Restricts the returned users to those that the current user has permission to view.
        """
        queryset = super().get_queryset()
        user = self.request.user
        
        # Superusers can see all users
        if user.is_superuser:
            return queryset
        
        # Administrators can see users in their tenant
        if hasattr(user, 'user_roles') and user.user_roles.filter(
            role__name='Administrator',
            is_active=True,
            is_deleted=False
        ).exists():
            if user.tenant:
                return queryset.filter(tenant=user.tenant)
            else:
                # User is admin but has no tenant, can only see themselves
                return queryset.filter(id=user.id)
        
        # Regular users can only see themselves
        return queryset.filter(id=user.id)
    
    def list(self, request):
        """
        List all users the current user has permission to see.
        """
        queryset = self.filter_queryset(self.get_queryset())
        
        # Filter by role if provided
        role = request.query_params.get('role', None)
        if role:
            queryset = queryset.filter(user_roles__role__name=role, user_roles__is_active=True)
        
        # Filter by search term across multiple fields
        search = request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                Q(email__icontains=search) |
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(phone_number__icontains=search)
            )
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    def retrieve(self, request, pk=None):
        """
        Retrieve a user instance.
        """
        instance = self.get_object()
        
        # Check if user is trying to access their own profile or has admin permissions
        if str(instance.id) != str(request.user.id) and not (
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
                {"detail": "You do not have permission to view this user."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = self.get_serializer(instance)
        
        # Log user activity
        UserActivity.objects.create(
            user=request.user,
            activity_type='VIEW',
            description=f"Viewed user profile for {instance.email}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            module='USERS',
            tenant=request.user.tenant
        )
        
        return Response(serializer.data)
    
    def create(self, request):
        """
        Create a new user.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Set tenant to the current user's tenant if not provided
        if 'tenant' not in serializer.validated_data and request.user.tenant:
            serializer.validated_data['tenant'] = request.user.tenant
        
        # Create user
        serializer.context['request'] = request
        user = serializer.save()
        
        # Create audit log
        create_audit_log(
            user=request.user,
            action='CREATE',
            model_name='User',
            instance_id=user.id,
            description=f"Created new user: {user.email}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            tenant=request.user.tenant
        )
        
        return Response(
            UserDetailSerializer(user).data,
            status=status.HTTP_201_CREATED
        )
    
    def update(self, request, pk=None):
        """
        Update a user instance.
        """
        instance = self.get_object()
        
        # Check if user is trying to update their own profile or has admin permissions
        if str(instance.id) != str(request.user.id) and not (
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
                {"detail": "You do not have permission to update this user."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = self.get_serializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        # Create audit log
        create_audit_log(
            user=request.user,
            action='UPDATE',
            model_name='User',
            instance_id=instance.id,
            description=f"Updated user: {instance.email}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            tenant=request.user.tenant
        )
        
        return Response(serializer.data)
    
    def partial_update(self, request, pk=None):
        """
        Partially update a user instance.
        """
        instance = self.get_object()
        
        # Check if user is trying to update their own profile or has admin permissions
        if str(instance.id) != str(request.user.id) and not (
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
                {"detail": "You do not have permission to update this user."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        # Create audit log
        create_audit_log(
            user=request.user,
            action='UPDATE',
            model_name='User',
            instance_id=instance.id,
            description=f"Partially updated user: {instance.email}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            tenant=request.user.tenant
        )
        
        return Response(serializer.data)
    
    def destroy(self, request, pk=None):
        """
        Soft delete a user instance.
        """
        instance = self.get_object()
        
        # Only admins can delete users
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
                {"detail": "You do not have permission to delete users."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Users cannot delete themselves
        if str(instance.id) == str(request.user.id):
            return Response(
                {"detail": "You cannot delete your own account."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Soft delete user
        instance.soft_delete()
        
        # Create audit log
        create_audit_log(
            user=request.user,
            action='DELETE',
            model_name='User',
            instance_id=instance.id,
            description=f"Deleted user: {instance.email}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            tenant=request.user.tenant
        )
        
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    @action(detail=True, methods=['post'])
    def change_password(self, request, pk=None):
        """
        Change a user's password.
        """
        user = self.get_object()
        
        # Users can only change their own password
        if str(user.id) != str(request.user.id):
            return Response(
                {"detail": "You can only change your own password."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Change password
        user.set_password(serializer.validated_data['new_password'])
        user.must_change_password = False
        user.save()
        
        # Create audit log
        create_audit_log(
            user=request.user,
            action='UPDATE',
            model_name='User',
            instance_id=user.id,
            description=f"Changed password for user: {user.email}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            tenant=request.user.tenant
        )
        
        return Response({"detail": "Password successfully changed."})
    
    @action(detail=False, methods=['get'])
    def me(self, request):
        """
        Get the current user's profile.
        """
        user = request.user
        serializer = UserDetailSerializer(user)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def roles(self, request):
        """
        Get list of users grouped by role.
        """
        # Only admins can access this endpoint
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
                {"detail": "You do not have permission to access this endpoint."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get roles and users
        from apps.users.models import Role
        
        result = {}
        queryset = self.get_queryset()
        
        # Filter by tenant
        if request.user.tenant:
            roles = Role.objects.filter(tenant=request.user.tenant, is_active=True)
        else:
            roles = Role.objects.filter(is_active=True)
        
        for role in roles:
            users = queryset.filter(
                user_roles__role=role,
                user_roles__is_active=True,
                user_roles__is_deleted=False
            )
            serializer = UserListSerializer(users, many=True)
            result[role.name] = serializer.data
        
        return Response(result)
