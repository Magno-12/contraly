from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.default.models.base_model import BaseModel


class InvoiceSchedule(BaseModel):
    """
    Programación de cuentas de cobro recurrentes
    """
    SCHEDULE_TYPES = (
        ('WEEKLY', _('Semanal')),
        ('BIWEEKLY', _('Quincenal')),
        ('MONTHLY', _('Mensual')),
        ('BIMONTHLY', _('Bimestral')),
        ('QUARTERLY', _('Trimestral')),
        ('SEMIANNUAL', _('Semestral')),
        ('ANNUAL', _('Anual')),
        ('CUSTOM', _('Personalizado')),
    )
    
    contract = models.ForeignKey(
        'contracts.Contract',
        on_delete=models.CASCADE,
        related_name='invoice_schedules',
        verbose_name=_("Contrato")
    )
    
    name = models.CharField(
        max_length=100,
        verbose_name=_("Nombre")
    )
    
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Descripción")
    )
    
    schedule_type = models.CharField(
        max_length=20,
        choices=SCHEDULE_TYPES,
        verbose_name=_("Tipo de programación")
    )
    
    start_date = models.DateField(
        verbose_name=_("Fecha de inicio")
    )
    
    end_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Fecha de finalización")
    )
    
    # Para programación personalizada
    custom_days = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_("Días personalizados")
    )
    
    # Para programación específica de día del mes
    day_of_month = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_("Día del mes"),
        help_text=_("Para cuentas mensuales o trimestrales")
    )
    
    # Generación automática
    is_auto_generate = models.BooleanField(
        default=True,
        verbose_name=_("Generar automáticamente")
    )
    
    auto_approve = models.BooleanField(
        default=False,
        verbose_name=_("Aprobar automáticamente")
    )
    
    # Estado
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Activa")
    )
    
    last_generated = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Última generación")
    )
    
    next_generation = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Próxima generación")
    )
    
    # Valores predeterminados para las cuentas generadas
    value = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name=_("Valor")
    )
    
    # Multi-tenancy
    tenant = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='invoice_schedules',
        verbose_name=_("Organización")
    )
    
    class Meta:
        verbose_name = _("Programación de cuenta de cobro")
        verbose_name_plural = _("Programaciones de cuenta de cobro")
        ordering = ['-is_active', 'contract', 'schedule_type']
    
    def __str__(self):
        return f"{self.name} - {self.get_schedule_type_display()} - {self.contract.contract_number}"
    
    def calculate_next_generation(self):
        """
        Calcula la próxima fecha de generación según el tipo de programación
        """
        import datetime
        from dateutil.relativedelta import relativedelta
        
        if not self.last_generated:
            # Si nunca se ha generado, la próxima es la fecha de inicio
            return self.start_date
        
        last_date = self.last_generated
        
        if self.schedule_type == 'WEEKLY':
            next_date = last_date + datetime.timedelta(days=7)
        elif self.schedule_type == 'BIWEEKLY':
            next_date = last_date + datetime.timedelta(days=14)
        elif self.schedule_type == 'MONTHLY':
            next_date = last_date + relativedelta(months=1)
            # Manejar el día específico del mes si está definido
            if self.day_of_month and self.day_of_month > 0:
                next_date = next_date.replace(day=min(self.day_of_month, 28))
        elif self.schedule_type == 'BIMONTHLY':
            next_date = last_date + relativedelta(months=2)
        elif self.schedule_type == 'QUARTERLY':
            next_date = last_date + relativedelta(months=3)
        elif self.schedule_type == 'SEMIANNUAL':
            next_date = last_date + relativedelta(months=6)
        elif self.schedule_type == 'ANNUAL':
            next_date = last_date + relativedelta(years=1)
        elif self.schedule_type == 'CUSTOM' and self.custom_days:
            next_date = last_date + datetime.timedelta(days=self.custom_days)
        else:
            # Por defecto, mensual
            next_date = last_date + relativedelta(months=1)
        
        # Verificar que no exceda la fecha de finalización
        if self.end_date and next_date > self.end_date:
            return None
        
        return next_date
    
    def save(self, *args, **kwargs):
        # Calcular próxima generación si es necesario
        if self.is_active and (not self.next_generation or kwargs.get('recalculate', False)):
            self.next_generation = self.calculate_next_generation()
            
        # Quitar el parámetro personalizado si existe
        if 'recalculate' in kwargs:
            del kwargs['recalculate']
            
        super().save(*args, **kwargs)
