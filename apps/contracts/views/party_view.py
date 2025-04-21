from rest_framework import status, permissions, filters
from rest_framework.viewsets import GenericViewSet
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from apps.contracts.models import ContractParty, Contract
from apps.contracts.serializers import ContractPartySerializer
from apps.core.utils import create_audit_log, get_client_ip


class ContractPartyViewSet(GenericViewSet):
    """
    API endpoint para gestionar partes involucradas en contratos
    """
    queryset = ContractParty.objects.filter(is_deleted=False)
    serializer_class = ContractPartySerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['contract', 'party_type', 'user', 'organization', 'tenant']
    search_fields = ['name', 'identification_number', 'email', 'role']
    ordering_fields = ['party_type', 'created_at']
    ordering = ['party_type', 'created_at']
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """
        Filtrar partes de contratos según permisos del usuario
        """
        queryset = super().get_queryset()
        user = self.request.user
        
        # Superusers ven todas las partes
        if user.is_superuser:
            return queryset
        
        # Restricciones para usuarios normales
        if user.tenant:
            # Ver partes de contratos de su organización
            return queryset.filter(tenant=user.tenant)
        
        # Ver solo partes donde el usuario está involucrado
        user_contracts = Contract.objects.filter(
            Q(supervisor=user) |
            Q(parties__user=user, parties__is_active=True, parties__is_deleted=False)
        ).distinct()
        
        return queryset.filter(contract__in=user_contracts)
    
    def list(self, request):
        """
        Listar partes de contratos
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
        Obtener detalle de una parte
        """
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
    
    def create(self, request):
        """
        Crear una nueva parte de contrato
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
        
        # Crear parte
        party = serializer.save(
            created_by=request.user,
            updated_by=request.user
        )
        
        # Registrar creación
        create_audit_log(
            user=request.user,
            action='CREATE',
            model_name='ContractParty',
            instance_id=party.id,
            description=f"Creación de parte de contrato: {party}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            data=request.data,
            tenant=request.user.tenant
        )
        
        return Response(
            self.get_serializer(party).data,
            status=status.HTTP_201_CREATED
        )
    
    def update(self, request, pk=None):
        """
        Actualizar una parte existente
        """
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        party = serializer.save(updated_by=request.user)
        
        # Registrar actualización
        create_audit_log(
            user=request.user,
            action='UPDATE',
            model_name='ContractParty',
            instance_id=party.id,
            description=f"Actualización de parte de contrato: {party}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            data=request.data,
            tenant=request.user.tenant
        )
        
        return Response(serializer.data)
    
    def partial_update(self, request, pk=None):
        """
        Actualizar parcialmente una parte
        """
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        party = serializer.save(updated_by=request.user)
        
        # Registrar actualización
        create_audit_log(
            user=request.user,
            action='UPDATE',
            model_name='ContractParty',
            instance_id=party.id,
            description=f"Actualización parcial de parte de contrato: {party}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            data=request.data,
            tenant=request.user.tenant
        )
        
        return Response(serializer.data)
    
    def destroy(self, request, pk=None):
        """
        Eliminar (soft delete) una parte
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
            model_name='ContractParty',
            instance_id=instance.id,
            description=f"Eliminación de parte de contrato: {instance}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            tenant=request.user.tenant
        )
        
        return Response(status=status.HTTP_204_NO_CONTENT)
