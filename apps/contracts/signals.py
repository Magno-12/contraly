from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from django.utils import timezone

from apps.contracts.models import (
    Contract, ContractDocument, ContractStatus, ContractRevision
)
from apps.core.utils import create_audit_log


@receiver(post_save, sender=Contract)
def contract_post_save(sender, instance, created, **kwargs):
    """
    Acciones a realizar después de guardar un contrato
    """
    # Si es un contrato nuevo, crear el estado inicial si no existe
    if created and not instance.statuses.exists():
        ContractStatus.objects.create(
            contract=instance,
            status='DRAFT',
            changed_by=instance.created_by,
            created_by=instance.created_by,
            updated_by=instance.created_by,
            tenant=instance.tenant
        )
        
        # Crear revisión inicial
        ContractRevision.objects.create(
            contract=instance,
            revision_type='CREATION',
            description="Creación inicial del contrato",
            created_by=instance.created_by,
            updated_by=instance.created_by,
            tenant=instance.tenant
        )
    
    # Actualizaciones especiales basadas en estado
    # Si está en estado ACTIVE y end_date es pasado, cambiar a COMPLETED
    current_status = instance.current_status
    if current_status and current_status.status == 'ACTIVE':
        today = timezone.now().date()
        if instance.end_date and instance.end_date < today:
            # Cambiar a COMPLETED o EXPIRED
            ContractStatus.objects.create(
                contract=instance,
                status='COMPLETED',
                comments="Contrato completado automáticamente por fecha de finalización",
                changed_by=instance.updated_by,
                created_by=instance.updated_by,
                updated_by=instance.updated_by,
                tenant=instance.tenant
            )


@receiver(post_save, sender=ContractDocument)
def document_post_save(sender, instance, created, **kwargs):
    """
    Acciones a realizar después de guardar un documento
    """
    # Si es un nuevo documento de contrato, crear revisión
    if created:
        ContractRevision.objects.create(
            contract=instance.contract,
            revision_type='UPLOAD',
            description=f"Carga de documento: {instance.title}",
            document=instance,
            created_by=instance.created_by,
            updated_by=instance.created_by,
            tenant=instance.tenant
        )
    
    # Si es el documento principal y está firmado, actualizar contrato
    if instance.document_type == 'CONTRACT' and instance.is_signed:
        contract = instance.contract
        # Actualizar fecha de firma si no tiene
        if not contract.signing_date and instance.signing_date:
            contract.signing_date = instance.signing_date
            contract.save(update_fields=['signing_date', 'updated_by'])
            
        # Si el estado actual es APPROVED, cambiarlo a SIGNED
        current_status = contract.current_status
        if current_status and current_status.status == 'APPROVED':
            ContractStatus.objects.create(
                contract=contract,
                status='SIGNED',
                comments=f"Contrato firmado. Documento: {instance.title}",
                changed_by=instance.updated_by or instance.created_by,
                created_by=instance.created_by,
                updated_by=instance.updated_by or instance.created_by,
                tenant=instance.tenant
            )


@receiver(post_save, sender=ContractStatus)
def status_post_save(sender, instance, created, **kwargs):
    """
    Acciones a realizar después de guardar un estado de contrato
    """
    if not created:
        return  # Solo para nuevos estados
    
    # Si el estado es SIGNED, verificar si debe cambiar a ACTIVE automáticamente
    if instance.status == 'SIGNED':
        contract = instance.contract
        today = timezone.now().date()
        
        # Si la fecha de inicio es hoy o anterior, cambiar a ACTIVE
        if contract.start_date and contract.start_date <= today:
            # Solo crear nuevo estado si el actual no es ACTIVE
            current_status = contract.current_status
            if current_status and current_status.status != 'ACTIVE':
                ContractStatus.objects.create(
                    contract=contract,
                    status='ACTIVE',
                    comments="Contrato activado automáticamente por fecha de inicio",
                    changed_by=instance.changed_by or instance.created_by,
                    created_by=instance.created_by,
                    updated_by=instance.updated_by,
                    tenant=instance.tenant
                )
