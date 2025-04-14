from rest_framework import serializers
from apps.organizations.models.organizations import (
    Organization, Domain, OrganizationMember, 
    OrganizationSettings, OrganizationInvitation
)


class DomainSerializer(serializers.ModelSerializer):
    """
    Serializer para dominios de organizaciones
    """
    class Meta:
        model = Domain
        fields = ['id', 'domain', 'is_primary', 'is_active', 'created_at']
        read_only_fields = ['id', 'created_at']


class OrganizationListSerializer(serializers.ModelSerializer):
    """
    Serializer simplificado para listar organizaciones
    """
    domains = serializers.SerializerMethodField()
    member_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Organization
        fields = ['id', 'name', 'subdomain', 'logo', 'city', 'state', 
                 'organization_type', 'is_active', 'domains', 'member_count']
        read_only_fields = ['id', 'domains', 'member_count']
    
    def get_domains(self, obj):
        domains = Domain.objects.filter(tenant=obj, is_active=True, is_deleted=False)
        return DomainSerializer(domains, many=True).data
    
    def get_member_count(self, obj):
        return OrganizationMember.objects.filter(
            organization=obj,
            is_active=True,
            is_deleted=False
        ).count()


class OrganizationDetailSerializer(serializers.ModelSerializer):
    """
    Serializer detallado para organizaciones
    """
    domains = serializers.SerializerMethodField()
    members = serializers.SerializerMethodField()
    
    class Meta:
        model = Organization
        fields = [
            'id', 'name', 'subdomain', 'description', 'logo', 
            'email', 'phone', 'address', 'city', 'state', 'country',
            'zip_code', 'tax_id', 'organization_type',
            'primary_color', 'secondary_color',
            'max_users', 'max_storage_gb', 'paid_until', 'on_trial',
            'trial_ends', 'is_active', 'created_at', 'updated_at',
            'domains', 'members'
        ]
        read_only_fields = [
            'id', 'created_at', 'updated_at', 'domains', 'members'
        ]
    
    def get_domains(self, obj):
        domains = Domain.objects.filter(tenant=obj, is_active=True, is_deleted=False)
        return DomainSerializer(domains, many=True).data
    
    def get_members(self, obj):
        members = OrganizationMember.objects.filter(
            organization=obj,
            is_active=True,
            is_deleted=False
        )
        return OrganizationMemberSerializer(members, many=True).data


class OrganizationCreateSerializer(serializers.ModelSerializer):
    """
    Serializer para crear nuevas organizaciones
    """
    domain = serializers.CharField(
        required=True, 
        write_only=True,
        help_text="Dominio principal para esta organización (ej: entidad.contraly.com)"
    )
    
    class Meta:
        model = Organization
        fields = [
            'name', 'subdomain', 'description', 'organization_type',
            'email', 'phone', 'city', 'state', 'country', 'domain'
        ]
        
    def validate_subdomain(self, value):
        """
        Validación para asegurar que el subdominio sea único y válido
        """
        # Convertir a minúscula y eliminar espacios
        value = value.lower().strip()
        
        # Verificar que solo contenga caracteres alfanuméricos y guiones
        if not all(c.isalnum() or c == '-' for c in value):
            raise serializers.ValidationError(
                "El subdominio solo puede contener letras, números y guiones."
            )
        
        # Verificar que no sea una palabra reservada
        reserved_words = ['www', 'api', 'admin', 'app', 'dev', 'stage', 'test', 'demo']
        if value in reserved_words:
            raise serializers.ValidationError(
                f"'{value}' es una palabra reservada y no puede usarse como subdominio."
            )
        
        # Verificar que no exista ya
        if Organization.objects.filter(subdomain=value).exists():
            raise serializers.ValidationError(
                f"El subdominio '{value}' ya está en uso."
            )
            
        return value
    
    def validate_domain(self, value):
        """
        Validación del dominio
        """
        # Convertir a minúscula y eliminar espacios
        value = value.lower().strip()
        
        # Verificar que no exista ya
        if Domain.objects.filter(domain=value).exists():
            raise serializers.ValidationError(
                f"El dominio '{value}' ya está en uso."
            )
            
        return value
    
    def create(self, validated_data):
        domain_data = validated_data.pop('domain')
        
        # Establecer schema_name igual al subdominio
        if 'schema_name' not in validated_data:
            validated_data['schema_name'] = validated_data['subdomain']
        
        # Crear la organización (tenant)
        organization = Organization.objects.create(**validated_data)
        
        # Crear el dominio asociado
        Domain.objects.create(
            domain=domain_data,
            tenant=organization,
            is_primary=True,
            is_active=True,
            created_by=self.context.get('request').user if 'request' in self.context else None
        )
        
        # Crear configuración por defecto
        OrganizationSettings.objects.create(
            organization=organization,
            created_by=self.context.get('request').user if 'request' in self.context else None
        )
        
        return organization


