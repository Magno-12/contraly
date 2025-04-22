from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.default.models.base_model import BaseModel


class Invoice(BaseModel):
    """
    Modelo principal para cuentas de cobro
    """
    # Identificación de la cuenta de cobro
    invoice_number = models.CharField(max_length=50, verbose_name=_("Número de cuenta"))
    title = models.CharField(max_length=200, verbose_name=_("Título/Concepto"))
    
    # Relación con contrato (opcional)
    contract = models.ForeignKey(
        'contracts.Contract',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invoices',
        verbose_name=_("Contrato asociado")
    )
    
    # Información del emisor
    issuer = models.ForeignKey(
        'user.User',
        on_delete=models.PROTECT,
        related_name='issued_invoices',
        verbose_name=_("Emisor")
    )
    
    # Información del receptor
    recipient_type = models.CharField(
        max_length=20,
        choices=(
            ('ORGANIZATION', _('Organización')),
            ('USER', _('Usuario')),
            ('EXTERNAL', _('Externo')),
        ),
        default='ORGANIZATION',
        verbose_name=_("Tipo de receptor")
    )
    
    recipient_organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='received_invoices',
        verbose_name=_("Organización receptora")
    )
    
    recipient_user = models.ForeignKey(
        'user.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='received_invoices',
        verbose_name=_("Usuario receptor")
    )
    
    recipient_name = models.CharField(
        max_length=200, 
        blank=True, 
        null=True, 
        verbose_name=_("Nombre del receptor externo")
    )
    
    recipient_identification = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name=_("Identificación del receptor")
    )
    
    # Fechas importantes
    issue_date = models.DateField(verbose_name=_("Fecha de emisión"))
    due_date = models.DateField(verbose_name=_("Fecha de vencimiento"))
    period_start = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Fecha inicio del periodo")
    )
    period_end = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Fecha fin del periodo")
    )
    
    # Información económica
    subtotal = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name=_("Subtotal")
    )
    
    tax_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name=_("Impuestos")
    )
    
    discount_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name=_("Descuentos")
    )
    
    total_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name=_("Total")
    )
    
    currency = models.CharField(
        max_length=3,
        default="COP",
        verbose_name=_("Moneda")
    )
    
    # Información adicional
    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Notas")
    )
    
    payment_terms = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Términos de pago")
    )
    
    reference = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_("Referencia")
    )
    
    payment_method = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name=_("Método de pago")
    )
    
    is_paid = models.BooleanField(
        default=False,
        verbose_name=_("Está pagada")
    )
    
    payment_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Fecha de pago")
    )
    
    # Documento generado
    document = models.FileField(
        upload_to='invoice_documents/',
        null=True,
        blank=True,
        verbose_name=_("Documento")
    )
    
    # Multi-tenancy
    tenant = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='invoices',
        verbose_name=_("Organización")
    )
    
    class Meta:
        verbose_name = _("Cuenta de cobro")
        verbose_name_plural = _("Cuentas de cobro")
        ordering = ['-issue_date', '-created_at']
        unique_together = [['invoice_number', 'tenant']]
    
    def __str__(self):
        return f"{self.invoice_number} - {self.title}"
    
    @property
    def current_status(self):
        """Obtener el estado actual de la cuenta de cobro"""
        status = self.statuses.filter(
            is_active=True,
            is_deleted=False
        ).order_by('-created_at').first()
        
        return status
    
    def save(self, *args, **kwargs):
        # Calcular total si no está definido
        if self.subtotal and not self.total_amount:
            self.total_amount = self.subtotal + self.tax_amount - self.discount_amount
            
        super().save(*args, **kwargs)
