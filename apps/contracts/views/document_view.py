from rest_framework import status, permissions, filters
from rest_framework.viewsets import GenericViewSet
from rest_framework.response import Response
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q
from django.utils import timezone

from apps.contracts.models import ContractDocument, Contract, ContractRevision
from apps.contracts.serializers import ContractDocumentSerializer
from apps.core.utils import create_audit_log, get_client_ip


class ContractDocumentViewSet(GenericViewSet):
    """
    API endpoint para gestionar documentos de contratos
    """
    queryset = ContractDocument.objects.filter(is_deleted=False)
    serializer_class = ContractDocumentSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['contract', 'document_type', 'is_signed', 'is_current_version', 'tenant']
    search_fields = ['title', 'description', 'reference_number']
    ordering_fields = ['title', 'document_type', 'created_at']
    ordering = ['-created_at']
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """
        Filtrar documentos según permisos del usuario
        """
        queryset = super().get_queryset()
        user = self.request.user
        
        # Superusers ven todos los documentos
        if user.is_superuser:
            return queryset
        
        # Restricciones para usuarios normales
        if user.tenant:
            # Ver documentos de su organización
            return queryset.filter(tenant=user.tenant)
        
        # Ver solo documentos de contratos donde el usuario está involucrado
        user_contracts = Contract.objects.filter(
            Q(supervisor=user) |
            Q(parties__user=user, parties__is_active=True, parties__is_deleted=False)
        ).distinct()
        
        return queryset.filter(contract__in=user_contracts)
    
    def list(self, request):
        """
        Listar documentos de contratos
        """
        queryset = self.filter_queryset(self.get_queryset())
        
        # Filtros adicionales
        document_type = request.query_params.get('document_type', None)
        if document_type:
            queryset = queryset.filter(document_type=document_type)
            
        # Paginación
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
            
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    def retrieve(self, request, pk=None):
        """
        Obtener detalle de un documento
        """
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        
        # Registrar visualización
        create_audit_log(
            user=request.user,
            action='VIEW',
            model_name='ContractDocument',
            instance_id=instance.id,
            description=f"Visualización de documento de contrato: {instance.title}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            tenant=request.user.tenant
        )
        
        return Response(serializer.data)
    
    def create(self, request):
        """
        Crear un nuevo documento de contrato
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
        
        # Crear documento
        document = serializer.save(
            created_by=request.user,
            updated_by=request.user
        )
        
        # Registrar creación
        create_audit_log(
            user=request.user,
            action='CREATE',
            model_name='ContractDocument',
            instance_id=document.id,
            description=f"Creación de documento de contrato: {document.title}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            tenant=request.user.tenant
        )
        
        # Crear revisión en el contrato
        ContractRevision.objects.create(
            contract=document.contract,
            revision_type='UPLOAD',
            description=f"Carga de documento: {document.title}",
            document=document,
            created_by=request.user,
            updated_by=request.user,
            tenant=document.tenant
        )
        
        return Response(
            self.get_serializer(document).data,
            status=status.HTTP_201_CREATED
        )
    
    def update(self, request, pk=None):
        """
        Actualizar un documento existente
        """
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        document = serializer.save(updated_by=request.user)
        
        # Registrar actualización
        create_audit_log(
            user=request.user,
            action='UPDATE',
            model_name='ContractDocument',
            instance_id=document.id,
            description=f"Actualización de documento de contrato: {document.title}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            tenant=request.user.tenant
        )
        
        return Response(serializer.data)
    
    def partial_update(self, request, pk=None):
        """
        Actualizar parcialmente un documento
        """
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        document = serializer.save(updated_by=request.user)
        
        # Registrar actualización
        create_audit_log(
            user=request.user,
            action='UPDATE',
            model_name='ContractDocument',
            instance_id=document.id,
            description=f"Actualización parcial de documento de contrato: {document.title}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            tenant=request.user.tenant
        )
        
        return Response(serializer.data)
    
    def destroy(self, request, pk=None):
        """
        Eliminar (soft delete) un documento
        """
        instance = self.get_object()
        
        # Soft delete
        instance.is_active = False
        instance.is_deleted = True
        instance.updated_by = request.user
        instance.save()
        
        # Si era la versión actual, marcar como actual la versión anterior
        if instance.is_current_version and instance.parent_document:
            parent = instance.parent_document
            parent.is_current_version = True
            parent.updated_by = request.user
            parent.save()
        
        # Registrar eliminación
        create_audit_log(
            user=request.user,
            action='DELETE',
            model_name='ContractDocument',
            instance_id=instance.id,
            description=f"Eliminación de documento de contrato: {instance.title}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            tenant=request.user.tenant
        )
        
        # Crear revisión en el contrato
        ContractRevision.objects.create(
            contract=instance.contract,
            revision_type='OTHER',
            description=f"Eliminación de documento: {instance.title}",
            created_by=request.user,
            updated_by=request.user,
            tenant=instance.tenant
        )
        
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    @action(detail=True, methods=['post'])
    def mark_signed(self, request, pk=None):
        """
        Marcar un documento como firmado
        """
        document = self.get_object()
        
        # Actualizar estado de firma
        document.is_signed = True
        document.signing_date = request.data.get('signing_date', timezone.now().date())
        document.updated_by = request.user
        document.save()
        
        # Registrar firma
        create_audit_log(
            user=request.user,
            action='UPDATE',
            model_name='ContractDocument',
            instance_id=document.id,
            description=f"Documento marcado como firmado: {document.title}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            tenant=request.user.tenant
        )
        
        # Crear revisión en el contrato
        ContractRevision.objects.create(
            contract=document.contract,
            revision_type='APPROVAL',
            description=f"Firma de documento: {document.title}",
            document=document,
            created_by=request.user,
            updated_by=request.user,
            tenant=document.tenant
        )
        
        # Si es el documento principal del contrato y es el actual contrato
        if document.document_type == 'CONTRACT' and document.is_current_version:
            # Actualizar la fecha de firma del contrato si no está establecida
            contract = document.contract
            if not contract.signing_date:
                contract.signing_date = document.signing_date
                contract.updated_by = request.user
                contract.save()
                
            # Cambiar estado del contrato a firmado si corresponde
            current_status = contract.current_status
            if current_status and current_status.status in ['APPROVED', 'PENDING_APPROVAL']:
                from apps.contracts.models import ContractStatus
                ContractStatus.objects.create(
                    contract=contract,
                    status='SIGNED',
                    comments=f"Contrato firmado. Documento: {document.title}",
                    changed_by=request.user,
                    created_by=request.user,
                    updated_by=request.user,
                    tenant=contract.tenant
                )
        
        return Response(self.get_serializer(document).data)
        
    @action(detail=True, methods=['post'])
    def create_new_version(self, request, pk=None):
        """
        Crear una nueva versión de un documento existente
        """
        document = self.get_object()
        
        # Obtener datos del request
        new_file = request.data.get('file')
        version = request.data.get('version')
        description = request.data.get('description', f"Nueva versión del documento {document.title}")
        
        if not new_file:
            return Response(
                {"detail": "Se requiere un archivo para la nueva versión del documento."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Desactivar la versión actual
        document.is_current_version = False
        document.updated_by = request.user
        document.save()
        
        # Crear nueva versión
        new_version = ContractDocument.objects.create(
            contract=document.contract,
            document_type=document.document_type,
            title=document.title,
            description=description,
            file=new_file,
            is_signed=False,  # Nueva versión no está firmada inicialmente
            version=version or f"{float(document.version) + 0.1:.1f}",
            is_current_version=True,
            parent_document=document,
            tenant=document.tenant,
            created_by=request.user,
            updated_by=request.user
        )
        
        # Registrar creación de nueva versión
        create_audit_log(
            user=request.user,
            action='CREATE',
            model_name='ContractDocument',
            instance_id=new_version.id,
            description=f"Creación de nueva versión del documento: {new_version.title} (v{new_version.version})",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            tenant=request.user.tenant
        )
        
        # Crear revisión en el contrato
        ContractRevision.objects.create(
            contract=document.contract,
            revision_type='UPDATE',
            description=f"Nueva versión del documento: {document.title} (v{new_version.version})",
            document=new_version,
            created_by=request.user,
            updated_by=request.user,
            tenant=document.tenant
        )
        
        return Response(
            self.get_serializer(new_version).data,
            status=status.HTTP_201_CREATED
        )
        
    @action(detail=False, methods=['get'])
    def document_types(self, request):
        """
        Obtener lista de tipos de documentos
        """
        types = [
            {'value': choice[0], 'label': choice[1]} 
            for choice in ContractDocument.DOCUMENT_TYPES
        ]
        return Response(types)
        
    @action(detail=False, methods=['get'])
    def by_contract(self, request):
        """
        Obtener documentos agrupados por contrato
        """
        # Verificar que se proporcionó un contrato
        contract_id = request.query_params.get('contract_id')
        if not contract_id:
            return Response(
                {"detail": "Se requiere el parámetro contract_id."},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        try:
            contract = Contract.objects.get(id=contract_id)
        except Contract.DoesNotExist:
            return Response(
                {"detail": "El contrato especificado no existe."},
                status=status.HTTP_404_NOT_FOUND
            )
            
        # Verificar permisos para ver este contrato
        if not request.user.is_superuser and contract.tenant != request.user.tenant:
            user_can_access = False
            
            # Verificar si el usuario es supervisor o parte del contrato
            if contract.supervisor == request.user:
                user_can_access = True
            else:
                user_in_parties = contract.parties.filter(
                    user=request.user,
                    is_active=True,
                    is_deleted=False
                ).exists()
                
                if user_in_parties:
                    user_can_access = True
                    
            if not user_can_access:
                return Response(
                    {"detail": "No tiene permisos para ver los documentos de este contrato."},
                    status=status.HTTP_403_FORBIDDEN
                )
        
        # Obtener documentos agrupados por tipo
        documents_by_type = {}
        documents = ContractDocument.objects.filter(
            contract=contract,
            is_active=True,
            is_deleted=False
        ).order_by('-created_at')
        
        for doc in documents:
            doc_type = doc.get_document_type_display()
            if doc_type not in documents_by_type:
                documents_by_type[doc_type] = []
            
            documents_by_type[doc_type].append(self.get_serializer(doc).data)
        
        return Response(documents_by_type)
