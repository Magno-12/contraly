from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.default.models.base_model import BaseModel


class ContractDocument(BaseModel):
    """
    Documentos asociados a un contrato
    """
    DOCUMENT_TYPES = (
        ('CONTRACT', _('Contrato')),
        ('ANNEX', _('Anexo')),
        ('AMENDMENT', _('Otrosí')),
        ('PROPOSAL', _('Propuesta')),
        ('INVOICE', _('Factura')),
        ('REPORT', _('Informe')),
        ('LEGAL', _('Documento legal')),
        ('TECHNICAL', _('Documento técnico')),
        ('FINANCIAL', _('Documento financiero')),
        ('OTHER', _('Otro')),
    )
    
    contract = models.ForeignKey(
        'contracts.Contract',
        on_delete=models.CASCADE,
        related_name='documents',
        verbose_name=_("Contrato")
    )
    
    document_type = models.CharField(
        max_length=20,
        choices=DOCUMENT_TYPES,
        verbose_name=_("Tipo de documento")
    )
    
    title = models.CharField(
        max_length=200,
        verbose_name=_("Título")
    )
    
    description = models.TextField(
        blank=True, 
        null=True, 
        verbose_name=_("Descripción")
    )
    
    file = models.FileField(
        upload_to='contract_documents/',
        verbose_name=_("Archivo")
    )
    
    is_signed = models.BooleanField(
        default=False,
        verbose_name=_("Está firmado")
    )
    
    signing_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Fecha de firma")
    )
    
    reference_number = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_("Número de referencia")
    )
    
    # Metadatos adicionales
    version = models.CharField(
        max_length=20,
        default="1.0",
        verbose_name=_("Versión")
    )
    
    is_current_version = models.BooleanField(
        default=True,
        verbose_name=_("Es versión actual")
    )
    
    parent_document = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='versions',
        verbose_name=_("Documento origen")
    )
    
    # Multi-tenancy
    tenant = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='contract_documents',
        verbose_name=_("Organización")
    )
    
    class Meta:
        verbose_name = _("Documento de contrato")
        verbose_name_plural = _("Documentos de contrato")
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.get_document_type_display()} - {self.title}"
    
    def save(self, *args, **kwargs):
        # Si es una nueva versión de un documento existente
        if self.parent_document and self.parent_document.is_current_version:
            self.parent_document.is_current_version = False
            self.parent_document.save()
            
        super().save(*args, **kwargs)
