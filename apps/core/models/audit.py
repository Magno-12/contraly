from django.db import models

from apps.default.models.base_model import BaseModel


class AuditLog(BaseModel):
    """
    Audit log for tracking important system activities
    """
    ACTION_CHOICES = (
        ('CREATE', 'Create'),
        ('UPDATE', 'Update'),
        ('DELETE', 'Delete'),
        ('LOGIN', 'Login'),
        ('LOGOUT', 'Logout'),
        ('APPROVE', 'Approve'),
        ('REJECT', 'Reject'),
        ('PAYMENT', 'Payment'),
        ('UPLOAD', 'Upload'),
        ('OTHER', 'Other'),
    )

    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    model_name = models.CharField(max_length=100)
    instance_id = models.CharField(max_length=100)
    description = models.TextField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    tenant = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    data = models.JSONField(null=True, blank=True)

    class Meta:
        verbose_name = "Audit Log"
        verbose_name_plural = "Audit Logs"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.action} - {self.model_name} - {self.created_at}"


class SystemLog(BaseModel):
    """
    System logs for tracking system-level activities and errors
    """
    LEVEL_CHOICES = (
        ('DEBUG', 'Debug'),
        ('INFO', 'Info'),
        ('WARNING', 'Warning'),
        ('ERROR', 'Error'),
        ('CRITICAL', 'Critical'),
    )

    level = models.CharField(max_length=10, choices=LEVEL_CHOICES)
    source = models.CharField(max_length=100)
    message = models.TextField()
    stack_trace = models.TextField(null=True, blank=True)
    tenant = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )

    class Meta:
        verbose_name = "System Log"
        verbose_name_plural = "System Logs"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.level} - {self.source} - {self.created_at}"
