import json
import logging
from django.conf import settings
from django.utils import timezone
from apps.core.models import SystemLog, AuditLog

logger = logging.getLogger(__name__)

def log_system_event(level, source, message, stack_trace=None, tenant=None, save_to_db=True):
    """
    Log a system event to both the standard logger and database
    
    Args:
        level (str): Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        source (str): Source of the log (module/component name)
        message (str): Message to log
        stack_trace (str, optional): Stack trace for errors
        tenant (Tenant, optional): Related tenant if applicable
        save_to_db (bool): Whether to save the log to database
    """
    # Map the level string to the corresponding logging method
    log_methods = {
        'DEBUG': logger.debug,
        'INFO': logger.info,
        'WARNING': logger.warning,
        'ERROR': logger.error,
        'CRITICAL': logger.critical
    }
    
    # Log to standard logger
    log_method = log_methods.get(level, logger.info)
    if tenant:
        log_method(f"[{tenant.name}] {source}: {message}")
    else:
        log_method(f"{source}: {message}")
    
    # Save to database if enabled
    if save_to_db and getattr(settings, 'ENABLE_SYSTEM_LOGGING', True):
        try:
            SystemLog.objects.create(
                level=level,
                source=source,
                message=message,
                stack_trace=stack_trace,
                tenant=tenant
            )
        except Exception as e:
            # Don't crash the application if logging fails
            logger.error(f"Failed to save system log to database: {str(e)}")


def create_audit_log(user, action, model_name, instance_id, description, ip_address=None, 
                    user_agent=None, data=None, tenant=None):
    """
    Create an audit log entry
    
    Args:
        user: User who performed the action
        action (str): Action performed (CREATE, UPDATE, etc.)
        model_name (str): Name of the model
        instance_id (str): ID of the affected instance
        description (str): Description of the action
        ip_address (str, optional): IP address of the user
        user_agent (str, optional): User agent string
        data (dict, optional): Additional data to store
        tenant (Tenant, optional): Related tenant
    """
    try:
        return AuditLog.objects.create(
            action=action,
            model_name=model_name,
            instance_id=instance_id,
            description=description,
            ip_address=ip_address,
            user_agent=user_agent,
            data=data,
            tenant=tenant,
            created_by=user
        )
    except Exception as e:
        # Log error but don't crash the main operation
        logger.error(f"Failed to create audit log: {str(e)}")
        return None


def get_client_ip(request):
    """
    Get client IP address from request
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def get_tenant_from_request(request):
    """
    Extract tenant from request based on domain or headers
    """
    # Try to get from subdomain
    host = request.get_host().lower()
    subdomain = host.split('.')[0] if '.' in host else None
    
    # If this is a custom domain or IP, subdomain parsing won't work
    # Try to get from header instead
    tenant_id = request.headers.get('X-Tenant-ID')
    
    # Return tenant based on found information
    if tenant_id:
        from apps.tenants.models import Tenant
        return Tenant.objects.filter(id=tenant_id, is_active=True).first()
    elif subdomain and subdomain not in ['www', 'api', 'admin']:
        from apps.tenants.models import Tenant
        return Tenant.objects.filter(subdomain=subdomain, is_active=True).first()
    
    return None


def encrypt_sensitive_data(data):
    """
    Encrypt sensitive data before storing
    """
    # TODO: Implement encryption using Fernet or similar
    return data


def decrypt_sensitive_data(encrypted_data):
    """
    Decrypt sensitive data for display
    """
    # TODO: Implement decryption using Fernet or similar
    return encrypted_data
