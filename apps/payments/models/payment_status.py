from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.default.models.base_model import BaseModel


class PaymentStatus(BaseModel):
    """
    Modelo para definir los diferentes estados de un pago
    """
    STATUS_CHOICES = (
        ('PENDING', _('Pendiente de verificación')),
        ('VERIFIED', _('Verificado')),
        ('REJECTED', _('Rechazado')),
        ('REFUNDED', _('Reembolsado')),
        ('CANCELLED', _('Cancelado')),
    )
    
    payment = models.ForeignKey(
        'payments.Payment',
        on_delete=models.CASCADE,
        related_name='status_history',
        verbose_name=_("Pago")
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        verbose_name=_("Estado")
    )
    
    change_date = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Fecha de cambio")
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
        related_name='payment_status_changes',
        verbose_name=_("Cambiado por")
    )
    
    # Multi-tenancy
    tenant = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='payment_statuses',
        verbose_name=_("Organización")
    )
    
    class Meta:
        verbose_name = _("Estado de pago")
        verbose_name_plural = _("Estados de pago")
        ordering = ['-change_date']
        get_latest_by = 'change_date'
    
    def __str__(self):
        return f"{self.payment} - {self.get_status_display()}"
