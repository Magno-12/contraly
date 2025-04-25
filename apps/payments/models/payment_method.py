from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.default.models.base_model import BaseModel


class PaymentMethod(BaseModel):
    """
    Modelo para representar los diferentes métodos de pago disponibles
    """
    name = models.CharField(
        max_length=100,
        verbose_name=_("Nombre")
    )
    
    code = models.CharField(
        max_length=50,
        unique=True,
        verbose_name=_("Código")
    )
    
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Descripción")
    )
    
    PAYMENT_TYPE_CHOICES = (
        ('CASH', _('Efectivo')),
        ('BANK_TRANSFER', _('Transferencia bancaria')),
        ('CHECK', _('Cheque')),
        ('CREDIT_CARD', _('Tarjeta de crédito')),
        ('DEBIT_CARD', _('Tarjeta de débito')),
        ('ELECTRONIC', _('Pago electrónico')),
        ('OTHER', _('Otro')),
    )
    
    payment_type = models.CharField(
        max_length=20,
        choices=PAYMENT_TYPE_CHOICES,
        default='BANK_TRANSFER',
        verbose_name=_("Tipo de pago")
    )
    
    requires_reference = models.BooleanField(
        default=True,
        verbose_name=_("Requiere referencia")
    )
    
    requires_receipt = models.BooleanField(
        default=True,
        verbose_name=_("Requiere comprobante")
    )
    
    requires_bank_info = models.BooleanField(
        default=False,
        verbose_name=_("Requiere información bancaria")
    )
    
    # Configuración para la organización
    allow_partial = models.BooleanField(
        default=True,
        verbose_name=_("Permite pagos parciales")
    )
    
    # Multi-tenancy
    tenant = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='payment_methods',
        verbose_name=_("Organización")
    )
    
    class Meta:
        verbose_name = _("Método de pago")
        verbose_name_plural = _("Métodos de pago")
        ordering = ['name']
        unique_together = [['code', 'tenant']]
    
    def __str__(self):
        return self.name
