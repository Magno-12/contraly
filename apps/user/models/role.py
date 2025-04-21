from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.default.models.base_model import BaseModel


class Role(BaseModel):
    """User roles with specific permissions"""
    
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    is_system_role = models.BooleanField(default=False)
    tenant = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='roles'
    )
    
    class Meta:
        verbose_name = _('role')
        verbose_name_plural = _('roles')
        
    def __str__(self):
        return self.name


class UserRole(BaseModel):
    """Many-to-many relationship between users and roles"""
    
    user = models.ForeignKey(
        'user.User', 
        on_delete=models.CASCADE,
        related_name='user_roles'
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name='role_users'
    )
    
    class Meta:
        verbose_name = _('user role')
        verbose_name_plural = _('user roles')
        unique_together = ('user', 'role')
        
    def __str__(self):
        return f"{self.user.email} - {self.role.name}"


class Permission(BaseModel):
    """Custom permissions for controlling access to different features"""
    
    PERMISSION_TYPES = (
        ('VIEW', 'View'),
        ('CREATE', 'Create'),
        ('EDIT', 'Edit'),
        ('DELETE', 'Delete'),
        ('APPROVE', 'Approve'),
        ('REJECT', 'Reject'),
        ('ADMIN', 'Administrator'),
    )
    
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    permission_type = models.CharField(max_length=20, choices=PERMISSION_TYPES)
    module = models.CharField(max_length=100, default='GENERAL')
    
    class Meta:
        verbose_name = _('permission')
        verbose_name_plural = _('permissions')
        ordering = ['module', 'permission_type', 'name']
        
    def __str__(self):
        return self.name


class RolePermission(BaseModel):
    """Many-to-many relationship between roles and permissions"""
    
    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name='role_permissions'
    )
    permission = models.ForeignKey(
        Permission,
        on_delete=models.CASCADE,
        related_name='permission_roles'
    )
    
    class Meta:
        verbose_name = _('role permission')
        verbose_name_plural = _('role permissions')
        unique_together = ('role', 'permission')
        
    def __str__(self):
        return f"{self.role.name} - {self.permission.name}"
