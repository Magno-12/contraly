from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse

from apps.payments.models import (
    Payment, PaymentMethod, PaymentSchedule, PaymentStatus, Withholding
)


class WithholdingInline(admin.TabularInline):
    model = Withholding
    extra = 1
    fields = ('name', 'code', 'percentage', 'amount', 'withholding_type')


class PaymentStatusInline(admin.TabularInline):
    model = PaymentStatus
    extra = 0
    fields = ('status', 'change_date', 'comments', 'changed_by', 'is_active')
    readonly_fields = ('change_date',)
    
    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('invoice_link', 'amount', 'payment_date', 'payment_method_display', 
                   'is_partial', 'status_display', 'is_active')
    list_filter = ('is_partial', 'payment_date', 'payment_method', 'tenant')
    search_fields = ('reference', 'notes', 'invoice__invoice_number', 'transaction_id')
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by')
    inlines = [WithholdingInline, PaymentStatusInline]
    
    fieldsets = (
        ('Información básica', {
            'fields': ('invoice', 'amount', 'payment_date', 'reference', 'payment_method')
        }),
        ('Detalles del pago', {
            'fields': ('is_partial', 'bank_name', 'account_number', 'transaction_id', 'receipt')
        }),
        ('Notas', {
            'fields': ('notes',)
        }),
        ('Multi-tenant', {
            'fields': ('tenant',)
        }),
        ('Metadatos', {
            'classes': ('collapse',),
            'fields': ('is_active', 'is_deleted', 'created_at', 'updated_at', 'created_by', 'updated_by')
        }),
    )
    
    def invoice_link(self, obj):
        url = reverse('admin:invoices_invoice_change', args=[obj.invoice.id])
        return format_html('<a href="{}">{}</a>', url, obj.invoice.invoice_number)
    invoice_link.short_description = 'Cuenta de cobro'
    
    def payment_method_display(self, obj):
        if obj.payment_method:
            return obj.payment_method.name
        return "-"
    payment_method_display.short_description = 'Método de pago'
    
    def status_display(self, obj):
        status = PaymentStatus.objects.filter(
            payment=obj,
            is_active=True,
            is_deleted=False
        ).order_by('-change_date').first()
        
        if status:
            status_map = {
                'PENDING': 'Pendiente',
                'VERIFIED': 'Verificado',
                'REJECTED': 'Rechazado',
                'REFUNDED': 'Reembolsado',
                'CANCELLED': 'Cancelado'
            }
            status_colors = {
                'PENDING': 'orange',
                'VERIFIED': 'green',
                'REJECTED': 'red',
                'REFUNDED': 'purple',
                'CANCELLED': 'gray'
            }
            
            color = status_colors.get(status.status, 'black')
            return format_html(
                '<span style="color: {};">{}</span>',
                color,
                status_map.get(status.status, status.status)
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


@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'payment_type_display', 'requires_reference', 
                   'requires_receipt', 'requires_bank_info', 'is_active')
    list_filter = ('payment_type', 'requires_reference', 'requires_receipt', 
                  'requires_bank_info', 'allow_partial', 'tenant')
    search_fields = ('name', 'code', 'description')
    
    fieldsets = (
        ('Información básica', {
            'fields': ('name', 'code', 'description', 'payment_type')
        }),
        ('Configuración de validación', {
            'fields': ('requires_reference', 'requires_receipt', 'requires_bank_info', 
                      'allow_partial')
        }),
        ('Multi-tenant', {
            'fields': ('tenant',)
        }),
        ('Metadatos', {
            'classes': ('collapse',),
            'fields': ('is_active', 'is_deleted', 'created_at', 'updated_at', 'created_by', 'updated_by')
        }),
    )
    
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by')
    
    def payment_type_display(self, obj):
        return obj.get_payment_type_display()
    payment_type_display.short_description = 'Tipo de pago'
    
    def save_model(self, request, obj, form, change):
        if not change:  # Si es una creación nueva
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(PaymentSchedule)
class PaymentScheduleAdmin(admin.ModelAdmin):
    list_display = ('invoice_link', 'due_date', 'amount', 'paid_amount', 'status_display', 
                   'installment_number', 'total_installments', 'is_active')
    list_filter = ('status', 'due_date', 'tenant')
    search_fields = ('invoice__invoice_number', 'notes')
    readonly_fields = ('paid_amount', 'payment_date', 'created_at', 'updated_at', 'created_by', 'updated_by')
    
    fieldsets = (
        ('Información básica', {
            'fields': ('invoice', 'due_date', 'amount', 'paid_amount', 'payment_date')
        }),
        ('Configuración de cuotas', {
            'fields': ('installment_number', 'total_installments', 'status')
        }),
        ('Notas', {
            'fields': ('notes',)
        }),
        ('Multi-tenant', {
            'fields': ('tenant',)
        }),
        ('Metadatos', {
            'classes': ('collapse',),
            'fields': ('is_active', 'is_deleted', 'created_at', 'updated_at', 'created_by', 'updated_by')
        }),
    )
    
    def invoice_link(self, obj):
        url = reverse('admin:invoices_invoice_change', args=[obj.invoice.id])
        return format_html('<a href="{}">{}</a>', url, obj.invoice.invoice_number)
    invoice_link.short_description = 'Cuenta de cobro'
    
    def status_display(self, obj):
        status_map = {
            'PENDING': 'Pendiente',
            'PARTIALLY_PAID': 'Parcialmente pagada',
            'PAID': 'Pagada',
            'OVERDUE': 'Vencida',
            'CANCELLED': 'Cancelada'
        }
        
        status_colors = {
            'PENDING': 'blue',
            'PARTIALLY_PAID': 'orange',
            'PAID': 'green',
            'OVERDUE': 'red',
            'CANCELLED': 'gray'
        }
        
        color = status_colors.get(obj.status, 'black')
        return format_html(
            '<span style="color: {};">{}</span>',
            color,
            status_map.get(obj.status, obj.status)
        )
    status_display.short_description = 'Estado'
    
    def save_model(self, request, obj, form, change):
        if not change:  # Si es una creación nueva
            obj.created_by = request.user
        obj.updated_by = request.user
        
        # Actualizar estado al guardar
        super().save_model(request, obj, form, change)
        obj.update_status()