class OrganizationMemberSerializer(serializers.ModelSerializer):
    """
    Serializer para miembros de organizaciones
    """
    user_details = serializers.SerializerMethodField()
    
    class Meta:
        model = OrganizationMember
        fields = [
            'id', 'organization', 'user', 'role', 
            'position', 'department', 'start_date', 'end_date',
            'is_active', 'created_at', 'user_details'
        ]
        read_only_fields = ['id', 'created_at', 'user_details']
    
    def get_user_details(self, obj):
        return {
            'id': obj.user.id,
            'email': obj.user.email,
            'first_name': obj.user.first_name,
            'last_name': obj.user.last_name,
            'full_name': f"{obj.user.first_name} {obj.user.last_name}",
            'is_active': obj.user.is_active
        }


class OrganizationSettingsSerializer(serializers.ModelSerializer):
    """
    Serializer para configuraciones de organizaciones
    """
    class Meta:
        model = OrganizationSettings
        fields = [
            'id', 'organization', 'require_double_approval', 'allow_self_approval',
            'email_notifications', 'sms_notifications', 
            'force_password_change', 'password_expiry_days', 'session_timeout_minutes',
            'fiscal_year_start', 'default_currency'
        ]
        read_only_fields = ['id']


class OrganizationInvitationSerializer(serializers.ModelSerializer):
    """
    Serializer para invitaciones a organizaciones
    """
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    role_display = serializers.CharField(source='get_role_display', read_only=True)
    organization_name = serializers.CharField(source='organization.name', read_only=True)
    
    class Meta:
        model = OrganizationInvitation
        fields = [
            'id', 'organization', 'organization_name', 'email', 
            'role', 'role_display', 'status', 'status_display',
            'expires_at', 'accepted_at', 'created_at'
        ]
        read_only_fields = [
            'id', 'token', 'status_display', 'role_display', 
            'organization_name', 'accepted_at', 'created_at'
        ]
    
    def create(self, validated_data):
        # Generar token y establecer fecha de expiración
        import secrets
        import datetime
        from django.utils import timezone
        
        validated_data['token'] = secrets.token_urlsafe(32)
        if 'expires_at' not in validated_data:
            validated_data['expires_at'] = timezone.now() + datetime.timedelta(days=7)
            
        return super().create(validated_data)


class InvitationAcceptSerializer(serializers.Serializer):
    """
    Serializer para aceptar invitaciones
    """
    token = serializers.CharField(required=True)
    
    def validate_token(self, value):
        try:
            invitation = OrganizationInvitation.objects.get(token=value)
            
            # Verificar estado y validez
            if invitation.status != 'PENDING':
                raise serializers.ValidationError(
                    f"Esta invitación ya ha sido {invitation.get_status_display().lower()}."
                )
                
            if invitation.is_expired:
                invitation.status = 'EXPIRED'
                invitation.save()
                raise serializers.ValidationError("Esta invitación ha expirado.")
                
            # Guardar en el contexto para usarla después
            self.context['invitation'] = invitation
                
        except OrganizationInvitation.DoesNotExist:
            raise serializers.ValidationError("Token de invitación inválido.")
            
        return value
