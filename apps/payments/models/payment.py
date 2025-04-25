from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.default.models.base_model import BaseModel


class Payment(BaseModel):
    """
    Modelo para registrar pagos realizados para cuentas de cobro
    """
    invoice = models.ForeignKey(
        'invoices.Invoice',
        on_delete=models.PROTECT,
        related_name='payments',
        verbose_name=_("Cuenta de cobro")
    )
    
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name=_("Monto pagado")
    )
    
    payment_date = models.DateField(
        verbose_name=_("Fecha de pago")
    )
    
    reference = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_("Referencia de pago")
    )
    
    payment_method = models.ForeignKey(
        'payments.PaymentMethod',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payments',
        verbose_name=_("Método de pago")
    )
    
    status = models.ForeignKey(
        'payments.PaymentStatus',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payments',
        verbose_name=_("Estado de pago")
    )
    
    # Si es un pago parcial
    is_partial = models.BooleanField(
        default=False,
        verbose_name=_("Es pago parcial")
    )
    
    # Campos para bancarios
    bank_name = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_("Nombre del banco")
    )
    
    account_number = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name=_("Número de cuenta")
    )
    
    transaction_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_("ID de transacción")
    )
    
    # Documento comprobante
    receipt = models.FileField(
        upload_to='payment_receipts/',
        null=True,
        blank=True,
        verbose_name=_("Comprobante de pago")
    )
    
    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Notas")
    )
    
    # Multi-tenancy
    tenant = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='payments',
        verbose_name=_("Organización")
    )
    
    class Meta:
        verbose_name = _("Pago")
        verbose_name_plural = _("Pagos")
        ordering = ['-payment_date', '-created_at']
    
    def __str__(self):
        return f"{self.invoice.invoice_number} - {self.amount} - {self.payment_date}"
    
    def save(self, *args, **kwargs):
        # Verificar si este pago completa el total de la factura
        super().save(*args, **kwargs)
        
        # Actualizar estado de la factura si es necesario
        self._update_invoice_status()
    
    def _update_invoice_status(self):
        """
        Actualiza el estado de la factura según los pagos realizados
        """
        invoice = self.invoice
        
        # Calcular el total pagado (incluyendo este pago)
        total_paid = Payment.objects.filter(
            invoice=invoice,
            is_active=True,
            is_deleted=False
        ).aggregate(models.Sum('amount'))['amount__sum'] or 0
        
        # Verificar si se ha pagado el total
        if total_paid >= invoice.total_amount and not invoice.is_paid:
            # Actualizar estado de la factura a pagada
            from apps.invoices.models import InvoiceStatus
            from django.utils import timezone
            
            invoice.is_paid = True
            invoice.payment_date = timezone.now().date()
            invoice.save(update_fields=['is_paid', 'payment_date', 'updated_at', 'updated_by'])
            
            # Crear estado de pago si no existe
            current_status = invoice.current_status
            if not current_status or current_status.status != 'PAID':
                InvoiceStatus.objects.create(
                    invoice=invoice,
                    status='PAID',
                    comments=f"Pago completado: {self.reference or ''}",
                    changed_by=self.created_by,
                    created_by=self.created_by,
                    updated_by=self.created_by,
                    tenant=invoice.tenant
                )
