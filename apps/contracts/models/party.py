from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.default.models.base_model import BaseModel


class ContractParty(BaseModel):
    """
    Entidades o personas que son parte de un contrato
    """
    CONTRACT_PARTY_TYPES = (
        ('CONTRACTOR', _('Contratista')),
        ('CONTRACTING', _('Contratante')),
        ('BENEFICIARY', _('Beneficiario')),
        ('SUPERVISOR', _('Supervisor')),
        ('GUARANTOR', _('Garante')),
        ('OTHER', _('Otro')),
    )
    
    contract = models.ForeignKey(
        'contracts.Contract',
        on_delete=models.CASCADE,
        related_name='parties',
        verbose_name=_("Contrato")
    )
    
    party_type = models.CharField(
        max_length=20,
        choices=CONTRACT_PARTY_TYPES,
        verbose_name=_("Tipo de parte")
    )
    
    # Si la parte es un usuario del sistema
    user = models.ForeignKey(
        'user.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='contract_participations',
        verbose_name=_("Usuario")
    )
    
    # Si la parte es una organización
    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='contract_participations',
        verbose_name=_("Organización")
    )
    
    # Si la parte es un tercero externo
    name = models.CharField(
        max_length=200, 
        blank=True, 
        null=True, 
        verbose_name=_("Nombre")
    )
    identification_type = models.CharField(
        max_length=20, 
        blank=True, 
        null=True, 
        verbose_name=_("Tipo de identificación")
    )
    identification_number = models.CharField(
        max_length=50, 
        blank=True, 
        null=True, 
        verbose_name=_("Número de identificación")
    )
    email = models.EmailField(
        blank=True, 
        null=True, 
        verbose_name=_("Correo electrónico")
    )
    phone = models.CharField(
        max_length=20, 
        blank=True, 
        null=True, 
        verbose_name=_("Teléfono")
    )
    address = models.TextField(
        blank=True, 
        null=True, 
        verbose_name=_("Dirección")
    )
    
    # Datos adicionales
    role = models.CharField(
        max_length=100, 
        blank=True, 
        null=True, 
        verbose_name=_("Rol en el contrato")
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
        related_name='contract_parties',
        verbose_name=_("Organización")
    )
    
    class Meta:
        verbose_name = _("Parte de contrato")
        verbose_name_plural = _("Partes de contrato")
        ordering = ['party_type', 'created_at']
    
    def __str__(self):
        if self.user:
            return f"{self.get_party_type_display()} - {self.user.email}"
        elif self.organization:
            return f"{self.get_party_type_display()} - {self.organization.name}"
        else:
            return f"{self.get_party_type_display()} - {self.name}"
