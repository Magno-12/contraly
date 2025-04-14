from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver

from apps.organizations.models.organizations import Organization, OrganizationMember


@receiver(post_save, sender=Organization)
def create_organization_settings(sender, instance, created, **kwargs):
    """
    Crear configuración por defecto cuando se crea una nueva organización
    """
    if created:
        from apps.organizations.models.organizations import OrganizationSettings
        
        # Crear configuración por defecto si no existe
        OrganizationSettings.objects.get_or_create(
            organization=instance,
            defaults={
                'created_by': instance.created_by
            }
        )


@receiver(post_save, sender=Organization)
def create_admin_member(sender, instance, created, **kwargs):
    """
    Crear miembro administrador para el creador de la organización
    """
    if created and instance.created_by:
        # Verificar si el creador ya es miembro
        if not OrganizationMember.objects.filter(
            organization=instance,
            user=instance.created_by
        ).exists():
            # Crear miembro administrador
            OrganizationMember.objects.create(
                organization=instance,
                user=instance.created_by,
                role='ADMIN',
                position='Administrador',
                is_active=True,
                created_by=instance.created_by,
                updated_by=instance.created_by
            )


@receiver(pre_delete, sender=Organization)
def handle_organization_deletion(sender, instance, **kwargs):
    """
    Acciones a realizar antes de eliminar una organización
    """
    # Marcar todos los miembros como eliminados
    OrganizationMember.objects.filter(
        organization=instance
    ).update(
        is_active=False,
        is_deleted=True,
        updated_by=instance.updated_by
    )
