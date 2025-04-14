from django.db import models
from django_tenants.models import TenantMixin, DomainMixin

from apps.default.models.base_model import BaseModel


class Organization(TenantMixin, BaseModel):
    """
    Modelo para representar una organización gubernamental (tenant)
    Implementa TenantMixin para permitir la funcionalidad multi-tenant
    """
    name = models.CharField(max_length=100, verbose_name="Nombre")
    subdomain = models.CharField(max_length=100, unique=True, verbose_name="Subdominio")
    description = models.TextField(blank=True, null=True, verbose_name="Descripción")
    
    # Información de contacto
    logo = models.ImageField(upload_to='organization_logos/', null=True, blank=True, verbose_name="Logo")
    email = models.EmailField(blank=True, null=True, verbose_name="Email de contacto")
    phone = models.CharField(max_length=30, blank=True, null=True, verbose_name="Teléfono")
    address = models.TextField(blank=True, null=True, verbose_name="Dirección")
    city = models.CharField(max_length=100, blank=True, null=True, verbose_name="Ciudad")
    state = models.CharField(max_length=100, blank=True, null=True, verbose_name="Departamento")
    country = models.CharField(max_length=100, default="Colombia", verbose_name="País")
    zip_code = models.CharField(max_length=20, blank=True, null=True, verbose_name="Código postal")
    tax_id = models.CharField(max_length=50, blank=True, null=True, verbose_name="NIT")
    
    # Personalización de la interfaz
    primary_color = models.CharField(max_length=20, default='#1976D2', verbose_name="Color primario")
    secondary_color = models.CharField(max_length=20, default='#424242', verbose_name="Color secundario")
    
    # Configuración y límites
    max_users = models.PositiveIntegerField(default=10, verbose_name="Máximo de usuarios")
    max_storage_gb = models.PositiveIntegerField(default=5, verbose_name="Almacenamiento máximo (GB)")
    
    # Facturación
    paid_until = models.DateField(null=True, blank=True, verbose_name="Pagado hasta")
    on_trial = models.BooleanField(default=True, verbose_name="En período de prueba")
    trial_ends = models.DateField(null=True, blank=True, verbose_name="Fin del período de prueba")
    
    # Tipo de organización
    ORGANIZATION_TYPES = (
        ('GOV_ENTITY', 'Entidad Gubernamental'),
        ('CONTRACTOR', 'Contratista'),
        ('PROVIDER', 'Proveedor'),
        ('OTHER', 'Otro'),
    )
    organization_type = models.CharField(
        max_length=20, 
        choices=ORGANIZATION_TYPES, 
        default='GOV_ENTITY',
        verbose_name="Tipo de organización"
    )
    
    # Configuración de django-tenants
    auto_create_schema = True
    
    class Meta:
        verbose_name = "Organización"
        verbose_name_plural = "Organizaciones"
    
    def __str__(self):
        return self.name


class Domain(DomainMixin, BaseModel):
    """
    Modelo para dominios asociados a las organizaciones
    Implementa DomainMixin para permitir la funcionalidad multi-tenant
    """
    is_primary = models.BooleanField(
        default=True, 
        help_text="¿Es este el dominio principal de la organización?",
        verbose_name="Dominio principal"
    )
    
    class Meta:
        verbose_name = "Dominio"
        verbose_name_plural = "Dominios"
        unique_together = (('domain', 'tenant'))
    
    def __str__(self):
        return self.domain


