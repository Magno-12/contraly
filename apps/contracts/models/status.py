from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.default.models.base_model import BaseModel


class ContractStatus(BaseModel):
    """
    Estados del ciclo de vida de un contrato
    """
    STATUS_CHOICES = (
        ('DRAFT', _('Borrador')),
        ('REVIEW', _('En revisión')),
        ('PENDING_APPROVAL', _('Pendiente de aprobación')),
        ('APPROVED', _('Aprobado')),
        ('SIGNED', _('Firmado')),
        ('ACTIVE', _('Activo')),
        ('ON_HOLD', _('Suspendido')),
        ('COMPLETED', _('Completado')),
        ('TERMINATED', _('Terminado')),
        ('CANCELLED', _('Cancelado')),
        ('EXPIRED', _('Expirado')),
        ('ARCHIVED', _('Archivado')),
    )
    
    contract = models.ForeignKey(
        'contracts.Contract',
        on_delete=models.CASCADE,
        related_name='statuses',
        verbose_name=_("Contrato")
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        verbose_name=_("Estado")
    )
    
    start_date = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Fecha de inicio")
    )
    
    end_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Fecha de finalización")
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
        related_name='contract_status_changes',
        verbose_name=_("Cambiado por")
    )
    
    # Multi-tenancy
    tenant = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='contract_statuses',
        verbose_name=_("Organización")
    )
    
    class Meta:
        verbose_name = _("Estado de contrato")
        verbose_name_plural = _("Estados de contrato")
        ordering = ['-start_date']
    
    def __str__(self):
        return f"{self.contract.contract_number} - {self.get_status_display()}"
    
    def save(self, *args, **kwargs):
        # Si es un nuevo estado, cerrar el estado anterior
        if not self.pk:  # Si es un nuevo registro
            previous_status = ContractStatus.objects.filter(
                contract=self.contract,
                end_date__isnull=True,
                is_active=True,
                is_deleted=False
            ).first()
            
            if previous_status:
                from django.utils import timezone
                previous_status.end_date = timezone.now()
                previous_status.save()
                
        super().save(*args, **kwargs)
