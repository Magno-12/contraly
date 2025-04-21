from rest_framework import status, permissions, filters
from rest_framework.viewsets import GenericViewSet
from rest_framework.response import Response
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q
from django.utils import timezone

from apps.contracts.models import Contract, ContractParty, ContractDocument, ContractStatus, ContractRevision
from apps.contracts.serializers import (
    ContractSerializer, ContractListSerializer, ContractDetailSerializer, ContractCreateSerializer
)
from apps.core.utils import create_audit_log, get_client_ip
from apps.core.permission import IsAdministrator


class ContractViewSet(GenericViewSet):
    """
    API endpoint para gestionar contratos
    """
    queryset = Contract.objects.filter(is_deleted=False)
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['contract_type', 'is_active', 'department', 'supervisor', 'tenant']
    search_fields = ['contract_number', 'title', 'description', 'reference_number']
    ordering_fields = ['contract_number', 'title', 'start_date', 'end_date', 'value', 'created_at']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return ContractListSerializer
        elif self.action == 'retrieve':
            return ContractDetailSerializer
        elif self.action == 'create':
            return ContractCreateSerializer
        return ContractSerializer
    
    def get_permissions(self):
        """
        Instantiates and returns the list of permissions that this view requires.
        """
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [permissions.IsAuthenticated, IsAdministrator]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        """
        Filtrar contratos según permisos del usuario
        """
        queryset = super().get_queryset()
        user = self.request.user
        
        # Superusers ven todos los contratos
        if user.is_superuser:
            return queryset
            
        # Administradores ven los contratos de su organización
        if hasattr(user, 'user_roles') and user.user_roles.filter(
            role__name='Administrator',
            is_active=True,
            is_deleted=False
        ).exists():
            if user.tenant:
                return queryset.filter(tenant=user.tenant)
            
        # Supervisores ven contratos donde son supervisores o participantes
        supervisor_contracts = queryset.filter(supervisor=user)
        
        # Participantes ven contratos donde están involucrados
        participant_contracts = queryset.filter(
            parties__user=user,
            parties__is_active=True,
            parties__is_deleted=False
        )
        
        # Combinar y eliminar duplicados
        return (supervisor_contracts | participant_contracts).distinct()
    
    def list(self, request):
        """
        Listar contratos con filtros
        """
        queryset = self.filter_queryset(self.get_queryset())
        
        # Filtro por estado actual
        status = request.query_params.get('status', None)
        if status:
            contract_ids = ContractStatus.objects.filter(
                status=status,
                is_active=True,
                is_deleted=False,
                end_date__isnull=True  # Es el estado actual
            ).values_list('contract_id', flat=True)
            queryset = queryset.filter(id__in=contract_ids)
        
        # Filtro por fecha
        start_after = request.query_params.get('start_after', None)
        start_before = request.query_params.get('start_before', None)
        end_after = request.query_params.get('end_after', None)
        end_before = request.query_params.get('end_before', None)
        
        if start_after:
            queryset = queryset.filter(start_date__gte=start_after)
        if start_before:
            queryset = queryset.filter(start_date__lte=start_before)
        if end_after:
            queryset = queryset.filter(end_date__gte=end_after)
        if end_before:
            queryset = queryset.filter(end_date__lte=end_before)
        
        # Filtro por término de búsqueda general
        search = request.query_params.get('q', None)
        if search:
            queryset = queryset.filter(
                Q(contract_number__icontains=search) |
                Q(title__icontains=search) |
                Q(description__icontains=search) |
                Q(reference_number__icontains=search)
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
        Obtener detalle de un contrato
        """
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        
        # Registrar visualización
        create_audit_log(
            user=request.user,
            action='VIEW',
            model_name='Contract',
            instance_id=instance.id,
            description=f"Visualización de contrato {instance.contract_number}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            tenant=request.user.tenant
        )
        
        return Response(serializer.data)
    
    def create(self, request):
        """
        Crear un nuevo contrato
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Establecer tenant si no se proporciona
        if 'tenant' not in serializer.validated_data and request.user.tenant:
            serializer.validated_data['tenant'] = request.user.tenant
        
        # Crear contrato
        contract = serializer.save(
            created_by=request.user,
            updated_by=request.user
        )
        
        # Registrar creación
        create_audit_log(
            user=request.user,
            action='CREATE',
            model_name='Contract',
            instance_id=contract.id,
            description=f"Creación de contrato {contract.contract_number}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            data=request.data,
            tenant=request.user.tenant
        )
        
        # Crear revisión inicial
        ContractRevision.objects.create(
            contract=contract,
            revision_type='CREATION',
            description="Creación inicial del contrato",
            new_data=serializer.data,
            created_by=request.user,
            updated_by=request.user,
            tenant=contract.tenant
        )
        
        return Response(
            ContractDetailSerializer(contract).data,
            status=status.HTTP_201_CREATED
        )
    
    def update(self, request, pk=None):
        """
        Actualizar un contrato existente
        """
        instance = self.get_object()
        
        # Guardar datos anteriores para la revisión
        previous_data = ContractSerializer(instance).data
        
        serializer = self.get_serializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        contract = serializer.save(updated_by=request.user)
        
        # Registrar actualización
        create_audit_log(
            user=request.user,
            action='UPDATE',
            model_name='Contract',
            instance_id=contract.id,
            description=f"Actualización de contrato {contract.contract_number}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            data=request.data,
            tenant=request.user.tenant
        )
        
        # Crear revisión
        ContractRevision.objects.create(
            contract=contract,
            revision_type='UPDATE',
            description="Actualización de información del contrato",
            previous_data=previous_data,
            new_data=serializer.data,
            created_by=request.user,
            updated_by=request.user,
            tenant=contract.tenant
        )
        
        return Response(ContractDetailSerializer(contract).data)
    
    def partial_update(self, request, pk=None):
        """
        Actualizar parcialmente un contrato
        """
        instance = self.get_object()
        
        # Guardar datos anteriores para la revisión
        previous_data = ContractSerializer(instance).data
        
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        contract = serializer.save(updated_by=request.user)
        
        # Registrar actualización
        create_audit_log(
            user=request.user,
            action='UPDATE',
            model_name='Contract',
            instance_id=contract.id,
            description=f"Actualización parcial de contrato {contract.contract_number}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            data=request.data,
            tenant=request.user.tenant
        )
        
        # Crear revisión
        ContractRevision.objects.create(
            contract=contract,
            revision_type='UPDATE',
            description="Actualización parcial de información del contrato",
            previous_data=previous_data,
            new_data=ContractSerializer(contract).data,
            created_by=request.user,
            updated_by=request.user,
            tenant=contract.tenant
        )
        
        return Response(ContractDetailSerializer(contract).data)
    
    def destroy(self, request, pk=None):
        """
        Eliminar (soft delete) un contrato
        """
        instance = self.get_object()
        
        # Soft delete
        instance.is_active = False
        instance.is_deleted = True
        instance.updated_by = request.user
        instance.save()
        
        # Registrar eliminación
        create_audit_log(
            user=request.user,
            action='DELETE',
            model_name='Contract',
            instance_id=instance.id,
            description=f"Eliminación de contrato {instance.contract_number}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            tenant=request.user.tenant
        )
        
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    @action(detail=True, methods=['get'])
    def parties(self, request, pk=None):
        """
        Obtener partes involucradas en un contrato
        """
        contract = self.get_object()
        from apps.contracts.serializers import ContractPartySerializer
        
        parties = ContractParty.objects.filter(
            contract=contract,
            is_active=True,
            is_deleted=False
        )
        
        serializer = ContractPartySerializer(parties, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def documents(self, request, pk=None):
        """
        Obtener documentos asociados a un contrato
        """
        contract = self.get_object()
        from apps.contracts.serializers import ContractDocumentSerializer
        
        documents = ContractDocument.objects.filter(
            contract=contract,
            is_active=True,
            is_deleted=False
        )
        
        # Filtrar por tipo de documento
        doc_type = request.query_params.get('type', None)
        if doc_type:
            documents = documents.filter(document_type=doc_type)
        
        serializer = ContractDocumentSerializer(documents, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        """
        Obtener historial de revisiones de un contrato
        """
        contract = self.get_object()
        from apps.contracts.serializers import ContractRevisionSerializer
        
        revisions = ContractRevision.objects.filter(
            contract=contract,
            is_active=True,
            is_deleted=False
        ).order_by('-revision_date')
        
        serializer = ContractRevisionSerializer(revisions, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def status_history(self, request, pk=None):
        """
        Obtener historial de estados de un contrato
        """
        contract = self.get_object()
        from apps.contracts.serializers import ContractStatusSerializer
        
        statuses = ContractStatus.objects.filter(
            contract=contract,
            is_active=True,
            is_deleted=False
        ).order_by('-start_date')
        
        serializer = ContractStatusSerializer(statuses, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def change_status(self, request, pk=None):
        """
        Cambiar el estado de un contrato
        """
        contract = self.get_object()
        from apps.contracts.serializers import ContractStatusSerializer
        
        # Validar datos del nuevo estado
        serializer = ContractStatusSerializer(data={
            'contract': contract.id,
            'status': request.data.get('status'),
            'comments': request.data.get('comments', ''),
            'tenant': contract.tenant.id if contract.tenant else None
        })
        serializer.is_valid(raise_exception=True)
        serializer.context['request'] = request
        
        # Crear nuevo estado
        status_obj = serializer.save(
            created_by=request.user,
            updated_by=request.user,
            changed_by=request.user
        )
        
        # Registrar cambio de estado
        create_audit_log(
            user=request.user,
            action='UPDATE',
            model_name='ContractStatus',
            instance_id=status_obj.id,
            description=f"Cambio de estado de contrato {contract.contract_number} a {status_obj.get_status_display()}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            tenant=request.user.tenant
        )
        
        # Crear revisión
        ContractRevision.objects.create(
            contract=contract,
            revision_type='APPROVAL' if status_obj.status in ['APPROVED', 'SIGNED'] else 'UPDATE',
            description=f"Cambio de estado a '{status_obj.get_status_display()}'",
            previous_data={'status': contract.current_status.status if contract.current_status else None},
            new_data={'status': status_obj.status},
            created_by=request.user,
            updated_by=request.user,
            tenant=contract.tenant
        )
        
        return Response(ContractStatusSerializer(status_obj).data)
