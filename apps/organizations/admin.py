from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse

from apps.organizations.models import (
    Organization, Domain, OrganizationMember, 
    OrganizationSettings, OrganizationInvitation
)


class DomainInline(admin.TabularInline):
    model = Domain
    extra = 1
    fields = ('domain', 'is_primary', 'is_active')


class OrganizationMemberInline(admin.TabularInline):
    model = OrganizationMember
    extra = 1
    fields = ('user', 'role', 'position', 'department', 'is_active')
    autocomplete_fields = ['user']


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ('name', 'subdomain', 'organization_type', 'city', 'state', 
                   'on_trial', 'paid_until', 'is_active', 'created_at')
    list_filter = ('organization_type', 'on_trial', 'is_active', 'city', 'state')
    search_fields = ('name', 'subdomain', 'email', 'tax_id')
    readonly_fields = ('schema_name', 'created_at', 'updated_at', 'created_by', 'updated_by')
    inlines = [DomainInline, OrganizationMemberInline]
    
    fieldsets = (
        ('Información básica', {
            'fields': ('name', 'subdomain', 'description', 'organization_type', 'logo')
        }),
        ('Información de contacto', {
            'fields': ('email', 'phone', 'address', 'city', 'state', 'country', 'zip_code', 'tax_id')
        }),
        ('Personalización', {
            'fields': ('primary_color', 'secondary_color')
        }),
        ('Configuración', {
            'fields': ('max_users', 'max_storage_gb')
        }),
        ('Facturación', {
            'fields': ('on_trial', 'trial_ends', 'paid_until')
        }),
        ('Información técnica', {
            'classes': ('collapse',),
            'fields': ('schema_name', 'is_active', 'created_at', 'updated_at', 'created_by', 'updated_by'),
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if not change:  # Si es una creación, no una actualización
            obj.created_by = request.user
            # Asegurarse de que schema_name se establezca correctamente
            if not obj.schema_name:
                obj.schema_name = obj.subdomain
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)
    
    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for instance in instances:
            if isinstance(instance, Domain) or isinstance(instance, OrganizationMember):
                if not instance.pk:  # Si es nuevo
                    instance.created_by = request.user
                instance.updated_by = request.user
            instance.save()
        formset.save_m2m()


@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
    list_display = ('domain', 'tenant_link', 'is_primary', 'is_active')
    list_filter = ('is_primary', 'is_active')
    search_fields = ('domain', 'tenant__name')
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by')
    
    def tenant_link(self, obj):
        url = reverse('admin:organizations_organization_change', args=[obj.tenant.id])
        return format_html('<a href="{}">{}</a>', url, obj.tenant.name)
    tenant_link.short_description = 'Organización'
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(OrganizationMember)
class OrganizationMemberAdmin(admin.ModelAdmin):
    list_display = ('user_email', 'user_name', 'organization_link', 'role', 
                   'position', 'department', 'is_active')
    list_filter = ('role', 'is_active', 'organization')
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 
                    'organization__name', 'position', 'department')
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by')
    autocomplete_fields = ['user', 'organization']
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'Email'
    
    def user_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}"
    user_name.short_description = 'Nombre'
    
    def organization_link(self, obj):
        url = reverse('admin:organizations_organization_change', args=[obj.organization.id])
        return format_html('<a href="{}">{}</a>', url, obj.organization.name)
    organization_link.short_description = 'Organización'
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(OrganizationSettings)
class OrganizationSettingsAdmin(admin.ModelAdmin):
    list_display = ('organization_link', 'email_notifications', 'require_double_approval',
                   'force_password_change', 'default_currency')
    list_filter = ('email_notifications', 'require_double_approval', 
                  'force_password_change', 'allow_self_approval')
    search_fields = ('organization__name',)
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by')
    
    fieldsets = (
        ('Organización', {
            'fields': ('organization',)
        }),
        ('Configuración de workflow', {
            'fields': ('require_double_approval', 'allow_self_approval')
        }),
        ('Notificaciones', {
            'fields': ('email_notifications', 'sms_notifications')
        }),
        ('Seguridad', {
            'fields': ('force_password_change', 'password_expiry_days', 'session_timeout_minutes')
        }),
        ('Configuración fiscal', {
            'fields': ('fiscal_year_start', 'default_currency')
        }),
        ('Metadata', {
            'classes': ('collapse',),
            'fields': ('created_at', 'updated_at', 'created_by', 'updated_by'),
        }),
    )
    
    def organization_link(self, obj):
        url = reverse('admin:organizations_organization_change', args=[obj.organization.id])
        return format_html('<a href="{}">{}</a>', url, obj.organization.name)
    organization_link.short_description = 'Organización'
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(OrganizationInvitation)
class OrganizationInvitationAdmin(admin.ModelAdmin):
    list_display = ('email', 'organization_link', 'role', 'status', 
                   'expires_at', 'created_at')
    list_filter = ('status', 'role', 'organization')
    search_fields = ('email', 'organization__name')
    readonly_fields = ('token', 'created_at', 'updated_at', 'created_by', 'updated_by')
    
    def organization_link(self, obj):
        url = reverse('admin:organizations_organization_change', args=[obj.organization.id])
        return format_html('<a href="{}">{}</a>', url, obj.organization.name)
    organization_link.short_description = 'Organización'
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
            # Generar token si es nuevo
            import secrets
            import datetime
            from django.utils import timezone
            
            obj.token = secrets.token_urlsafe(32)
            # Establecer expiración a 7 días si no se especifica
            if not obj.expires_at:
                obj.expires_at = timezone.now() + datetime.timedelta(days=7)
                
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)
