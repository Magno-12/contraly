from rest_framework import status, permissions, filters
from rest_framework.viewsets import GenericViewSet
from rest_framework.response import Response
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q

from apps.payments.models import PaymentMethod
from apps.payments.serializers import PaymentMethodSerializer
from apps.core.utils import create_audit_log, get_client_ip
from apps.core.permission import IsAdministrator


class PaymentMethodViewSet(GenericViewSet):
    """
    API endpoint para gestionar métodos de pago
    """
    queryset = PaymentMethod.objects.filter(is_deleted=False)
    serializer_class = PaymentMethodSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['payment_type', 'requires_reference', 'requires_receipt', 'tenant']
    search_fields = ['name', 'code', 'description']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']
    
    def get_permissions(self):
        """
        Solo administradores pueden crear/modificar métodos de pago
        """
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [permissions.IsAuthenticated, IsAdministrator]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        """
        Filtrar métodos de pago según permisos del usuario
        """
        queryset = super().get_queryset()
        user = self.request.user
        
        # Superusers ven todos los métodos de pago
        if user.is_superuser:
            return queryset
            
        # Resto de usuarios solo ven métodos de pago de su organización
        if user.tenant:
            return queryset.filter(
                Q(tenant=user.tenant) | Q(tenant__isnull=True)  # Incluir métodos globales
            )
        
        # Usuarios sin tenant solo ven métodos globales
        return queryset.filter(tenant__isnull=True)
    
    def list(self, request):
        """
        Listar métodos de pago
        """
        queryset = self.filter_queryset(self.get_queryset())
        
        # Filtro adicional para mostrar solo activos
        active_only = request.query_params.get('active_only', 'false').lower() == 'true'
        if active_only:
            queryset = queryset.filter(is_active=True)
        
        # Paginación
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
            
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    def retrieve(self, request, pk=None):
        """
        Obtener detalle de un método de pago
        """
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
    
    def create(self, request):
        """
        Crear un nuevo método de pago
        """
        serializer = self.get_serializer(data=request.data)
        serializer.context['tenant'] = request.user.tenant
        serializer.is_valid(raise_exception=True)
        
        # Establecer tenant si no se proporciona
        if 'tenant' not in serializer.validated_data and request.user.tenant:
            serializer.validated_data['tenant'] = request.user.tenant
        
        # Crear método de pago
        payment_method = serializer.save(
            created_by=request.user,
            updated_by=request.user
        )
        
        # Registrar creación
        create_audit_log(
            user=request.user,
            action='CREATE',
            model_name='PaymentMethod',
            instance_id=payment_method.id,
            description=f"Creación de método de pago: {payment_method.name}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            tenant=request.user.tenant
        )
        
        return Response(
            self.get_serializer(payment_method).data,
            status=status.HTTP_201_CREATED
        )
    
    def update(self, request, pk=None):
        """
        Actualizar un método de pago existente
        """
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data)
        serializer.context['tenant'] = request.user.tenant
        serializer.is_valid(raise_exception=True)
        payment_method = serializer.save(updated_by=request.user)
        
        # Registrar actualización
        create_audit_log(
            user=request.user,
            action='UPDATE',
            model_name='PaymentMethod',
            instance_id=payment_method.id,
            description=f"Actualización de método de pago: {payment_method.name}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            tenant=request.user.tenant
        )
        
        return Response(serializer.data)
    
    def partial_update(self, request, pk=None):
        """
        Actualizar parcialmente un método de pago
        """
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.context['tenant'] = request.user.tenant
        serializer.is_valid(raise_exception=True)
        payment_method = serializer.save(updated_by=request.user)
        
        # Registrar actualización
        create_audit_log(
            user=request.user,
            action='UPDATE',
            model_name='PaymentMethod',
            instance_id=payment_method.id,
            description=f"Actualización parcial de método de pago: {payment_method.name}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            tenant=request.user.tenant
        )
        
        return Response(serializer.data)
    
    def destroy(self, request, pk=None):
        """
        Eliminar (soft delete) un método de pago
        """
        instance = self.get_object()
        
        # No permitir eliminar si tiene pagos asociados
        if instance.payments.filter(is_deleted=False).exists():
            return Response(
                {"detail": "No se puede eliminar este método de pago porque tiene pagos asociados."},
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
            model_name='PaymentMethod',
            instance_id=instance.id,
            description=f"Eliminación de método de pago: {instance.name}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            tenant=request.user.tenant
        )
        
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    @action(detail=False, methods=['get'])
    def payment_types(self, request):
        """
        Obtener lista de tipos de pago disponibles
        """
        return Response([
            {'value': choice[0], 'label': choice[1]}
            for choice in PaymentMethod.PAYMENT_TYPE_CHOICES
        ])
