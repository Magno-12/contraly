from rest_framework import status, permissions, filters
from rest_framework.viewsets import GenericViewSet
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q

from apps.contracts.models import ContractRevision, Contract
from apps.contracts.serializers import ContractRevisionSerializer
from apps.core.utils import create_audit_log, get_client_ip


class ContractRevisionViewSet(GenericViewSet):
    """
    API endpoint para gestionar revisiones de contratos
    """
    queryset = ContractRevision.objects.filter(is_deleted=False)
    serializer_class = ContractRevisionSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['contract', 'revision_type', 'tenant']
    search_fields = ['description']
    ordering_fields = ['revision_date', 'revision_type']
    ordering = ['-revision_date']
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """
        Filtrar revisiones según permisos del usuario
        """
        queryset = super().get_queryset()
        user = self.request.user
        
        # Superusers ven todas las revisiones
        if user.is_superuser:
            return queryset
        
        # Restricciones para usuarios normales
        if user.tenant:
            # Ver revisiones de su organización
            return queryset.filter(tenant=user.tenant)
        
        # Ver solo revisiones de contratos donde el usuario está involucrado
        user_contracts = Contract.objects.filter(
            Q(supervisor=user) |
            Q(parties__user=user, parties__is_active=True, parties__is_deleted=False)
        ).distinct()
        
        return queryset.filter(contract__in=user_contracts)
    
    def list(self, request):
        """
        Listar revisiones de contratos
        """
        queryset = self.filter_queryset(self.get_queryset())
        
        # Filtros adicionales
        contract_id = request.query_params.get('contract_id', None)
        if contract_id:
            queryset = queryset.filter(contract_id=contract_id)
            
        # Paginación
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
            
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    def retrieve(self, request, pk=None):
        """
        Obtener detalle de una revisión
        """
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
    
    def create(self, request):
        """
        Crear una nueva revisión de contrato
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Establecer tenant si no se proporciona
        if 'tenant' not in serializer.validated_data:
            contract = serializer.validated_data.get('contract')
            if contract and contract.tenant:
                serializer.validated_data['tenant'] = contract.tenant
            elif request.user.tenant:
                serializer.validated_data['tenant'] = request.user.tenant
        
        # Crear revisión
        revision = serializer.save(
            created_by=request.user,
            updated_by=request.user
        )
        
        # Registrar creación
        create_audit_log(
            user=request.user,
            action='CREATE',
            model_name='ContractRevision',
            instance_id=revision.id,
            description=f"Creación de revisión de contrato: {revision.description}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            tenant=request.user.tenant
        )
        
        return Response(
            self.get_serializer(revision).data,
            status=status.HTTP_201_CREATED
        )
