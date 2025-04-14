from rest_framework import status, permissions, filters
from rest_framework.viewsets import GenericViewSet
from rest_framework.response import Response
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend

from apps.user.models import Role, Permission, RolePermission, UserRole
from apps.user.serializers.role_serializer import (
    PermissionSerializer, RoleSerializer, RoleDetailSerializer,
    RoleCreateUpdateSerializer, UserRoleSerializer
)
from apps.core.permission import IsAdministrator
from apps.core.utils import create_audit_log, get_client_ip


class PermissionViewSet(GenericViewSet):
    """
    API endpoint that allows permissions to be viewed.
    """
    queryset = Permission.objects.filter(is_active=True, is_deleted=False)
    serializer_class = PermissionSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdministrator]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['permission_type', 'module']
    search_fields = ['name', 'code', 'description']
    ordering_fields = ['name', 'module', 'permission_type']
    ordering = ['module', 'permission_type', 'name']
    
    def list(self, request):
        """
        List all permissions.
        """
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    def retrieve(self, request, pk=None):
        """
        Retrieve a permission instance.
        """
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def modules(self, request):
        """
        Get list of available permission modules.
        """
        modules = Permission.objects.filter(
            is_active=True,
            is_deleted=False
        ).values_list('module', flat=True).distinct()
        
        return Response(sorted(list(set(modules))))
    
    @action(detail=False, methods=['get'])
    def by_module(self, request):
        """
        Get permissions grouped by module.
        """
        modules = Permission.objects.filter(
            is_active=True,
            is_deleted=False
        ).values_list('module', flat=True).distinct()
        
        result = {}
        for module in modules:
            permissions = Permission.objects.filter(
                module=module,
                is_active=True,
                is_deleted=False
            )
            serializer = self.get_serializer(permissions, many=True)
            result[module] = serializer.data
        
        return Response(result)
    
    @action(detail=False, methods=['get'])
    def types(self, request):
        """
        Get list of available permission types.
        """
        types = [choice[0] for choice in Permission.PERMISSION_TYPES]
        return Response(types)


