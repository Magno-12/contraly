from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.default.models.base_model import BaseModel


class Withholding(BaseModel):
    """
    Modelo para representar retenciones aplicadas a los pagos
    """
    payment = models.ForeignKey(
        'payments.Payment',
        on_delete=models.CASCADE,
        related_name='withholdings',
        verbose_name=_("Pago")
    )
    
    name = models.CharField(
        max_length=100,
        verbose_name=_("Nombre de la retención")
    )
    
    code = models.CharField(
        max_length=50,
        verbose_name=_("Código")
    )
    
    percentage = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        verbose_name=_("Porcentaje")
    )
    
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name=_("Monto retenido")
    )
    
    # Tipo de retención
    WITHHOLDING_TYPE_CHOICES = (
        ('TAX', _('Impuesto')),
        ('SOCIAL_SECURITY', _('Seguridad social')),
        ('PENSION', _('Pensión')),
        ('OTHER', _('Otro')),
    )
    
    withholding_type = models.CharField(
        max_length=20,
        choices=WITHHOLDING_TYPE_CHOICES,
        default='TAX',
        verbose_name=_("Tipo de retención")
    )
    
    # Documentos de soporte
    certificate = models.FileField(
        upload_to='withholding_certificates/',
        null=True,
        blank=True,
        verbose_name=_("Certificado de retención")
    )
    
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Descripción")
    )
    
    # Multi-tenancy
    tenant = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='withholdings',
        verbose_name=_("Organización")
    )
    
    class Meta:
        verbose_name = _("Retención")
        verbose_name_plural = _("Retenciones")
        ordering = ['payment', 'name']
    
    def __str__(self):
        return f"{self.name} - {self.percentage}% - {self.amount}"
    
    def save(self, *args, **kwargs):
        # Calcular automáticamente el monto de retención si no está establecido
        if not self.amount and self.percentage and hasattr(self, 'payment'):
            self.amount = self.payment.amount * (self.percentage / 100)
        
        super().save(*args, **kwargs)
