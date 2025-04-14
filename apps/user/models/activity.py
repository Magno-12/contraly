from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.default.models.base_model import BaseModel


class LoginAttempt(BaseModel):
    """Track login attempts for security purposes"""

    email = models.EmailField()
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True, null=True)
    successful = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    class Meta:
        verbose_name = _('login attempt')
        verbose_name_plural = _('login attempts')
        ordering = ['-created_at']
        
    def __str__(self):
        return f"{self.email} - {'Success' if self.successful else 'Failed'} - {self.created_at}"


class UserActivity(BaseModel):
    """Track user activities for analytics"""
    
    ACTIVITY_TYPES = (
        ('LOGIN', 'Login'),
        ('LOGOUT', 'Logout'),
        ('VIEW', 'View'),
        ('CREATE', 'Create'),
        ('UPDATE', 'Update'),
        ('DELETE', 'Delete'),
        ('APPROVE', 'Approve'),
        ('REJECT', 'Reject'),
        ('DOWNLOAD', 'Download'),
        ('UPLOAD', 'Upload'),
        ('OTHER', 'Other'),
    )
    
    user = models.ForeignKey(
        'user.User',
        on_delete=models.CASCADE,
        related_name='activities'
    )
    activity_type = models.CharField(max_length=20, choices=ACTIVITY_TYPES)
    description = models.TextField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    module = models.CharField(max_length=100, default='GENERAL')
    page = models.CharField(max_length=255, null=True, blank=True)
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    
    class Meta:
        verbose_name = _('user activity')
        verbose_name_plural = _('user activities')
        ordering = ['-created_at']
        
    def __str__(self):
        return f"{self.user.email} - {self.activity_type} - {self.created_at}"


class UserSession(BaseModel):
    """Track user sessions"""
    
    user = models.ForeignKey(
        'user.User',
        on_delete=models.CASCADE,
        related_name='sessions'
    )
    session_key = models.CharField(max_length=40)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    device_type = models.CharField(max_length=20, null=True, blank=True)
    browser = models.CharField(max_length=100, null=True, blank=True)
    os = models.CharField(max_length=100, null=True, blank=True)
    expires_at = models.DateTimeField()
    is_expired = models.BooleanField(default=False)
    logout_time = models.DateTimeField(null=True, blank=True)
    last_activity = models.DateTimeField(auto_now=True)
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    
    class Meta:
        verbose_name = _('user session')
        verbose_name_plural = _('user sessions')
        ordering = ['-created_at']
        
    def __str__(self):
        return f"{self.user.email} - {self.created_at}"
