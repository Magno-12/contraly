from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.default.models.base_model import BaseModel


class InvoiceStatus(BaseModel):
    """
    Estados del proceso de aprobación de cuentas de cobro
    """
    STATUS_CHOICES = (
        ('DRAFT', _('Borrador')),
        ('SUBMITTED', _('Enviada')),
        ('REVIEW', _('En revisión')),
        ('PENDING_APPROVAL', _('Pendiente de aprobación')),
        ('APPROVED', _('Aprobada')),
        ('REJECTED', _('Rechazada')),
        ('PAID', _('Pagada')),
        ('CANCELLED', _('Cancelada')),
        ('ARCHIVED', _('Archivada')),
    )
    
    invoice = models.ForeignKey(
        'invoices.Invoice',
        on_delete=models.CASCADE,
        related_name='statuses',
        verbose_name=_("Cuenta de cobro")
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        verbose_name=_("Estado")
    )
    
    start_date = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Fecha de inicio")
    )
    
    end_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Fecha de finalización")
    )
    
    comments = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Comentarios")
    )
    
    changed_by = models.ForeignKey(
        'user.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invoice_status_changes',
        verbose_name=_("Cambiado por")
    )
    
    # Multi-tenancy
    tenant = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='invoice_statuses',
        verbose_name=_("Organización")
    )
    
    class Meta:
        verbose_name = _("Estado de cuenta de cobro")
        verbose_name_plural = _("Estados de cuenta de cobro")
        ordering = ['-start_date']
    
    def __str__(self):
        return f"{self.invoice.invoice_number} - {self.get_status_display()}"
    
    def save(self, *args, **kwargs):
        # Si es un nuevo estado, cerrar el estado anterior
        if not self.pk:  # Si es un nuevo registro
            previous_status = InvoiceStatus.objects.filter(
                invoice=self.invoice,
                end_date__isnull=True,
                is_active=True,
                is_deleted=False
            ).first()
            
            if previous_status:
                from django.utils import timezone
                previous_status.end_date = timezone.now()
                previous_status.save()
                
        super().save(*args, **kwargs)
        
        # Si el estado es PAID, actualizar la factura
        if self.status == 'PAID' and not self.invoice.is_paid:
            self.invoice.is_paid = True
            self.invoice.payment_date = self.start_date.date()
            self.invoice.save(update_fields=['is_paid', 'payment_date'])
