from django.utils import timezone
from rest_framework import status, permissions
from rest_framework.viewsets import GenericViewSet
from rest_framework.response import Response
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.db.models import Q

from apps.organizations.models.organizations import (
    Organization, Domain, OrganizationMember, 
    OrganizationSettings, OrganizationInvitation
)
from apps.organizations.serializers.organizations_serializer import (
    OrganizationListSerializer, OrganizationDetailSerializer,
    OrganizationCreateSerializer, DomainSerializer,
    OrganizationMemberSerializer, OrganizationSettingsSerializer,
    OrganizationInvitationSerializer, InvitationAcceptSerializer
)
from apps.core.utils import get_client_ip, create_audit_log
from apps.user.models import User


class OrganizationViewSet(GenericViewSet):
    """
    API endpoint para gestionar organizaciones
    """
    queryset = Organization.objects.filter(is_deleted=False)
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'subdomain', 'email', 'city', 'state']
    filterset_fields = ['organization_type', 'is_active', 'on_trial']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']
    
    def get_serializer_class(self):
        if self.action == 'create':
            return OrganizationCreateSerializer
        elif self.action in ['retrieve', 'update', 'partial_update']:
            return OrganizationDetailSerializer
        return OrganizationListSerializer
    
    def get_permissions(self):
        """
        Solo los superadmins pueden crear/modificar organizaciones
        Los miembros pueden ver su propia organización
        """
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [permissions.IsAdminUser()]
        return [permissions.IsAuthenticated()]
    
    def get_queryset(self):
        """
        Filtrar organizaciones según permisos
        """
        queryset = super().get_queryset()
        user = self.request.user
        
        # Superadmins ven todas las organizaciones
        if user.is_superuser:
            return queryset
            
        # Usuarios normales solo ven las organizaciones a las que pertenecen
        # como miembros activos
        member_orgs = OrganizationMember.objects.filter(
            user=user,
            is_active=True,
            is_deleted=False
        ).values_list('organization_id', flat=True)
        
        return queryset.filter(id__in=member_orgs)
    
    def list(self, request):
        """
        Listar organizaciones
        """
        queryset = self.filter_queryset(self.get_queryset())
        
        # Filtro adicional por búsqueda general
        search = request.query_params.get('q', None)
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(subdomain__icontains=search) |
                Q(email__icontains=search) |
                Q(city__icontains=search) |
                Q(state__icontains=search) |
                Q(country__icontains=search)
            )
        
        # Paginación
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    def retrieve(self, request, pk=None):
        """
        Obtener detalles de una organización
        """
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
    
    def create(self, request):
        """
        Crear una nueva organización
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Incluir el usuario actual como creador
        serializer.context['request'] = request
        organization = serializer.save(created_by=request.user, updated_by=request.user)
        
        # Registrar evento
        create_audit_log(
            user=request.user,
            action='CREATE',
            model_name='Organization',
            instance_id=organization.id,
            description=f"Creación de organización: {organization.name}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        # Devolver datos completos
        return Response(
            OrganizationDetailSerializer(organization).data,
            status=status.HTTP_201_CREATED
        )
    
    def update(self, request, pk=None):
        """
        Actualizar una organización
        """
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        organization = serializer.save(updated_by=request.user)
        
        # Registrar evento
        create_audit_log(
            user=request.user,
            action='UPDATE',
            model_name='Organization',
            instance_id=organization.id,
            description=f"Actualización de organización: {organization.name}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        return Response(serializer.data)
    
    def partial_update(self, request, pk=None):
        """
        Actualizar parcialmente una organización
        """
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        organization = serializer.save(updated_by=request.user)
        
        # Registrar evento
        create_audit_log(
            user=request.user,
            action='UPDATE',
            model_name='Organization',
            instance_id=organization.id,
            description=f"Actualización parcial de organización: {organization.name}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        return Response(serializer.data)
    
    def destroy(self, request, pk=None):
        """
        Eliminar (desactivar) una organización
        """
        instance = self.get_object()
        
        # Soft delete
        instance.is_active = False
        instance.is_deleted = True
        instance.updated_by = request.user
        instance.save()
        
        # Registrar evento
        create_audit_log(
            user=request.user,
            action='DELETE',
            model_name='Organization',
            instance_id=instance.id,
            description=f"Eliminación de organización: {instance.name}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    @action(detail=True, methods=['get'])
    def members(self, request, pk=None):
        """
        Obtener miembros de una organización
        """
        organization = self.get_object()
        
        # Filtrar miembros activos
        members = OrganizationMember.objects.filter(
            organization=organization,
            is_active=True,
            is_deleted=False
        )
        
        # Aplicar filtro por rol si existe
        role = request.query_params.get('role', None)
        if role:
            members = members.filter(role=role)
        
        serializer = OrganizationMemberSerializer(members, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def settings(self, request, pk=None):
        """
        Obtener configuración de una organización
        """
        organization = self.get_object()
        
        try:
            settings = OrganizationSettings.objects.get(organization=organization)
        except OrganizationSettings.DoesNotExist:
            # Crear configuración por defecto si no existe
            settings = OrganizationSettings.objects.create(
                organization=organization,
                created_by=request.user
            )
        
        serializer = OrganizationSettingsSerializer(settings)
        return Response(serializer.data)
    
    @action(detail=True, methods=['put', 'patch'])
    def update_settings(self, request, pk=None):
        """
        Actualizar configuración de una organización
        """
        organization = self.get_object()
        
        try:
            settings = OrganizationSettings.objects.get(organization=organization)
        except OrganizationSettings.DoesNotExist:
            settings = OrganizationSettings.objects.create(
                organization=organization,
                created_by=request.user
            )
        
        serializer = OrganizationSettingsSerializer(
            settings, 
            data=request.data,
            partial=True
        )
        serializer.is_valid(raise_exception=True)
        settings = serializer.save(updated_by=request.user)
        
        # Registrar evento
        create_audit_log(
            user=request.user,
            action='UPDATE',
            model_name='OrganizationSettings',
            instance_id=settings.id,
            description=f"Actualización de configuración para: {organization.name}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def domains(self, request, pk=None):
        """
        Obtener dominios de una organización
        """
        organization = self.get_object()
        
        domains = Domain.objects.filter(
            tenant=organization,
            is_active=True,
            is_deleted=False
        )
        
        serializer = DomainSerializer(domains, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def add_domain(self, request, pk=None):
        """
        Añadir un nuevo dominio a una organización
        """
        organization = self.get_object()
        
        serializer = DomainSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Verificar dominio único
        domain_name = serializer.validated_data['domain']
        if Domain.objects.filter(domain=domain_name).exists():
            return Response(
                {"detail": f"El dominio {domain_name} ya está en uso."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Crear dominio
        domain = Domain.objects.create(
            domain=domain_name,
            tenant=organization,
            is_primary=serializer.validated_data.get('is_primary', False),
            is_active=True,
            created_by=request.user,
            updated_by=request.user
        )
        
        # Si este es primario, quitar marca de primario de otros
        if domain.is_primary:
            Domain.objects.filter(
                tenant=organization,
                is_primary=True
            ).exclude(id=domain.id).update(
                is_primary=False,
                updated_by=request.user
            )
        
        # Registrar evento
        create_audit_log(
            user=request.user,
            action='CREATE',
            model_name='Domain',
            instance_id=domain.id,
            description=f"Nuevo dominio {domain.domain} para: {organization.name}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        return Response(
            DomainSerializer(domain).data,
            status=status.HTTP_201_CREATED
        )


class OrganizationMemberViewSet(GenericViewSet):
    """
    API endpoint para gestionar miembros de organizaciones
    """
    queryset = OrganizationMember.objects.filter(is_deleted=False)
    serializer_class = OrganizationMemberSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['organization', 'role', 'is_active']
    search_fields = ['user__email', 'user__first_name', 'user__last_name', 'position', 'department']
    ordering_fields = ['user__email', 'role', 'created_at']
    ordering = ['user__email']
    
    def get_permissions(self):
        """
        Solo admins de organización pueden modificar miembros
        """
        # TODO: Implementar permisos por rol de organización
        return [permissions.IsAuthenticated()]
    
    def get_queryset(self):
        """
        Filtrar miembros según permisos
        """
        queryset = super().get_queryset()
        user = self.request.user
        
        # Superadmins ven todos los miembros
        if user.is_superuser:
            return queryset
            
        # Ver solo miembros de organizaciones a las que pertenezco como admin
        admin_orgs = OrganizationMember.objects.filter(
            user=user,
            role='ADMIN',
            is_active=True,
            is_deleted=False
        ).values_list('organization_id', flat=True)
        
        # Si soy admin, ver miembros de mis organizaciones
        if admin_orgs.exists():
            return queryset.filter(organization_id__in=admin_orgs)
        
        # Si no soy admin, solo verme a mí mismo
        return queryset.filter(user=user)
    
    def list(self, request):
        """
        Listar miembros
        """
        queryset = self.filter_queryset(self.get_queryset())
        
        # Paginación
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    def retrieve(self, request, pk=None):
        """
        Obtener detalle de un miembro
        """
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
    
    def create(self, request):
        """
        Añadir un miembro a una organización
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Verificar que no exista ya
        user_id = serializer.validated_data['user'].id
        organization_id = serializer.validated_data['organization'].id
        
        if OrganizationMember.objects.filter(
            user_id=user_id,
            organization_id=organization_id,
            is_deleted=False
        ).exists():
            return Response(
                {"detail": "Este usuario ya es miembro de esta organización."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Crear miembro
        member = serializer.save(
            created_by=request.user,
            updated_by=request.user
        )
        
        # Registrar evento
        create_audit_log(
            user=request.user,
            action='CREATE',
            model_name='OrganizationMember',
            instance_id=member.id,
            description=f"Nuevo miembro {member.user.email} con rol {member.get_role_display()} en: {member.organization.name}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        return Response(
            self.get_serializer(member).data,
            status=status.HTTP_201_CREATED
        )
    
    def update(self, request, pk=None):
        """
        Actualizar un miembro
        """
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        member = serializer.save(updated_by=request.user)
        
        # Registrar evento
        create_audit_log(
            user=request.user,
            action='UPDATE',
            model_name='OrganizationMember',
            instance_id=member.id,
            description=f"Actualización de miembro {member.user.email} en: {member.organization.name}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        return Response(serializer.data)
    
    def partial_update(self, request, pk=None):
        """
        Actualizar parcialmente un miembro
        """
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        member = serializer.save(updated_by=request.user)
        
        # Registrar evento
        create_audit_log(
            user=request.user,
            action='UPDATE',
            model_name='OrganizationMember',
            instance_id=member.id,
            description=f"Actualización parcial de miembro {member.user.email} en: {member.organization.name}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        return Response(serializer.data)
    
    def destroy(self, request, pk=None):
        """
        Eliminar un miembro de una organización
        """
        instance = self.get_object()
        
        # Soft delete
        instance.is_active = False
        instance.is_deleted = True
        instance.updated_by = request.user
        instance.save()
        
        # Registrar evento
        create_audit_log(
            user=request.user,
            action='DELETE',
            model_name='OrganizationMember',
            instance_id=instance.id,
            description=f"Eliminación de miembro {instance.user.email} de: {instance.organization.name}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        return Response(status=status.HTTP_204_NO_CONTENT)


class OrganizationInvitationViewSet(GenericViewSet):
    """
    API endpoint para gestionar invitaciones a organizaciones
    """
    queryset = OrganizationInvitation.objects.all()
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['organization', 'status', 'role']
    search_fields = ['email']
    ordering_fields = ['created_at', 'expires_at']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        if self.action == 'accept':
            return InvitationAcceptSerializer
        return OrganizationInvitationSerializer
    
    def get_permissions(self):
        """
        Solo admins de organización pueden gestionar invitaciones
        Aceptar invitación es público
        """
        if self.action == 'accept':
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]
    
    def get_queryset(self):
        """
        Filtrar invitaciones según permisos
        """
        queryset = super().get_queryset()
        user = self.request.user
        
        # Para accept podemos estar sin autenticación
        if self.action == 'accept':
            return queryset
        
        # Superadmins ven todas las invitaciones
        if user.is_superuser:
            return queryset
            
        # Ver solo invitaciones de organizaciones a las que pertenezco como admin
        admin_orgs = OrganizationMember.objects.filter(
            user=user,
            role='ADMIN',
            is_active=True,
            is_deleted=False
        ).values_list('organization_id', flat=True)
        
        # Si soy admin, ver invitaciones de mis organizaciones
        if admin_orgs.exists():
            return queryset.filter(organization_id__in=admin_orgs)
        
        # Si no soy admin, ver invitaciones a mi email
        return queryset.filter(email=user.email)
    
    def list(self, request):
        """
        Listar invitaciones
        """
        queryset = self.filter_queryset(self.get_queryset())
        
        # Paginación
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    def retrieve(self, request, pk=None):
        """
        Obtener detalle de una invitación
        """
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
    
    def create(self, request):
        """
        Crear una nueva invitación
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Comprobar si ya existe una invitación pendiente
        email = serializer.validated_data['email']
        organization_id = serializer.validated_data['organization'].id
        
        existing = OrganizationInvitation.objects.filter(
            email=email,
            organization_id=organization_id,
            status='PENDING'
        ).first()
        
        if existing:
            # Actualizar invitación existente
            for key, value in serializer.validated_data.items():
                setattr(existing, key, value)
            
            existing.token = None  # Para generar un nuevo token
            existing.updated_by = request.user
            invitation = serializer.save(instance=existing)
        else:
            # Crear nueva invitación
            invitation = serializer.save(
                created_by=request.user,
                updated_by=request.user
            )
        
        # Enviar email
        self._send_invitation_email(invitation)
        
        # Registrar evento
        create_audit_log(
            user=request.user,
            action='CREATE',
            model_name='OrganizationInvitation',
            instance_id=invitation.id,
            description=f"Invitación enviada a {invitation.email} para: {invitation.organization.name}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        return Response(
            self.get_serializer(invitation).data,
            status=status.HTTP_201_CREATED
        )
    
    def update(self, request, pk=None):
        """
        Actualizar una invitación
        """
        instance = self.get_object()
        
        # Solo se pueden actualizar invitaciones pendientes
        if instance.status != 'PENDING':
            return Response(
                {"detail": f"Esta invitación ya ha sido {instance.get_status_display().lower()} y no puede modificarse."},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        serializer = self.get_serializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        invitation = serializer.save(updated_by=request.user)
        
        # Registrar evento
        create_audit_log(
            user=request.user,
            action='UPDATE',
            model_name='OrganizationInvitation',
            instance_id=invitation.id,
            description=f"Actualización de invitación a {invitation.email} para: {invitation.organization.name}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        return Response(serializer.data)
    
    def destroy(self, request, pk=None):
        """
        Cancelar una invitación
        """
        instance = self.get_object()
        
        # Solo se pueden cancelar invitaciones pendientes
        if instance.status != 'PENDING':
            return Response(
                {"detail": f"Esta invitación ya ha sido {instance.get_status_display().lower()} y no puede cancelarse."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Cambiar estado a cancelada
        instance.status = 'REJECTED'
        instance.updated_by = request.user
        instance.save()
        
        # Registrar evento
        create_audit_log(
            user=request.user,
            action='DELETE',
            model_name='OrganizationInvitation',
            instance_id=instance.id,
            description=f"Cancelación de invitación a {instance.email} para: {instance.organization.name}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    @action(detail=False, methods=['post'], permission_classes=[permissions.AllowAny])
    def accept(self, request):
        """
        Aceptar una invitación
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        invitation = serializer.context['invitation']
        
        # Buscar usuario existente o crear uno nuevo
        user = None
        try:
            user = User.objects.get(email=invitation.email)
        except User.DoesNotExist:
            # El usuario debería registrarse primero
            return Response(
                {"detail": "Debes registrarte antes de aceptar la invitación."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Crear miembro de organización
        member, created = OrganizationMember.objects.get_or_create(
            user=user,
            organization=invitation.organization,
            defaults={
                'role': invitation.role,
                'is_active': True,
                'created_by': user,
                'updated_by': user
            }
        )
        
        if not created:
            # Actualizar miembro existente
            member.role = invitation.role
            member.is_active = True
            member.is_deleted = False
            member.updated_by = user
            member.save()
        
        # Actualizar invitación
        invitation.status = 'ACCEPTED'
        invitation.accepted_at = timezone.now()
        invitation.save()
        
        # Registrar evento
        create_audit_log(
            user=user,
            action='UPDATE',
            model_name='OrganizationInvitation',
            instance_id=invitation.id,
            description=f"Invitación aceptada por {user.email} para: {invitation.organization.name}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        return Response({
            "detail": f"Has sido añadido a la organización {invitation.organization.name} con el rol de {invitation.get_role_display()}.",
            "organization": {
                "id": invitation.organization.id,
                "name": invitation.organization.name,
                "subdomain": invitation.organization.subdomain
            },
            "role": invitation.role,
            "role_display": invitation.get_role_display()
        })
    
    @action(detail=True, methods=['post'])
    def resend(self, request, pk=None):
        """
        Reenviar una invitación
        """
        invitation = self.get_object()
        
        # Solo se pueden reenviar invitaciones pendientes
        if invitation.status != 'PENDING':
            return Response(
                {"detail": f"Esta invitación ya ha sido {invitation.get_status_display().lower()} y no puede reenviarse."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Generar nuevo token y actualizar fechas
        import secrets
        from django.utils import timezone
        import datetime
        
        invitation.token = secrets.token_urlsafe(32)
        invitation.expires_at = timezone.now() + datetime.timedelta(days=7)
        invitation.updated_by = request.user
        invitation.save()
        
        # Enviar email
        self._send_invitation_email(invitation)
        
        # Registrar evento
        create_audit_log(
            user=request.user,
            action='UPDATE',
            model_name='OrganizationInvitation',
            instance_id=invitation.id,
            description=f"Reenvío de invitación a {invitation.email} para: {invitation.organization.name}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        return Response({
            "detail": f"Invitación reenviada a {invitation.email}."
        })
    
    def _send_invitation_email(self, invitation):
        """
        Enviar email de invitación
        """
        subject = f"Invitación a unirse a {invitation.organization.name}"
        
        # Crear enlace de aceptación
        invitation_url = f"{settings.FRONTEND_URL}/invitations/accept?token={invitation.token}"
        
        context = {
            'organization_name': invitation.organization.name,
            'invitation_url': invitation_url,
            'role': invitation.get_role_display(),
            'expires_at': invitation.expires_at,
        }
        
        # Preparar email
        html_message = render_to_string('organizations/invitation_email.html', context)
        plain_message = render_to_string('organizations/invitation_email.txt', context)
        
        # Enviar email
        from_email = settings.DEFAULT_FROM_EMAIL
        recipient_list = [invitation.email]
        
        try:
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=from_email,
                recipient_list=recipient_list,
                html_message=html_message,
                fail_silently=False
            )
            return True
        except Exception as e:
            # Loguear el error pero no fallar el proceso
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error al enviar email de invitación: {str(e)}")
            return False
