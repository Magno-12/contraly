from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.default.models.base_model import BaseModel


class InvoiceItem(BaseModel):
    """
    Ítems específicos dentro de una cuenta de cobro
    """
    invoice = models.ForeignKey(
        'invoices.Invoice',
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name=_("Cuenta de cobro")
    )
    
    description = models.CharField(
        max_length=255,
        verbose_name=_("Descripción")
    )
    
    quantity = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=1,
        verbose_name=_("Cantidad")
    )
    
    unit_price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name=_("Precio unitario")
    )
    
    tax_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        verbose_name=_("Porcentaje de impuesto")
    )
    
    tax_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name=_("Monto de impuesto")
    )
    
    discount_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        verbose_name=_("Porcentaje de descuento")
    )
    
    discount_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name=_("Monto de descuento")
    )
    
    subtotal = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name=_("Subtotal")
    )
    
    total = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name=_("Total")
    )
    
    # Referencia a contrato si aplica
    contract_item = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_("Ítem de contrato")
    )
    
    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Notas")
    )
    
    # Orden del ítem en la cuenta
    order = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Orden")
    )
    
    # Multi-tenancy
    tenant = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name=_("Organización")
    )
    
    class Meta:
        verbose_name = _("Ítem de cuenta de cobro")
        verbose_name_plural = _("Ítems de cuenta de cobro")
        ordering = ['invoice', 'order']
    
    def __str__(self):
        return f"{self.invoice.invoice_number} - {self.description[:30]}"
    
    def save(self, *args, **kwargs):
        # Calcular subtotal
        self.subtotal = self.quantity * self.unit_price
        
        # Calcular montos de impuesto y descuento basados en porcentajes
        if self.tax_percentage > 0:
            self.tax_amount = self.subtotal * (self.tax_percentage / 100)
        
        if self.discount_percentage > 0:
            self.discount_amount = self.subtotal * (self.discount_percentage / 100)
        
        # Calcular total
        self.total = self.subtotal + self.tax_amount - self.discount_amount
        
        # Guardar
        super().save(*args, **kwargs)
        
        # Actualizar totales de la factura
        self.update_invoice_totals()
    
    def update_invoice_totals(self):
        """
        Actualiza los totales de la factura basado en sus ítems
        """
        invoice = self.invoice
        
        # Calcular subtotal, impuestos y descuentos de todos los ítems
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
        invoice.save(update_fields=['subtotal', 'tax_amount', 'discount_amount', 'total_amount'])