@admin.register(PaymentStatus)
class PaymentStatusAdmin(admin.ModelAdmin):
    list_display = ('payment_link', 'status_display', 'change_date', 'changed_by', 'is_active')
    list_filter = ('status', 'is_active', 'tenant')
    search_fields = ('payment__invoice__invoice_number', 'comments')
    readonly_fields = ('change_date', 'created_at', 'updated_at', 'created_by', 'updated_by')
    
    fieldsets = (
        ('Información básica', {
            'fields': ('payment', 'status', 'change_date', 'comments')
        }),
        ('Responsables', {
            'fields': ('changed_by',)
        }),
        ('Multi-tenant', {
            'fields': ('tenant',)
        }),
        ('Metadatos', {
            'classes': ('collapse',),
            'fields': ('is_active', 'is_deleted', 'created_at', 'updated_at', 'created_by', 'updated_by')
        }),
    )
    
    def payment_link(self, obj):
        url = reverse('admin:payments_payment_change', args=[obj.payment.id])
        return format_html('<a href="{}">{}</a>', url, obj.payment.id)
    payment_link.short_description = 'Pago'
    
    def status_display(self, obj):
        return obj.get_status_display()
    status_display.short_description = 'Estado'
    
    def save_model(self, request, obj, form, change):
        if not change:  # Si es una creación nueva
            obj.created_by = request.user
            obj.changed_by = request.user  # Asignar el usuario que cambia el estado
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Withholding)
class WithholdingAdmin(admin.ModelAdmin):
    list_display = ('payment_link', 'name', 'code', 'percentage', 'amount', 
                   'withholding_type_display', 'is_active')
    list_filter = ('withholding_type', 'is_active', 'tenant')
    search_fields = ('name', 'code', 'description')
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by')
    
    fieldsets = (
        ('Información básica', {
            'fields': ('payment', 'name', 'code', 'percentage', 'amount')
        }),
        ('Configuración', {
            'fields': ('withholding_type', 'description', 'certificate')
        }),
        ('Multi-tenant', {
            'fields': ('tenant',)
        }),
        ('Metadatos', {
            'classes': ('collapse',),
            'fields': ('is_active', 'is_deleted', 'created_at', 'updated_at', 'created_by', 'updated_by')
        }),
    )
    
    def payment_link(self, obj):
        url = reverse('admin:payments_payment_change', args=[obj.payment.id])
        return format_html('<a href="{}">{}</a>', url, obj.payment.id)
    payment_link.short_description = 'Pago'
    
    def withholding_type_display(self, obj):
        return obj.get_withholding_type_display()
    withholding_type_display.short_description = 'Tipo de retención'
    
    def save_model(self, request, obj, form, change):
        if not change:  # Si es una creación nueva
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)
