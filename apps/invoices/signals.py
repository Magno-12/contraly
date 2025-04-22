from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from django.utils import timezone

from apps.invoices.models import (
    Invoice, InvoiceItem, InvoiceStatus, InvoiceApproval, InvoiceSchedule
)
from apps.core.utils import create_audit_log


@receiver(post_save, sender=Invoice)
def invoice_post_save(sender, instance, created, **kwargs):
    """
    Acciones a realizar después de guardar una cuenta de cobro
    """
    # Si es una cuenta nueva, crear el estado inicial si no existe
    if created and not instance.statuses.exists():
        InvoiceStatus.objects.create(
            invoice=instance,
            status='DRAFT',
            changed_by=instance.created_by,
            created_by=instance.created_by,
            updated_by=instance.created_by,
            tenant=instance.tenant
        )


@receiver(post_save, sender=InvoiceStatus)
def status_post_save(sender, instance, created, **kwargs):
    """
    Acciones a realizar después de guardar un estado de cuenta de cobro
    """
    if not created:
        return  # Solo para nuevos estados
    
    # Si el estado es PAID, actualizar la factura
    if instance.status == 'PAID':
        invoice = instance.invoice
        if not invoice.is_paid:
            invoice.is_paid = True
            invoice.payment_date = timezone.now().date()
            invoice.save(update_fields=['is_paid', 'payment_date', 'updated_at'])


@receiver(post_save, sender=InvoiceApproval)
def approval_post_save(sender, instance, created, **kwargs):
    """
    Acciones a realizar después de guardar una aprobación
    """
    if not created and instance.result == 'PENDING':
        return  # Solo para aprobaciones nuevas o cambiadas de estado
    
    # Si todas las aprobaciones están completadas, actualizar el estado de la factura
    invoice = instance.invoice
    
    # Solo si la aprobación fue aprobada o rechazada
    if instance.result in ['APPROVED', 'REJECTED']:
        # Verificar si hay más aprobaciones pendientes
        pending_approvals = InvoiceApproval.objects.filter(
            invoice=invoice,
            result='PENDING',
            is_active=True,
            is_deleted=False
        ).exists()
        
        if not pending_approvals:
            # Si no hay pendientes, verificar si alguna fue rechazada
            rejected = InvoiceApproval.objects.filter(
                invoice=invoice,
                result='REJECTED',
                is_active=True,
                is_deleted=False
            ).exists()
            
            current_status = invoice.current_status
            
            if rejected and current_status and current_status.status != 'REJECTED':
                # Si hay rechazos, cambiar a REJECTED
                InvoiceStatus.objects.create(
                    invoice=invoice,
                    status='REJECTED',
                    comments='Rechazo automático por aprobación rechazada',
                    changed_by=instance.updated_by or instance.created_by,
                    created_by=instance.created_by,
                    updated_by=instance.updated_by or instance.created_by,
                    tenant=invoice.tenant
                )
            elif not rejected and current_status:
                # Si no hay rechazos, cambiar al siguiente estado según el tipo de aprobación
                if instance.approval_type == 'FINAL_APPROVAL' and current_status.status == 'PENDING_APPROVAL':
                    InvoiceStatus.objects.create(
                        invoice=invoice,
                        status='APPROVED',
                        comments='Aprobación automática por completar todas las aprobaciones',
                        changed_by=instance.updated_by or instance.created_by,
                        created_by=instance.created_by,
                        updated_by=instance.updated_by or instance.created_by,
                        tenant=invoice.tenant
                    )
                elif instance.approval_type == 'FIRST_APPROVAL' and current_status.status == 'REVIEW':
                    InvoiceStatus.objects.create(
                        invoice=invoice,
                        status='PENDING_APPROVAL',
                        comments='Cambio automático a pendiente de aprobación final',
                        changed_by=instance.updated_by or instance.created_by,
                        created_by=instance.created_by,
                        updated_by=instance.updated_by or instance.created_by,
                        tenant=invoice.tenant
                    )


@receiver(post_save, sender=InvoiceItem)
def item_post_save(sender, instance, created, **kwargs):
    """
    Acciones a realizar después de guardar un ítem de cuenta de cobro
    """
    # Actualizar totales de la factura
    invoice = instance.invoice
    
    # Calcular subtotal, impuestos y descuentos de todos los ítems activos
    items = InvoiceItem.objects.filter(
        invoice=invoice,
        is_active=True,
        is_deleted=False
    )
    
    subtotal = sum(item.subtotal for item in items)
    tax_amount = sum(item.tax_amount for item in items)
    discount_amount = sum(item.discount_amount for item in items)
    total_amount = subtotal + tax_amount - discount_amount
    
    # Actualizar factura
    invoice.subtotal = subtotal
    invoice.tax_amount = tax_amount
    invoice.discount_amount = discount_amount
    invoice.total_amount = total_amount
    invoice.save(update_fields=['subtotal', 'tax_amount', 'discount_amount', 'total_amount', 'updated_at'])


@receiver(post_delete, sender=InvoiceItem)
def item_post_delete(sender, instance, **kwargs):
    """
    Acciones a realizar después de eliminar un ítem de cuenta de cobro
    """
    # Actualizar totales de la factura
    try:
        invoice = instance.invoice
        
        # Calcular subtotal, impuestos y descuentos de todos los ítems activos
        items = InvoiceItem.objects.filter(
            invoice=invoice,
            is_active=True,
            is_deleted=False
        )
        
        subtotal = sum(item.subtotal for item in items)
        tax_amount = sum(item.tax_amount for item in items)
        discount_amount = sum(item.discount_amount for item in items)
        total_amount = subtotal + tax_amount - discount_amount
        
        # Actualizar factura
        invoice.subtotal = subtotal
        invoice.tax_amount = tax_amount
        invoice.discount_amount = discount_amount
        invoice.total_amount = total_amount
        invoice.save(update_fields=['subtotal', 'tax_amount', 'discount_amount', 'total_amount', 'updated_at'])
    except Invoice.DoesNotExist:
        # La factura ya fue eliminada
        pass
