from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse

from apps.invoices.models import (
    Invoice, InvoiceItem, InvoiceStatus, InvoiceApproval, InvoiceSchedule
)


class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 1
    fields = ('description', 'quantity', 'unit_price', 'tax_percentage', 
              'discount_percentage', 'subtotal', 'total', 'is_active')
    readonly_fields = ('subtotal', 'total')


class InvoiceStatusInline(admin.TabularInline):
    model = InvoiceStatus
    extra = 0
    fields = ('status', 'start_date', 'end_date', 'comments', 'changed_by', 'is_active')
    readonly_fields = ('start_date', 'end_date')
    
    def has_add_permission(self, request, obj=None):
        return False


class InvoiceApprovalInline(admin.TabularInline):
    model = InvoiceApproval
    extra = 0
    fields = ('approval_type', 'approver', 'result', 'assigned_date', 
              'approval_date', 'comments', 'is_active')
    readonly_fields = ('assigned_date', 'approval_date')


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('invoice_number', 'title', 'issuer', 'recipient_display', 
                   'issue_date', 'due_date', 'total_amount', 'currency', 
                   'is_paid', 'status_display', 'is_active')
    list_filter = ('is_paid', 'is_active', 'issue_date', 'due_date', 'tenant')
    search_fields = ('invoice_number', 'title', 'reference', 'notes')
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by')
    inlines = [InvoiceItemInline, InvoiceStatusInline, InvoiceApprovalInline]
    
    fieldsets = (
        ('Información básica', {
            'fields': ('invoice_number', 'title', 'contract', 'reference')
        }),
        ('Emisor y receptor', {
            'fields': ('issuer', 'recipient_type', 'recipient_organization', 
                      'recipient_user', 'recipient_name', 'recipient_identification')
        }),
        ('Fechas', {
            'fields': ('issue_date', 'due_date', 'period_start', 'period_end',
                      'payment_date')
        }),
        ('Importes', {
            'fields': ('subtotal', 'tax_amount', 'discount_amount', 'total_amount',
                      'currency', 'is_paid')
        }),
        ('Información adicional', {
            'fields': ('notes', 'payment_terms', 'payment_method', 'document')
        }),
        ('Multi-tenant', {
            'fields': ('tenant',)
        }),
        ('Metadatos', {
            'classes': ('collapse',),
            'fields': ('is_active', 'is_deleted', 'created_at', 'updated_at', 
                      'created_by', 'updated_by')
        }),
    )
    
    def recipient_display(self, obj):
        if obj.recipient_type == 'ORGANIZATION' and obj.recipient_organization:
            return obj.recipient_organization.name
        elif obj.recipient_type == 'USER' and obj.recipient_user:
            return f"{obj.recipient_user.first_name} {obj.recipient_user.last_name}"
        else:
            return obj.recipient_name
    recipient_display.short_description = 'Receptor'
    
    def status_display(self, obj):
        current_status = obj.current_status
        if current_status:
            status_map = {
                'DRAFT': 'Borrador',
                'SUBMITTED': 'Enviada',
                'REVIEW': 'En revisión',
                'PENDING_APPROVAL': 'Pendiente de aprobación',
                'APPROVED': 'Aprobada',
                'REJECTED': 'Rechazada',
                'PAID': 'Pagada',
                'CANCELLED': 'Cancelada',
                'ARCHIVED': 'Archivada'
            }
            status_colors = {
                'DRAFT': 'gray',
                'SUBMITTED': 'blue',
                'REVIEW': 'orange',
                'PENDING_APPROVAL': 'purple',
                'APPROVED': 'green',
                'REJECTED': 'red',
                'PAID': 'green',
                'CANCELLED': 'red',
                'ARCHIVED': 'gray'
            }
            color = status_colors.get(current_status.status, 'black')
            return format_html(
                '<span style="color: {};">{}</span>',
                color,
                status_map.get(current_status.status, current_status.status)
            )
        return "Sin estado"
    status_display.short_description = 'Estado'
    
    def save_model(self, request, obj, form, change):
        if not change:  # Si es una creación nueva
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)
    
    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for instance in instances:
            if not instance.pk:  # Si es nuevo
                instance.created_by = request.user
            instance.updated_by = request.user
            instance.save()
        formset.save_m2m()


