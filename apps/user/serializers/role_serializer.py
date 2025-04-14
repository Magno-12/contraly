from rest_framework import serializers
from apps.user.models import Role, Permission, RolePermission, UserRole


class PermissionSerializer(serializers.ModelSerializer):
    """Serializer for permission model"""
    
    class Meta:
        model = Permission
        fields = ['id', 'name', 'code', 'description', 'permission_type', 
                 'module', 'is_active', 'created_at']
        read_only_fields = ['id', 'created_at']


class RoleSerializer(serializers.ModelSerializer):
    """Serializer for role model"""
    permissions = serializers.SerializerMethodField()
    user_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Role
        fields = ['id', 'name', 'description', 'is_system_role', 'tenant', 
                 'is_active', 'created_at', 'permissions', 'user_count']
        read_only_fields = ['id', 'created_at', 'user_count']
    
    def get_permissions(self, obj):
        permission_ids = RolePermission.objects.filter(
            role=obj, 
            is_active=True, 
            is_deleted=False
        ).values_list('permission_id', flat=True)
        
        return list(permission_ids)
    
    def get_user_count(self, obj):
        return UserRole.objects.filter(
            role=obj, 
            is_active=True, 
            is_deleted=False
        ).count()


class RoleDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for role model with permissions"""
    permissions = serializers.SerializerMethodField()
    permission_details = serializers.SerializerMethodField()
    user_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Role
        fields = ['id', 'name', 'description', 'is_system_role', 'tenant', 
                 'is_active', 'created_at', 'created_by', 'updated_at', 
                 'updated_by', 'permissions', 'permission_details', 'user_count']
        read_only_fields = ['id', 'created_at', 'created_by', 'updated_at', 'updated_by', 'user_count']
    
    def get_permissions(self, obj):
        return list(RolePermission.objects.filter(
            role=obj, 
            is_active=True, 
            is_deleted=False
        ).values_list('permission_id', flat=True))
    
    def get_permission_details(self, obj):
        permission_ids = RolePermission.objects.filter(
            role=obj, 
            is_active=True, 
            is_deleted=False
        ).values_list('permission_id', flat=True)
        
        permissions = Permission.objects.filter(id__in=permission_ids)
        return PermissionSerializer(permissions, many=True).data
    
    def get_user_count(self, obj):
        return UserRole.objects.filter(
            role=obj, 
            is_active=True, 
            is_deleted=False
        ).count()


class RoleCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating and updating roles with permissions"""
    permissions = serializers.ListField(
        child=serializers.UUIDField(), 
        required=False,
        write_only=True
    )
    
    class Meta:
        model = Role
        fields = ['id', 'name', 'description', 'is_system_role', 'tenant', 
                 'is_active', 'permissions']
        read_only_fields = ['id']
    
    def create(self, validated_data):
        permissions = validated_data.pop('permissions', [])
        role = Role.objects.create(**validated_data)
        
        # Assign permissions
        self._assign_permissions(role, permissions)
        return role
    
    def update(self, instance, validated_data):
        permissions = validated_data.pop('permissions', None)
        
        # Update role fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Update permissions if provided
        if permissions is not None:
            # Clear existing permissions
            RolePermission.objects.filter(
                role=instance
            ).update(is_active=False, is_deleted=True)
            
            # Assign new permissions
            self._assign_permissions(instance, permissions)
            
        return instance
    
    def _assign_permissions(self, role, permission_ids):
        """Helper method to assign permissions to a role"""
        request = self.context.get('request')
        created_by = request.user if request else None
        
        for perm_id in permission_ids:
            try:
                permission = Permission.objects.get(id=perm_id)
                
                # Check if relationship exists but was soft-deleted
                role_perm, created = RolePermission.objects.get_or_create(
                    role=role,
                    permission=permission,
                    defaults={
                        'created_by': created_by,
                        'is_active': True,
                        'is_deleted': False
                    }
                )
                
                if not created:
                    # Reactivate if it was deleted
                    role_perm.is_active = True
                    role_perm.is_deleted = False
                    role_perm.updated_by = created_by
                    role_perm.save()
                    
            except Permission.DoesNotExist:
                # Skip invalid permission IDs
                pass


class UserRoleSerializer(serializers.ModelSerializer):
    """Serializer for user role assignments"""
    role_name = serializers.CharField(source='role.name', read_only=True)
    role_description = serializers.CharField(source='role.description', read_only=True)
    
    class Meta:
        model = UserRole
        fields = ['id', 'user', 'role', 'role_name', 'role_description', 
                 'is_active', 'created_at']
        read_only_fields = ['id', 'created_at', 'role_name', 'role_description']
