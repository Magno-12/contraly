from django.db import models

from apps.default.models.base_model import BaseModel


class ConfigurationSetting(BaseModel):
    """
    System-wide configuration settings for the application
    """
    key = models.CharField(max_length=100, unique=True)
    value = models.TextField()
    description = models.TextField(blank=True, null=True)
    is_editable = models.BooleanField(default=True)
    is_encrypted = models.BooleanField(default=False)
    category = models.CharField(max_length=100, default='GENERAL')

    class Meta:
        verbose_name = "Configuration Setting"
        verbose_name_plural = "Configuration Settings"
        ordering = ['category', 'key']

    def __str__(self):
        return f"{self.key}: {self.value}"

    def save(self, *args, **kwargs):
        # TODO: Add encryption for sensitive settings if is_encrypted=True
        super().save(*args, **kwargs)
