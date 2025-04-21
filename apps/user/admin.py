from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _

from apps.user.models import (
    User, UserProfile, Role, UserRole, Permission, RolePermission,
    LoginAttempt, UserActivity, UserSession
)


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    fk_name = 'user'
    can_delete = False
    verbose_name_plural = 'profile'


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('email', 'first_name', 'last_name', 'is_staff', 'tenant', 'is_active')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'tenant', 'is_deleted')
    search_fields = ('email', 'first_name', 'last_name', 'phone_number')
    ordering = ('email',)
    inlines = (UserProfileInline,)
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        (_('Personal info'), {'fields': ('first_name', 'last_name', 'phone_number', 'avatar',
                                         'document_type', 'document_number')}),
        (_('Tenant info'), {'fields': ('tenant',)}),
        (_('Permissions'), {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'is_deleted', 'must_change_password',
                       'groups', 'user_permissions'),
        }),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
        (_('Security'), {'fields': ('last_login_ip', 'failed_login_attempts')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'first_name', 'last_name', 'password1', 'password2', 'tenant'),
        }),
    )


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'tenant', 'is_system_role', 'is_active')
    list_filter = ('tenant', 'is_system_role', 'is_active', 'is_deleted')
    search_fields = ('name', 'description')
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'is_active')
    list_filter = ('role', 'is_active', 'is_deleted')
    search_fields = ('user__email', 'role__name')
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'permission_type', 'module', 'is_active')
    list_filter = ('permission_type', 'module', 'is_active', 'is_deleted')
    search_fields = ('name', 'code', 'description')
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(RolePermission)
class RolePermissionAdmin(admin.ModelAdmin):
    list_display = ('role', 'permission', 'is_active')
    list_filter = ('is_active', 'is_deleted')
    search_fields = ('role__name', 'permission__name')
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(LoginAttempt)
class LoginAttemptAdmin(admin.ModelAdmin):
    list_display = ('email', 'ip_address', 'successful', 'created_at', 'tenant')
    list_filter = ('successful', 'created_at', 'tenant')
    search_fields = ('email', 'ip_address')
    readonly_fields = ('email', 'ip_address', 'user_agent', 'successful', 'created_at', 'tenant')
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False


@admin.register(UserActivity)
class UserActivityAdmin(admin.ModelAdmin):
    list_display = ('user', 'activity_type', 'module', 'ip_address', 'created_at', 'tenant')
    list_filter = ('activity_type', 'module', 'created_at', 'tenant')
    search_fields = ('user__email', 'description', 'ip_address')
    readonly_fields = ('user', 'activity_type', 'description', 'ip_address', 'user_agent',
                      'module', 'page', 'created_at', 'tenant')
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False


@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    list_display = ('user', 'ip_address', 'browser', 'is_expired', 'created_at', 'expires_at', 'tenant')
    list_filter = ('is_expired', 'created_at', 'tenant')
    search_fields = ('user__email', 'ip_address', 'browser')
    readonly_fields = ('user', 'session_key', 'ip_address', 'user_agent', 'device_type',
                      'browser', 'os', 'expires_at', 'is_expired', 'logout_time',
                      'last_activity', 'created_at', 'tenant')
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
