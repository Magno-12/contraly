from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.default.models.base_model import BaseModel


class ContractType(BaseModel):
    """
    Tipos de contratos disponibles en el sistema
    """
    name = models.CharField(max_length=100, verbose_name=_("Nombre"))
    code = models.CharField(max_length=20, unique=True, verbose_name=_("Código"))
    description = models.TextField(blank=True, null=True, verbose_name=_("Descripción"))
    template = models.TextField(blank=True, null=True, verbose_name=_("Plantilla"))
    requires_approval = models.BooleanField(default=True, verbose_name=_("Requiere aprobación"))
    sequential_number = models.BooleanField(default=True, verbose_name=_("Numeración secuencial"))
    tenant = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='contract_types',
        verbose_name=_("Organización")
    )

    class Meta:
        verbose_name = _("Tipo de contrato")
        verbose_name_plural = _("Tipos de contrato")
        ordering = ['name']
        unique_together = [['name', 'tenant'], ['code', 'tenant']]

    def __str__(self):
        return self.name


class Contract(BaseModel):
    """
    Modelo principal para almacenar los contratos
    """
    contract_number = models.CharField(max_length=50, verbose_name=_("Número de contrato"))
    title = models.CharField(max_length=200, verbose_name=_("Título"))
    contract_type = models.ForeignKey(
        ContractType,
        on_delete=models.PROTECT,
        related_name='contracts',
        verbose_name=_("Tipo de contrato")
    )
    description = models.TextField(blank=True, null=True, verbose_name=_("Descripción"))

    # Fechas importantes
    start_date = models.DateField(verbose_name=_("Fecha de inicio"))
    end_date = models.DateField(verbose_name=_("Fecha de finalización"))
    signing_date = models.DateField(null=True, blank=True, verbose_name=_("Fecha de firma"))

    # Información financiera
    value = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        verbose_name=_("Valor del contrato")
    )
    currency = models.CharField(
        max_length=3, 
        default="COP", 
        verbose_name=_("Moneda")
    )

    # Información de supervisión
    supervisor = models.ForeignKey(
        'user.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='supervised_contracts',
        verbose_name=_("Supervisor")
    )

    # Cláusulas especiales
    special_clauses = models.TextField(blank=True, null=True, verbose_name=_("Cláusulas especiales"))

    # Metadatos y organización
    reference_number = models.CharField(
        max_length=100, 
        blank=True, 
        null=True, 
        verbose_name=_("Número de referencia")
    )
    department = models.CharField(
        max_length=100, 
        blank=True, 
        null=True, 
        verbose_name=_("Departamento/Área")
    )
    is_renewal = models.BooleanField(
        default=False, 
        verbose_name=_("Es una renovación")
    )
    parent_contract = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='renewals',
        verbose_name=_("Contrato origen")
    )
    requires_performance_bond = models.BooleanField(
        default=False, 
        verbose_name=_("Requiere póliza de cumplimiento")
    )

    # Multi-tenancy
    tenant = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='contracts',
        verbose_name=_("Organización")
    )

    class Meta:
        verbose_name = _("Contrato")
        verbose_name_plural = _("Contratos")
        ordering = ['-created_at']
        unique_together = [['contract_number', 'tenant']]

    def __str__(self):
        return f"{self.contract_number} - {self.title}"

    @property
    def current_status(self):
        """Obtener el estado actual del contrato"""
        status = self.statuses.filter(
            is_active=True,
            is_deleted=False
        ).order_by('-created_at').first()

        return status
