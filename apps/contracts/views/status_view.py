from rest_framework import status, permissions, filters
from rest_framework.viewsets import GenericViewSet
from rest_framework.response import Response
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Count
from django.utils import timezone

from apps.contracts.models import ContractStatus, ContractType, Contract, ContractRevision
from apps.contracts.serializers import ContractStatusSerializer, ContractTypeSerializer
from apps.core.utils import create_audit_log, get_client_ip
from apps.core.permission import IsAdministrator


class ContractStatusViewSet(GenericViewSet):
    """
    API endpoint para gestionar estados de contratos
    """
    queryset = ContractStatus.objects.filter(is_deleted=False)
    serializer_class = ContractStatusSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['contract', 'status', 'tenant']
    search_fields = ['comments']
    ordering_fields = ['start_date', 'status']
    ordering = ['-start_date']
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """
        Filtrar estados según permisos del usuario
        """
        queryset = super().get_queryset()
        user = self.request.user
        
        # Superusers ven todos los estados
        if user.is_superuser:
            return queryset
        
        # Restricciones para usuarios normales
        if user.tenant:
            # Ver estados de su organización
            return queryset.filter(tenant=user.tenant)
        
        # Ver solo estados de contratos donde el usuario está involucrado
        user_contracts = Contract.objects.filter(
            Q(supervisor=user) |
            Q(parties__user=user, parties__is_active=True, parties__is_deleted=False)
        ).distinct()
        
        return queryset.filter(contract__in=user_contracts)
    
    def list(self, request):
        """
        Listar estados de contratos
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
        Obtener detalle de un estado
        """
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
    
    def create(self, request):
        """
        Crear un nuevo estado de contrato
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
        
        # Crear estado
        serializer.context['request'] = request
        status_obj = serializer.save(
            created_by=request.user,
            updated_by=request.user,
            changed_by=request.user
        )
        
        # Registrar creación
        create_audit_log(
            user=request.user,
            action='CREATE',
            model_name='ContractStatus',
            instance_id=status_obj.id,
            description=f"Creación de estado de contrato: {status_obj.get_status_display()}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            tenant=request.user.tenant
        )
        
        # Crear revisión en el contrato
        ContractRevision.objects.create(
            contract=status_obj.contract,
            revision_type='APPROVAL' if status_obj.status in ['APPROVED', 'SIGNED'] else 'UPDATE',
            description=f"Cambio de estado a '{status_obj.get_status_display()}'",
            created_by=request.user,
            updated_by=request.user,
            tenant=status_obj.tenant
        )
        
        return Response(
            self.get_serializer(status_obj).data,
            status=status.HTTP_201_CREATED
        )
    
    def update(self, request, pk=None):
        """
        Actualizar un estado de contrato existente
        """
        instance = self.get_object()
        
        # No permitir actualizar estados cerrados
        if instance.end_date is not None:
            return Response(
                {"detail": "No se puede modificar un estado que ya ha sido cerrado."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = self.get_serializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        status_obj = serializer.save(updated_by=request.user)
        
        # Registrar actualización
        create_audit_log(
            user=request.user,
            action='UPDATE',
            model_name='ContractStatus',
            instance_id=status_obj.id,
            description=f"Actualización de estado de contrato: {status_obj.get_status_display()}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            tenant=request.user.tenant
        )
        
        return Response(serializer.data)
    
    def partial_update(self, request, pk=None):
        """
        Actualizar parcialmente un estado de contrato
        """
        instance = self.get_object()
        
        # No permitir actualizar estados cerrados
        if instance.end_date is not None:
            return Response(
                {"detail": "No se puede modificar un estado que ya ha sido cerrado."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        status_obj = serializer.save(updated_by=request.user)
        
        # Registrar actualización
        create_audit_log(
            user=request.user,
            action='UPDATE',
            model_name='ContractStatus',
            instance_id=status_obj.id,
            description=f"Actualización parcial de estado de contrato: {status_obj.get_status_display()}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            tenant=request.user.tenant
        )
        
        return Response(serializer.data)
    
    def destroy(self, request, pk=None):
        """
        Eliminar (soft delete) un estado de contrato
        """
        instance = self.get_object()
        
        # No permitir eliminar el estado actual de un contrato
        contract = instance.contract
        current_status = contract.current_status
        
        if current_status and current_status.id == instance.id:
            return Response(
                {"detail": "No se puede eliminar el estado actual de un contrato."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Soft delete
        instance.is_active = False
        instance.is_deleted = True
        instance.updated_by = request.user
        instance.save()
        
        # Registrar eliminación
        create_audit_log(
            user=request.user,
            action='DELETE',
            model_name='ContractStatus',
            instance_id=instance.id,
            description=f"Eliminación de estado de contrato: {instance.get_status_display()}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            tenant=request.user.tenant
        )
        
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    @action(detail=False, methods=['get'])
    def status_choices(self, request):
        """
        Obtener lista de estados posibles
        """
        return Response([
            {'value': choice[0], 'label': choice[1]}
            for choice in ContractStatus.STATUS_CHOICES
        ])
        
    @action(detail=False, methods=['get'])
    def current_by_contract(self, request):
        """
        Obtener el estado actual de un contrato específico
        """
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
            
        current_status = contract.current_status
        if not current_status:
            return Response(
                {"detail": "El contrato no tiene un estado actual definido."},
                status=status.HTTP_404_NOT_FOUND
            )
            
        serializer = self.get_serializer(current_status)
        return Response(serializer.data)
        
    @action(detail=False, methods=['get'])
    def history_by_contract(self, request):
        """
        Obtener el historial completo de estados de un contrato
        """
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
            
        statuses = ContractStatus.objects.filter(
            contract=contract,
            is_active=True,
            is_deleted=False
        ).order_by('-start_date')
        
        serializer = self.get_serializer(statuses, many=True)
        return Response(serializer.data)
        
    @action(detail=False, methods=['post'])
    def transition(self, request):
        """
        Realizar una transición de estado para un contrato
        """
        # Validar datos requeridos
        contract_id = request.data.get('contract_id')
        new_status = request.data.get('status')
        comments = request.data.get('comments', '')
        
        if not contract_id or not new_status:
            return Response(
                {"detail": "Se requieren los parámetros contract_id y status."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verificar que el estado solicitado es válido
        valid_statuses = [choice[0] for choice in ContractStatus.STATUS_CHOICES]
        if new_status not in valid_statuses:
            return Response(
                {"detail": f"El estado '{new_status}' no es válido. Opciones válidas: {', '.join(valid_statuses)}"},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        # Obtener el contrato
        try:
            contract = Contract.objects.get(id=contract_id)
        except Contract.DoesNotExist:
            return Response(
                {"detail": "El contrato especificado no existe."},
                status=status.HTTP_404_NOT_FOUND
            )
            
        # Verificar permisos para modificar este contrato
        if not request.user.is_superuser and contract.tenant != request.user.tenant:
            # Comprobar si es supervisor o tiene un rol con permiso
            if contract.supervisor != request.user and not (
                hasattr(request.user, 'user_roles') and 
                request.user.user_roles.filter(
                    role__role_permissions__permission__code__in=[
                        'contracts.approve_contract',
                        'contracts.change_contract_status'
                    ],
                    is_active=True, 
                    is_deleted=False
                ).exists()
            ):
                return Response(
                    {"detail": "No tiene permisos para cambiar el estado de este contrato."},
                    status=status.HTTP_403_FORBIDDEN
                )
        
        # Verificar transiciones válidas desde el estado actual
        current_status = contract.current_status
        current_status_code = current_status.status if current_status else None
        
        # Definir transiciones válidas
        valid_transitions = {
            'DRAFT': ['REVIEW', 'PENDING_APPROVAL', 'CANCELLED'],
            'REVIEW': ['DRAFT', 'PENDING_APPROVAL', 'APPROVED', 'CANCELLED'],
            'PENDING_APPROVAL': ['APPROVED', 'REVIEW', 'DRAFT', 'CANCELLED'],
            'APPROVED': ['SIGNED', 'PENDING_APPROVAL', 'CANCELLED'],
            'SIGNED': ['ACTIVE', 'ON_HOLD', 'CANCELLED'],
            'ACTIVE': ['COMPLETED', 'TERMINATED', 'ON_HOLD', 'EXPIRED'],
            'ON_HOLD': ['ACTIVE', 'TERMINATED', 'CANCELLED'],
            'COMPLETED': ['ARCHIVED'],
            'TERMINATED': ['ARCHIVED'],
            'CANCELLED': ['ARCHIVED'],
            'EXPIRED': ['ARCHIVED'],
            'ARCHIVED': []
        }
        
        # Si no hay estado actual, cualquier estado inicial es válido
        if not current_status_code:
            valid_initial_states = ['DRAFT', 'REVIEW', 'PENDING_APPROVAL']
            if new_status not in valid_initial_states:
                return Response(
                    {"detail": f"Para un contrato nuevo, solo se permiten los estados iniciales: {', '.join(valid_initial_states)}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        # Verificar si la transición es válida desde el estado actual
        elif new_status not in valid_transitions.get(current_status_code, []):
            return Response(
                {"detail": f"No se puede cambiar del estado '{current_status_code}' al estado '{new_status}'. Transiciones válidas: {', '.join(valid_transitions.get(current_status_code, []))}"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Crear el nuevo estado
        new_status_obj = ContractStatus.objects.create(
            contract=contract,
            status=new_status,
            comments=comments,
            changed_by=request.user,
            created_by=request.user,
            updated_by=request.user,
            tenant=contract.tenant
        )
        
        # Registrar cambio de estado
        create_audit_log(
            user=request.user,
            action='UPDATE',
            model_name='ContractStatus',
            instance_id=new_status_obj.id,
            description=f"Transición de estado de '{current_status_code}' a '{new_status}'",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            tenant=request.user.tenant
        )
        
        # Crear revisión en el contrato
        ContractRevision.objects.create(
            contract=contract,
            revision_type='APPROVAL' if new_status in ['APPROVED', 'SIGNED'] else 'UPDATE',
            description=f"Cambio de estado a '{new_status_obj.get_status_display()}'",
            created_by=request.user,
            updated_by=request.user,
            tenant=contract.tenant
        )
        
        # Actualizar fecha de firma si el estado es SIGNED
        if new_status == 'SIGNED' and not contract.signing_date:
            contract.signing_date = timezone.now().date()
            contract.updated_by = request.user
            contract.save(update_fields=['signing_date', 'updated_by', 'updated_at'])
        
        return Response(self.get_serializer(new_status_obj).data)
    
    @action(detail=False, methods=['get'])
    def contracts_by_status(self, request):
        """
        Obtener un resumen de contratos agrupados por estado
        """
        # Filtrar por tenant si el usuario no es superadmin
        if request.user.is_superuser:
            contracts = Contract.objects.filter(is_active=True, is_deleted=False)
        elif request.user.tenant:
            contracts = Contract.objects.filter(
                tenant=request.user.tenant,
                is_active=True, 
                is_deleted=False
            )
        else:
            # Usuarios sin tenant ven contratos donde están involucrados
            contracts = Contract.objects.filter(
                Q(supervisor=request.user) |
                Q(parties__user=request.user, parties__is_active=True, parties__is_deleted=False),
                is_active=True,
                is_deleted=False
            ).distinct()
        
        # Obtener el estado actual de cada contrato
        status_counts = {}
        status_details = {}
        
        # Agrupar contratos por estado
        for contract in contracts:
            current_status = contract.current_status
            if not current_status:
                continue
                
            status_code = current_status.status
            status_display = current_status.get_status_display()
            
            # Inicializar contadores
            if status_code not in status_counts:
                status_counts[status_code] = 0
                status_details[status_code] = {
                    'code': status_code,
                    'display': status_display,
                    'count': 0,
                    'contracts': []
                }
            
            # Incrementar contador y agregar detalle del contrato
            status_counts[status_code] += 1
            status_details[status_code]['count'] += 1
            status_details[status_code]['contracts'].append({
                'id': str(contract.id),
                'contract_number': contract.contract_number,
                'title': contract.title,
                'start_date': contract.start_date,
                'end_date': contract.end_date,
                'value': float(contract.value) if contract.value else None,
                'currency': contract.currency
            })
        
        # Ordenar por código de estado
        result = [
            status_details[status_code] 
            for status_code in sorted(status_details.keys())
        ]
        
        return Response(result)


class ContractTypeViewSet(GenericViewSet):
    """
    API endpoint para gestionar tipos de contratos
    """
    queryset = ContractType.objects.filter(is_deleted=False)
    serializer_class = ContractTypeSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active', 'requires_approval', 'tenant']
    search_fields = ['name', 'code', 'description']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']
    
    def get_permissions(self):
        """
        Solo administradores pueden crear, actualizar y eliminar tipos de contratos
        """
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [permissions.IsAuthenticated, IsAdministrator]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        """
        Filtrar tipos de contratos según permisos del usuario
        """
        queryset = super().get_queryset()
        user = self.request.user
        
        # Superusers ven todos los tipos
        if user.is_superuser:
            return queryset
        
        # Usuarios normales solo ven tipos de su organización
        if user.tenant:
            return queryset.filter(Q(tenant=user.tenant) | Q(tenant__isnull=True))
        
        # Sin tenant, solo ver tipos globales
        return queryset.filter(tenant__isnull=True)
    
    def list(self, request):
        """
        Listar tipos de contratos
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
        Obtener detalle de un tipo de contrato
        """
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
    
    def create(self, request):
        """
        Crear un nuevo tipo de contrato
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Establecer tenant si no se proporciona y el usuario tiene uno
        if 'tenant' not in serializer.validated_data and request.user.tenant:
            serializer.validated_data['tenant'] = request.user.tenant
        
        # Crear tipo
        contract_type = serializer.save(
            created_by=request.user,
            updated_by=request.user
        )
        
        # Registrar creación
        create_audit_log(
            user=request.user,
            action='CREATE',
            model_name='ContractType',
            instance_id=contract_type.id,
            description=f"Creación de tipo de contrato: {contract_type.name}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            tenant=request.user.tenant
        )
        
        return Response(
            self.get_serializer(contract_type).data,
            status=status.HTTP_201_CREATED
        )
    
    def update(self, request, pk=None):
        """
        Actualizar un tipo de contrato existente
        """
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        contract_type = serializer.save(updated_by=request.user)
        
        # Registrar actualización
        create_audit_log(
            user=request.user,
            action='UPDATE',
            model_name='ContractType',
            instance_id=contract_type.id,
            description=f"Actualización de tipo de contrato: {contract_type.name}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            tenant=request.user.tenant
        )
        
        return Response(serializer.data)
    
    def partial_update(self, request, pk=None):
        """
        Actualizar parcialmente un tipo de contrato
        """
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        contract_type = serializer.save(updated_by=request.user)
        
        # Registrar actualización
        create_audit_log(
            user=request.user,
            action='UPDATE',
            model_name='ContractType',
            instance_id=contract_type.id,
            description=f"Actualización parcial de tipo de contrato: {contract_type.name}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            tenant=request.user.tenant
        )
        
        return Response(serializer.data)
    
    def destroy(self, request, pk=None):
        """
        Eliminar (soft delete) un tipo de contrato
        """
        instance = self.get_object()
        
        # Verificar si hay contratos que usan este tipo
        contracts_count = Contract.objects.filter(
            contract_type=instance,
            is_active=True,
            is_deleted=False
        ).count()
        
        if contracts_count > 0:
            return Response(
                {"detail": f"No se puede eliminar el tipo de contrato porque está siendo utilizado por {contracts_count} contratos."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Soft delete
        instance.is_active = False
        instance.is_deleted = True
        instance.updated_by = request.user
        instance.save()
        
        # Registrar eliminación
        create_audit_log(
            user=request.user,
            action='DELETE',
            model_name='ContractType',
            instance_id=instance.id,
            description=f"Eliminación de tipo de contrato: {instance.name}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            tenant=request.user.tenant
        )
        
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    @action(detail=False, methods=['get'])
    def with_contract_count(self, request):
        """
        Obtener tipos de contrato con el conteo de contratos asociados
        """
        queryset = self.filter_queryset(self.get_queryset())
        
        # Agregar conteo de contratos
        result = []
        for contract_type in queryset:
            contracts_count = Contract.objects.filter(
                contract_type=contract_type,
                is_active=True,
                is_deleted=False
            ).count()
            
            data = self.get_serializer(contract_type).data
            data['contracts_count'] = contracts_count
            result.append(data)
        
        # Ordenar por nombre
        result = sorted(result, key=lambda x: x['name'])
        
        return Response(result)
    
    @action(detail=False, methods=['get'])
    def by_tenant(self, request):
        """
        Agrupar tipos de contrato por tenant
        """
        # Solo administradores pueden ver agrupados por tenant
        if not request.user.is_superuser and not (
            hasattr(request.user, 'user_roles') and 
            request.user.user_roles.filter(
                role__name='Administrator',
                is_active=True,
                is_deleted=False
            ).exists()
        ):
            return Response(
                {"detail": "No tiene permisos para ver esta información."},
                status=status.HTTP_403_FORBIDDEN
            )
            
        # Obtener todos los tenants con tipos de contrato
        from apps.organizations.models import Organization
        
        result = {}
        
        # Primero los tipos globales (sin tenant)
        global_types = ContractType.objects.filter(
            tenant__isnull=True,
            is_active=True,
            is_deleted=False
        )
        
        if global_types.exists():
            result['global'] = {
                'name': 'Global',
                'types': self.get_serializer(global_types, many=True).data
            }
        
        # Luego por tenant
        tenants = Organization.objects.filter(
            is_active=True,
            is_deleted=False
        )
        
        for tenant in tenants:
            tenant_types = ContractType.objects.filter(
                tenant=tenant,
                is_active=True,
                is_deleted=False
            )
            
            if tenant_types.exists():
                result[str(tenant.id)] = {
                    'name': tenant.name,
                    'types': self.get_serializer(tenant_types, many=True).data
                }
        
        return Response(result)
    
    @action(detail=True, methods=['get'])
    def contracts(self, request, pk=None):
        """
        Obtener contratos de un tipo específico
        """
        contract_type = self.get_object()
        
        # Obtener contratos de este tipo
        contracts = Contract.objects.filter(
            contract_type=contract_type,
            is_active=True,
            is_deleted=False
        )
        
        # Filtrar por tenant si el usuario no es superadmin
        if not request.user.is_superuser and request.user.tenant:
            contracts = contracts.filter(tenant=request.user.tenant)
        
        # Formato simplificado para la lista
        result = []
        for contract in contracts:
            current_status = contract.current_status
            status_display = current_status.get_status_display() if current_status else "Sin estado"
            
            result.append({
                'id': str(contract.id),
                'contract_number': contract.contract_number,
                'title': contract.title,
                'start_date': contract.start_date,
                'end_date': contract.end_date,
                'value': float(contract.value) if contract.value else None,
                'currency': contract.currency,
                'status': current_status.status if current_status else None,
                'status_display': status_display
            })
        
        # Paginación manual
        page_size = int(request.query_params.get('page_size', 10))
        page = int(request.query_params.get('page', 1))
        
        start = (page - 1) * page_size
        end = start + page_size
        
        paginated_result = result[start:end]
        
        return Response({
            'count': len(result),
            'next': f"?page={page+1}&page_size={page_size}" if end < len(result) else None,
            'previous': f"?page={page-1}&page_size={page_size}" if page > 1 else None,
            'results': paginated_result
        })
    
    @action(detail=False, methods=['get'])
    def for_current_tenant(self, request):
        """
        Obtener tipos de contrato disponibles para el tenant actual del usuario
        """
        user = request.user
        
        # Si el usuario no tiene tenant, devolver solo tipos globales
        if not user.tenant:
            queryset = ContractType.objects.filter(
                tenant__isnull=True,
                is_active=True,
                is_deleted=False
            )
        else:
            # Devolver tipos del tenant del usuario y globales
            queryset = ContractType.objects.filter(
                Q(tenant=user.tenant) | Q(tenant__isnull=True),
                is_active=True,
                is_deleted=False
            )
        
        # Ordenar por nombre
        queryset = queryset.order_by('name')
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