class OrganizationMember(BaseModel):
    """
    Modelo para gestionar miembros de una organización
    Permite definir roles específicos dentro de cada organización
    """
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='members',
        verbose_name="Organización"
    )
    user = models.ForeignKey(
        'user.User',
        on_delete=models.CASCADE,
        related_name='organization_memberships',
        verbose_name="Usuario"
    )
    
    # Roles específicos dentro de la organización
    ROLE_CHOICES = (
        ('ADMIN', 'Administrador'),
        ('MANAGER', 'Gestor'),
        ('SUPERVISOR', 'Supervisor'),
        ('CONTRACTOR', 'Contratista'),
        ('APPROVER', 'Aprobador'),
        ('VIEWER', 'Visualizador'),
    )
    role = models.CharField(
        max_length=20, 
        choices=ROLE_CHOICES,
        verbose_name="Rol en la organización"
    )
    
    # Datos específicos del miembro
    position = models.CharField(max_length=100, blank=True, null=True, verbose_name="Cargo")
    department = models.CharField(max_length=100, blank=True, null=True, verbose_name="Departamento/Área")
    start_date = models.DateField(null=True, blank=True, verbose_name="Fecha de inicio")
    end_date = models.DateField(null=True, blank=True, verbose_name="Fecha de finalización")
    notes = models.TextField(blank=True, null=True, verbose_name="Notas")
    
    class Meta:
        verbose_name = "Miembro de organización"
        verbose_name_plural = "Miembros de organizaciones"
        unique_together = (('organization', 'user'),)
    
    def __str__(self):
        return f"{self.user.email} - {self.get_role_display()} en {self.organization.name}"


class OrganizationSettings(BaseModel):
    """
    Configuraciones específicas por organización
    """
    organization = models.OneToOneField(
        Organization,
        on_delete=models.CASCADE,
        related_name='settings',
        verbose_name="Organización"
    )
    
    # Configuraciones de workflow
    require_double_approval = models.BooleanField(
        default=False,
        verbose_name="Requerir doble aprobación"
    )
    allow_self_approval = models.BooleanField(
        default=False,
        verbose_name="Permitir auto-aprobación"
    )
    
    # Configuraciones de notificaciones
    email_notifications = models.BooleanField(
        default=True,
        verbose_name="Notificaciones por email"
    )
    sms_notifications = models.BooleanField(
        default=False,
        verbose_name="Notificaciones por SMS"
    )
    
    # Configuraciones de seguridad
    force_password_change = models.BooleanField(
        default=True,
        verbose_name="Forzar cambio de contraseña"
    )
    password_expiry_days = models.IntegerField(
        default=90,
        verbose_name="Días para expiración de contraseña"
    )
    session_timeout_minutes = models.IntegerField(
        default=30,
        verbose_name="Tiempo de inactividad para cierre de sesión (minutos)"
    )
    
    # Configuración fiscal y de facturación
    fiscal_year_start = models.DateField(
        null=True, 
        blank=True,
        verbose_name="Inicio de año fiscal"
    )
    default_currency = models.CharField(
        max_length=3,
        default="COP",
        verbose_name="Moneda predeterminada"
    )
    
    class Meta:
        verbose_name = "Configuración de organización"
        verbose_name_plural = "Configuraciones de organizaciones"
    
    def __str__(self):
        return f"Configuración de {self.organization.name}"


class OrganizationInvitation(BaseModel):
    """
    Invitaciones para unirse a una organización
    """
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='invitations',
        verbose_name="Organización"
    )
    email = models.EmailField(verbose_name="Email del invitado")
    token = models.CharField(max_length=100, unique=True, verbose_name="Token de invitación")
    
    # Rol que se asignará al aceptar
    role = models.CharField(
        max_length=20, 
        choices=OrganizationMember.ROLE_CHOICES,
        verbose_name="Rol a asignar"
    )
    
    # Estados de la invitación
    STATUS_CHOICES = (
        ('PENDING', 'Pendiente'),
        ('ACCEPTED', 'Aceptada'),
        ('REJECTED', 'Rechazada'),
        ('EXPIRED', 'Expirada'),
    )
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='PENDING',
        verbose_name="Estado"
    )
    
    expires_at = models.DateTimeField(verbose_name="Expira en")
    accepted_at = models.DateTimeField(null=True, blank=True, verbose_name="Aceptada en")
    
    class Meta:
        verbose_name = "Invitación a organización"
        verbose_name_plural = "Invitaciones a organizaciones"
    
    def __str__(self):
        return f"Invitación a {self.email} para {self.organization.name}"
    
    @property
    def is_expired(self):
        """Verifica si la invitación ha expirado"""
        from django.utils import timezone
        return self.expires_at < timezone.now()