@admin.register(InvoiceItem)
class InvoiceItemAdmin(admin.ModelAdmin):
    list_display = ('invoice_link', 'description', 'quantity', 'unit_price', 
                   'subtotal', 'tax_amount', 'discount_amount', 'total', 'order')
    list_filter = ('invoice__is_paid', 'is_active', 'tenant')
    search_fields = ('description', 'contract_item')
    readonly_fields = ('subtotal', 'total', 'created_at', 'updated_at', 'created_by', 'updated_by')
    
    fieldsets = (
        ('Información básica', {
            'fields': ('invoice', 'description', 'contract_item', 'order')
        }),
        ('Cantidades', {
            'fields': ('quantity', 'unit_price', 'subtotal')
        }),
        ('Impuestos y descuentos', {
            'fields': ('tax_percentage', 'tax_amount', 'discount_percentage', 
                      'discount_amount', 'total')
        }),
        ('Notas', {
            'fields': ('notes',)
        }),
        ('Multi-tenant', {
            'fields': ('tenant',)
        }),
        ('Metadatos', {
            'classes': ('collapse',),
            'fields': ('is_active', 'is_deleted', 'created_at', 'updated_at', 
                      'created_by', 'updated_by')
        }),
    )
    
    def invoice_link(self, obj):
        url = reverse('admin:invoices_invoice_change', args=[obj.invoice.id])
        return format_html('<a href="{}">{}</a>', url, obj.invoice.invoice_number)
    invoice_link.short_description = 'Cuenta de cobro'
    
    def save_model(self, request, obj, form, change):
        if not change:  # Si es una creación nueva
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(InvoiceStatus)
class InvoiceStatusAdmin(admin.ModelAdmin):
    list_display = ('invoice_link', 'status', 'start_date', 'end_date', 
                   'changed_by', 'is_active')
    list_filter = ('status', 'is_active', 'tenant')
    search_fields = ('invoice__invoice_number', 'comments')
    readonly_fields = ('start_date', 'end_date', 'created_at', 'updated_at', 
                      'created_by', 'updated_by')
    
    fieldsets = (
        ('Información básica', {
            'fields': ('invoice', 'status', 'comments')
        }),
        ('Fechas', {
            'fields': ('start_date', 'end_date')
        }),
        ('Responsables', {
            'fields': ('changed_by',)
        }),
        ('Multi-tenant', {
            'fields': ('tenant',)
        }),
        ('Metadatos', {
            'classes': ('collapse',),
            'fields': ('is_active', 'is_deleted', 'created_at', 'updated_at', 
                      'created_by', 'updated_by')
        }),
    )
    
    def invoice_link(self, obj):
        url = reverse('admin:invoices_invoice_change', args=[obj.invoice.id])
        return format_html('<a href="{}">{}</a>', url, obj.invoice.invoice_number)
    invoice_link.short_description = 'Cuenta de cobro'
    
    def save_model(self, request, obj, form, change):
        if not change:  # Si es una creación nueva
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(InvoiceApproval)
class InvoiceApprovalAdmin(admin.ModelAdmin):
    list_display = ('invoice_link', 'approval_type', 'approver', 'result', 
                   'assigned_date', 'approval_date', 'is_active')
    list_filter = ('approval_type', 'result', 'is_active', 'tenant')
    search_fields = ('invoice__invoice_number', 'approver__email', 'comments')
    readonly_fields = ('assigned_date', 'created_at', 'updated_at', 'created_by', 'updated_by')
    
    fieldsets = (
        ('Información básica', {
            'fields': ('invoice', 'approval_type', 'approver')
        }),
        ('Resultado', {
            'fields': ('result', 'comments')
        }),
        ('Fechas', {
            'fields': ('assigned_date', 'due_date', 'approval_date')
        }),
        ('Multi-tenant', {
            'fields': ('tenant',)
        }),
        ('Metadatos', {
            'classes': ('collapse',),
            'fields': ('is_active', 'is_deleted', 'created_at', 'updated_at', 
                      'created_by', 'updated_by')
        }),
    )
    
    def invoice_link(self, obj):
        url = reverse('admin:invoices_invoice_change', args=[obj.invoice.id])
        return format_html('<a href="{}">{}</a>', url, obj.invoice.invoice_number)
    invoice_link.short_description = 'Cuenta de cobro'
    
    def save_model(self, request, obj, form, change):
        if not change:  # Si es una creación nueva
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(InvoiceSchedule)
class InvoiceScheduleAdmin(admin.ModelAdmin):
    list_display = ('name', 'contract_link', 'schedule_type', 'start_date', 
                   'next_generation', 'is_auto_generate', 'is_active')
    list_filter = ('schedule_type', 'is_auto_generate', 'is_active', 'tenant')
    search_fields = ('name', 'description', 'contract__contract_number')
    readonly_fields = ('last_generated', 'next_generation', 'created_at', 'updated_at', 
                      'created_by', 'updated_by')
    
    fieldsets = (
        ('Información básica', {
            'fields': ('name', 'description', 'contract')
        }),
        ('Programación', {
            'fields': ('schedule_type', 'start_date', 'end_date', 'custom_days', 'day_of_month')
        }),
        ('Generación', {
            'fields': ('is_auto_generate', 'auto_approve', 'value', 'last_generated', 'next_generation')
        }),
        ('Multi-tenant', {
            'fields': ('tenant',)
        }),
        ('Metadatos', {
            'classes': ('collapse',),
            'fields': ('is_active', 'is_deleted', 'created_at', 'updated_at', 
                      'created_by', 'updated_by')
        }),
    )
    
    def contract_link(self, obj):
        url = reverse('admin:contracts_contract_change', args=[obj.contract.id])
        return format_html('<a href="{}">{}</a>', url, obj.contract.contract_number)
    contract_link.short_description = 'Contrato'
    
    def save_model(self, request, obj, form, change):
        if not change:  # Si es una creación nueva
            obj.created_by = request.user
        obj.updated_by = request.user
        
        # Al guardar, recalcular la próxima fecha de generación si es necesario
        if obj.is_active and not obj.next_generation:
            obj.next_generation = obj.calculate_next_generation()
            
        super().save_model(request, obj, form, change)
