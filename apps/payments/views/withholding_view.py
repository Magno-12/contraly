from rest_framework import status, permissions, filters
from rest_framework.viewsets import GenericViewSet
from rest_framework.response import Response
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend

from apps.payments.models import Withholding, Payment
from apps.payments.serializers import WithholdingSerializer, WithholdingCreateSerializer
from apps.core.utils import create_audit_log, get_client_ip
from apps.core.permission import IsAdministrator


class WithholdingViewSet(GenericViewSet):
    """
    API endpoint para gestionar retenciones
    """
    queryset = Withholding.objects.filter(is_deleted=False)
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['payment', 'withholding_type', 'tenant']
    search_fields = ['name', 'code', 'description']
    ordering_fields = ['name', 'percentage', 'amount', 'created_at']
    ordering = ['payment', 'name']
    
    def get_serializer_class(self):
        if self.action == 'create':
            return WithholdingCreateSerializer
        return WithholdingSerializer
    
    def get_permissions(self):
        """
        Permisos para gestionar retenciones
        """
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [permissions.IsAuthenticated, IsAdministrator]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        """
        Filtrar retenciones según permisos del usuario
        """
        queryset = super().get_queryset()
        user = self.request.user
        
        # Superusers ven todas las retenciones
        if user.is_superuser:
            return queryset
            
        # Administradores ven retenciones de su organización
        if hasattr(user, 'user_roles') and user.user_roles.filter(
            role__name='Administrator',
            is_active=True,
            is_deleted=False
        ).exists():
            if user.tenant:
                return queryset.filter(tenant=user.tenant)
        
        # Usuarios normales ven retenciones de pagos donde son propietarios de la factura
        payment_ids = Payment.objects.filter(
            invoice__issuer=user,
            is_active=True,
            is_deleted=False
        ).values_list('id', flat=True)
        
        return queryset.filter(payment_id__in=payment_ids)
    
    def list(self, request):
        """
        Listar retenciones
        """
        queryset = self.filter_queryset(self.get_queryset())
        
        # Filtros adicionales
        payment_id = request.query_params.get('payment_id', None)
        if payment_id:
            queryset = queryset.filter(payment_id=payment_id)
        
        # Paginación
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
            
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    def retrieve(self, request, pk=None):
        """
        Obtener detalle de una retención
        """
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
    
    def create(self, request):
        """
        Crear una nueva retención
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Establecer tenant si no se proporciona
        if 'tenant' not in serializer.validated_data:
            payment = serializer.validated_data.get('payment')
            if payment and payment.tenant:
                serializer.validated_data['tenant'] = payment.tenant
            elif request.user.tenant:
                serializer.validated_data['tenant'] = request.user.tenant
        
        # Verificar estado del pago
        payment = serializer.validated_data.get('payment')
        from apps.payments.models import PaymentStatus
        current_status = PaymentStatus.objects.filter(
            payment=payment,
            is_active=True,
            is_deleted=False
        ).order_by('-change_date').first()
        
        if current_status and current_status.status not in ['PENDING', 'VERIFIED']:
            return Response(
                {"detail": "No se pueden añadir retenciones a un pago que no está en estado pendiente o verificado."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Crear retención
        withholding = serializer.save(
            created_by=request.user,
            updated_by=request.user
        )
        
        # Registrar creación
        create_audit_log(
            user=request.user,
            action='CREATE',
            model_name='Withholding',
            instance_id=withholding.id,
            description=f"Creación de retención {withholding.name} para pago {payment.id}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            tenant=request.user.tenant
        )
        
        return Response(
            self.get_serializer(withholding).data,
            status=status.HTTP_201_CREATED
        )
    
    def update(self, request, pk=None):
        """
        Actualizar una retención existente
        """
        instance = self.get_object()
        
        # Verificar estado del pago
        payment = instance.payment
        from apps.payments.models import PaymentStatus
        current_status = PaymentStatus.objects.filter(
            payment=payment,
            is_active=True,
            is_deleted=False
        ).order_by('-change_date').first()
        
        if current_status and current_status.status not in ['PENDING', 'VERIFIED']:
            return Response(
                {"detail": "No se pueden modificar retenciones de un pago que no está en estado pendiente o verificado."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = self.get_serializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        withholding = serializer.save(updated_by=request.user)
        
        # Registrar actualización
        create_audit_log(
            user=request.user,
            action='UPDATE',
            model_name='Withholding',
            instance_id=withholding.id,
            description=f"Actualización de retención {withholding.name} para pago {payment.id}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            tenant=request.user.tenant
        )
        
        return Response(serializer.data)
    
    def partial_update(self, request, pk=None):
        """
        Actualizar parcialmente una retención
        """
        instance = self.get_object()
        
        # Verificar estado del pago
        payment = instance.payment
        from apps.payments.models import PaymentStatus
        current_status = PaymentStatus.objects.filter(
            payment=payment,
            is_active=True,
            is_deleted=False
        ).order_by('-change_date').first()
        
        if current_status and current_status.status not in ['PENDING', 'VERIFIED']:
            return Response(
                {"detail": "No se pueden modificar retenciones de un pago que no está en estado pendiente o verificado."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        withholding = serializer.save(updated_by=request.user)
        
        # Registrar actualización
        create_audit_log(
            user=request.user,
            action='UPDATE',
            model_name='Withholding',
            instance_id=withholding.id,
            description=f"Actualización parcial de retención {withholding.name} para pago {payment.id}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            tenant=request.user.tenant
        )
        
        return Response(serializer.data)
    
    def destroy(self, request, pk=None):
        """
        Eliminar (soft delete) una retención
        """
        instance = self.get_object()
        
        # Verificar estado del pago
        payment = instance.payment
        from apps.payments.models import PaymentStatus
        current_status = PaymentStatus.objects.filter(
            payment=payment,
            is_active=True,
            is_deleted=False
        ).order_by('-change_date').first()
        
        if current_status and current_status.status not in ['PENDING', 'VERIFIED']:
            return Response(
                {"detail": "No se pueden eliminar retenciones de un pago que no está en estado pendiente o verificado."},
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
            model_name='Withholding',
            instance_id=instance.id,
            description=f"Eliminación de retención {instance.name} para pago {payment.id}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            tenant=request.user.tenant
        )
        
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    @action(detail=False, methods=['get'])
    def withholding_types(self, request):
        """
        Obtener lista de tipos de retención disponibles
        """
        return Response([
            {'value': choice[0], 'label': choice[1]}
            for choice in Withholding.WITHHOLDING_TYPE_CHOICES
        ])
    
    @action(detail=False, methods=['get'])
    def by_payment(self, request):
        """
        Obtener retenciones para un pago específico
        """
        payment_id = request.query_params.get('payment_id')
        if not payment_id:
            return Response(
                {"detail": "Se requiere el parámetro payment_id."},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        queryset = self.get_queryset().filter(payment_id=payment_id)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