class RoleViewSet(GenericViewSet):
    """
    API endpoint that allows roles to be viewed or edited.
    """
    queryset = Role.objects.filter(is_active=True, is_deleted=False)
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['tenant', 'is_system_role']
    search_fields = ['name', 'description']
    ordering_fields = ['name']
    ordering = ['name']
    permission_classes = [permissions.IsAuthenticated, IsAdministrator]
    
    def get_serializer_class(self):
        if self.action == 'list':
            return RoleSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return RoleCreateUpdateSerializer
        else:
            return RoleDetailSerializer
    
    def get_queryset(self):
        """
        Restricts the returned roles to those in the user's tenant.
        """
        queryset = super().get_queryset()
        user = self.request.user
        
        # Superusers can see all roles
        if user.is_superuser:
            return queryset
            
        # Other users can only see roles in their tenant
        if user.tenant:
            return queryset.filter(tenant=user.tenant)
        else:
            # If user has no tenant, they can only see tenant-less roles
            return queryset.filter(tenant__isnull=True)
    
    def list(self, request):
        """
        List all roles the current user has permission to see.
        """
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    def retrieve(self, request, pk=None):
        """
        Retrieve a role instance.
        """
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
    
    def create(self, request):
        """
        Create a new role.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Set tenant to the current user's tenant if not provided
        if 'tenant' not in serializer.validated_data and request.user.tenant:
            serializer.validated_data['tenant'] = request.user.tenant
        
        # Create role
        serializer.context['request'] = request
        role = serializer.save(created_by=request.user, updated_by=request.user)
        
        # Create audit log
        create_audit_log(
            user=request.user,
            action='CREATE',
            model_name='Role',
            instance_id=role.id,
            description=f"Created new role: {role.name}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            tenant=request.user.tenant
        )
        
        return Response(
            RoleDetailSerializer(role).data,
            status=status.HTTP_201_CREATED
        )
    
    def update(self, request, pk=None):
        """
        Update a role instance.
        """
        instance = self.get_object()
        
        # Check if it's a system role that cannot be modified
        if instance.is_system_role:
            return Response(
                {"detail": "System roles cannot be modified."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = self.get_serializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(updated_by=request.user)
        
        # Create audit log
        create_audit_log(
            user=request.user,
            action='UPDATE',
            model_name='Role',
            instance_id=instance.id,
            description=f"Updated role: {instance.name}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            tenant=request.user.tenant
        )
        
        return Response(
            RoleDetailSerializer(instance).data
        )
    
    def partial_update(self, request, pk=None):
        """
        Partially update a role instance.
        """
        instance = self.get_object()
        
        # Check if it's a system role that cannot be modified
        if instance.is_system_role:
            return Response(
                {"detail": "System roles cannot be modified."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(updated_by=request.user)
        
        # Create audit log
        create_audit_log(
            user=request.user,
            action='UPDATE',
            model_name='Role',
            instance_id=instance.id,
            description=f"Partially updated role: {instance.name}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            tenant=request.user.tenant
        )
        
        return Response(
            RoleDetailSerializer(instance).data
        )
    
    def destroy(self, request, pk=None):
        """
        Soft delete a role.
        """
        instance = self.get_object()
        
        # Check if it's a system role that cannot be deleted
        if instance.is_system_role:
            return Response(
                {"detail": "System roles cannot be deleted."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check if role is currently assigned to users
        if UserRole.objects.filter(
            role=instance,
            is_active=True,
            is_deleted=False
        ).exists():
            return Response(
                {"detail": "Cannot delete a role that is still assigned to users."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Soft delete
        instance.is_active = False
        instance.is_deleted = True
        instance.updated_by = request.user
        instance.save()
        
        # Soft delete all role permissions
        RolePermission.objects.filter(role=instance).update(
            is_active=False,
            is_deleted=True,
            updated_by=request.user
        )
        
        # Create audit log
        create_audit_log(
            user=request.user,
            action='DELETE',
            model_name='Role',
            instance_id=instance.id,
            description=f"Deleted role: {instance.name}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            tenant=request.user.tenant
        )
        
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    @action(detail=True, methods=['get'])
    def users(self, request, pk=None):
        """
        Get list of users with this role.
        """
        role = self.get_object()
        
        users = role.role_users.filter(
            is_active=True,
            is_deleted=False
        ).select_related('user')
        
        # Create a list of users with this role
        result = []
        for user_role in users:
            if not user_role.user.is_deleted:
                from apps.users.serializers import UserListSerializer
                result.append(UserListSerializer(user_role.user).data)
        
        return Response(result)
    
    @action(detail=True, methods=['post'])
    def assign_permission(self, request, pk=None):
        """
        Assign a permission to this role.
        """
        role = self.get_object()
        
        # Check if it's a system role that cannot be modified
        if role.is_system_role:
            return Response(
                {"detail": "System roles cannot be modified."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Validate permission id
        permission_id = request.data.get('permission_id')
        if not permission_id:
            return Response(
                {"detail": "Permission ID is required."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            permission = Permission.objects.get(id=permission_id, is_active=True, is_deleted=False)
        except Permission.DoesNotExist:
            return Response(
                {"detail": "Permission not found."},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Create or reactivate role permission
        role_perm, created = RolePermission.objects.get_or_create(
            role=role,
            permission=permission,
            defaults={
                'created_by': request.user,
                'is_active': True,
                'is_deleted': False
            }
        )
        
        if not created:
            # Reactivate if it was deleted
            role_perm.is_active = True
            role_perm.is_deleted = False
            role_perm.updated_by = request.user
            role_perm.save()
        
        # Create audit log
        create_audit_log(
            user=request.user,
            action='UPDATE',
            model_name='RolePermission',
            instance_id=role_perm.id,
            description=f"Assigned permission '{permission.name}' to role '{role.name}'",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            tenant=request.user.tenant
        )
        
        return Response(
            {"detail": "Permission assigned successfully."},
            status=status.HTTP_200_OK
        )
