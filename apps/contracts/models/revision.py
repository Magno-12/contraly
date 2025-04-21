from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.default.models.base_model import BaseModel


class ContractRevision(BaseModel):
    """
    Historial de revisiones y cambios en contratos
    """
    REVISION_TYPES = (
        ('CREATION', _('Creación')),
        ('UPDATE', _('Actualización')),
        ('AMENDMENT', _('Otrosí')),
        ('APPROVAL', _('Aprobación')),
        ('RENEWAL', _('Renovación')),
        ('TERMINATION', _('Terminación')),
        ('OTHER', _('Otro')),
    )
    
    contract = models.ForeignKey(
        'contracts.Contract',
        on_delete=models.CASCADE,
        related_name='revisions',
        verbose_name=_("Contrato")
    )
    
    revision_type = models.CharField(
        max_length=20,
        choices=REVISION_TYPES,
        verbose_name=_("Tipo de revisión")
    )
    
    description = models.TextField(
        verbose_name=_("Descripción del cambio")
    )
    
    previous_data = models.JSONField(
        null=True,
        blank=True,
        verbose_name=_("Datos anteriores")
    )
    
    new_data = models.JSONField(
        null=True,
        blank=True,
        verbose_name=_("Datos nuevos")
    )
    
    document = models.ForeignKey(
        'contracts.ContractDocument',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='revisions',
        verbose_name=_("Documento asociado")
    )
    
    revision_date = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Fecha de revisión")
    )
    
    # Multi-tenancy
    tenant = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='contract_revisions',
        verbose_name=_("Organización")
    )
    
    class Meta:
        verbose_name = _("Revisión de contrato")
        verbose_name_plural = _("Revisiones de contrato")
        ordering = ['-revision_date']
    
    def __str__(self):
        return f"{self.get_revision_type_display()} - {self.revision_date}"
