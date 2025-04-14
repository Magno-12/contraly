from django.contrib import admin

from apps.core.models import ConfigurationSetting, AuditLog, SystemLog


@admin.register(ConfigurationSetting)
class ConfigurationSettingAdmin(admin.ModelAdmin):
    list_display = ('key', 'value', 'category', 'is_editable', 'is_encrypted', 'is_active')
    list_filter = ('category', 'is_editable', 'is_encrypted', 'is_active')
    search_fields = ('key', 'value', 'description')
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by')
    fieldsets = (
        (None, {
            'fields': ('key', 'value', 'description')
        }),
        ('Settings', {
            'fields': ('category', 'is_editable', 'is_encrypted', 'is_active')
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_by', 'updated_at'),
            'classes': ('collapse',)
        })
    )

    def save_model(self, request, obj, form, change):
        if not change:  # If creating a new object
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('action', 'model_name', 'instance_id', 'created_by', 'created_at', 'tenant')
    list_filter = ('action', 'model_name', 'created_at')
    search_fields = ('model_name', 'instance_id', 'description', 'ip_address')
    readonly_fields = ('action', 'model_name', 'instance_id', 'description', 'ip_address', 
                      'user_agent', 'data', 'created_by', 'created_at', 'tenant')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(SystemLog)
class SystemLogAdmin(admin.ModelAdmin):
    list_display = ('level', 'source', 'message', 'created_at', 'tenant')
    list_filter = ('level', 'source', 'created_at')
    search_fields = ('source', 'message')
    readonly_fields = ('level', 'source', 'message', 'stack_trace', 'created_at', 'tenant')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
