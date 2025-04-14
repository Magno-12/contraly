from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.conf import settings

from apps.core.models import AuditLog

User = get_user_model()

def create_audit_log(sender, instance, user=None, action=None, **kwargs):
    """
    Create an audit log entry for model changes
    """
    # Skip audit logs for AuditLog model to prevent infinite recursion
    if sender == AuditLog:
        return

    # Skip if audit logging is disabled
    if not getattr(settings, 'ENABLE_AUDIT_LOGGING', True):
        return

    # Default user to system user if not provided
    if not user:
        try:
            # Try to get system user, fall back to first superuser
            user = User.objects.filter(email=settings.SYSTEM_USER_EMAIL).first() or \
                   User.objects.filter(is_superuser=True).first()
        except:
            user = None

    # Create log entry
    try:
        AuditLog.objects.create(
            action=action,
            model_name=sender.__name__,
            instance_id=str(instance.id),
            description=f"{action} operation on {sender.__name__} with ID {instance.id}",
            created_by=user,
            tenant=getattr(instance, 'tenant', None) if hasattr(instance, 'tenant') else None
        )
    except Exception as e:
        # Log error but don't crash the main operation
        print(f"Error creating audit log: {str(e)}")


@receiver(post_save)
def model_post_save(sender, instance, created, **kwargs):
    """Create audit log entry when a model is saved"""
    if created:
        create_audit_log(sender, instance, action='CREATE')
    else:
        create_audit_log(sender, instance, action='UPDATE')


@receiver(post_delete)
def model_post_delete(sender, instance, **kwargs):
    """Create audit log entry when a model is deleted"""
    create_audit_log(sender, instance, action='DELETE')
