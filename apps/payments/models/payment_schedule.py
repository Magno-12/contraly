from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.default.models.base_model import BaseModel


class PaymentSchedule(BaseModel):
    """
    Modelo para programación de pagos para cuentas de cobro
    """
    invoice = models.ForeignKey(
        'invoices.Invoice',
        on_delete=models.CASCADE,
        related_name='payment_schedules',
        verbose_name=_("Cuenta de cobro")
    )
    
    due_date = models.DateField(
        verbose_name=_("Fecha de vencimiento")
    )
    
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name=_("Monto a pagar")
    )
    
    SCHEDULE_STATUS_CHOICES = (
        ('PENDING', _('Pendiente')),
        ('PARTIALLY_PAID', _('Parcialmente pagado')),
        ('PAID', _('Pagado')),
        ('OVERDUE', _('Vencido')),
        ('CANCELLED', _('Cancelado')),
    )
    
    status = models.CharField(
        max_length=20,
        choices=SCHEDULE_STATUS_CHOICES,
        default='PENDING',
        verbose_name=_("Estado")
    )
    
    paid_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name=_("Monto pagado")
    )
    
    payment_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Fecha de pago")
    )
    
    installment_number = models.PositiveIntegerField(
        default=1,
        verbose_name=_("Número de cuota")
    )
    
    total_installments = models.PositiveIntegerField(
        default=1,
        verbose_name=_("Total de cuotas")
    )
    
    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Notas")
    )
    
    # Referencias a pagos asociados
    payments = models.ManyToManyField(
        'payments.Payment',
        blank=True,
        related_name='schedules',
        verbose_name=_("Pagos asociados")
    )
    
    # Multi-tenancy
    tenant = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='payment_schedules',
        verbose_name=_("Organización")
    )
    
    class Meta:
        verbose_name = _("Programación de pago")
        verbose_name_plural = _("Programaciones de pago")
        ordering = ['invoice', 'due_date']
    
    def __str__(self):
        return f"{self.invoice.invoice_number} - Cuota {self.installment_number}/{self.total_installments} - {self.due_date}"
    
    def update_status(self):
        """
        Actualiza el estado de la programación según el monto pagado
        """
        from django.utils import timezone
        today = timezone.now().date()
        
        if self.paid_amount <= 0:
            if self.due_date < today:
                self.status = 'OVERDUE'
            else:
                self.status = 'PENDING'
        elif self.paid_amount < self.amount:
            self.status = 'PARTIALLY_PAID'
        else:
            self.status = 'PAID'
            if not self.payment_date:
                self.payment_date = today
        
        self.save(update_fields=['status', 'payment_date'])
