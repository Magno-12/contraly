from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from django.utils import timezone

from apps.payments.models import (
    Payment, PaymentStatus, Withholding, PaymentSchedule
)
from apps.invoices.models import Invoice, InvoiceStatus


@receiver(post_save, sender=Payment)
def payment_post_save(sender, instance, created, **kwargs):
    """
    Acciones a realizar después de guardar un pago
    """
    # Si es un pago nuevo, crear el estado inicial si no existe
    if created and not PaymentStatus.objects.filter(payment=instance).exists():
        PaymentStatus.objects.create(
            payment=instance,
            status='PENDING',
            changed_by=instance.created_by,
            created_by=instance.created_by,
            updated_by=instance.created_by,
            tenant=instance.tenant
        )
    
    # Actualizar programaciones de pago asociadas
    for schedule in instance.schedules.filter(is_active=True, is_deleted=False):
        # Actualizar monto pagado
        total_paid = Payment.objects.filter(
            schedules=schedule,
            is_active=True,
            is_deleted=False
        ).aggregate(models.Sum('amount'))['amount__sum'] or 0
        
        schedule.paid_amount = total_paid
        
        # Actualizar estado
        schedule.update_status()


@receiver(post_save, sender=PaymentStatus)
def payment_status_post_save(sender, instance, created, **kwargs):
    """
    Acciones a realizar después de guardar un estado de pago
    """
    if not created:
        return  # Solo para nuevos estados
    
    # Si el estado es VERIFIED, actualizar la factura si es necesario
    if instance.status == 'VERIFIED':
        payment = instance.payment
        payment._update_invoice_status()


@receiver(post_delete, sender=Payment)
def payment_post_delete(sender, instance, **kwargs):
    """
    Acciones a realizar después de eliminar un pago
    """
    # Actualizar programaciones asociadas
    for schedule in instance.schedules.filter(is_active=True, is_deleted=False):
        # Recalcular monto pagado
        total_paid = Payment.objects.filter(
            schedules=schedule,
            is_active=True,
            is_deleted=False
        ).aggregate(models.Sum('amount'))['amount__sum'] or 0
        
        schedule.paid_amount = total_paid or 0
        
        # Actualizar estado
        schedule.update_status()
    
    # Verificar si la factura necesita actualizar su estado
    invoice = instance.invoice
    
    if invoice and invoice.is_paid:
        # Verificar si hay suficientes pagos para mantener como pagada
        total_paid = Payment.objects.filter(
            invoice=invoice,
            is_active=True,
            is_deleted=False
        ).aggregate(models.Sum('amount'))['amount__sum'] or 0
        
        if total_paid < invoice.total_amount:
            # Cambiar estado de factura a aprobada (si estaba pagada)
            current_status = invoice.current_status
            if current_status and current_status.status == 'PAID':
                invoice.is_paid = False
                invoice.payment_date = None
                invoice.save(update_fields=['is_paid', 'payment_date', 'updated_at'])
                
                # Crear nuevo estado
                InvoiceStatus.objects.create(
                    invoice=invoice,
                    status='APPROVED',
                    comments="Estado restablecido por eliminación de pago",
                    changed_by=instance.updated_by,
                    created_by=instance.updated_by,
                    updated_by=instance.updated_by,
                    tenant=instance.tenant
                )


@receiver(post_save, sender=PaymentSchedule)
def schedule_post_save(sender, instance, created, **kwargs):
    """
    Acciones a realizar después de guardar una programación de pago
    """
    if created:
        # Actualizar estado al crear
        instance.update_status()
    
    # Verificar si todas las programaciones de la factura están pagadas
    invoice = instance.invoice
    
    if invoice and not invoice.is_paid:
        pending_schedules = PaymentSchedule.objects.filter(
            invoice=invoice,
            is_active=True,
            is_deleted=False
        ).exclude(
            status='PAID'
        ).exists()
        
        if not pending_schedules:
            # Si todas están pagadas, actualizar estado de la factura
            invoice.is_paid = True
            invoice.payment_date = timezone.now().date()
            invoice.save(update_fields=['is_paid', 'payment_date', 'updated_at'])
            
            # Crear estado PAID para la factura
            current_status = invoice.current_status
            if current_status and current_status.status != 'PAID':
                InvoiceStatus.objects.create(
                    invoice=invoice,
                    status='PAID',
                    comments="Todas las cuotas programadas han sido pagadas",
                    changed_by=instance.updated_by or instance.created_by,
                    created_by=instance.created_by,
                    updated_by=instance.updated_by or instance.created_by,
                    tenant=instance.tenant
                )
