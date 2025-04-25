from rest_framework import status, permissions, filters
from rest_framework.viewsets import GenericViewSet
from rest_framework.response import Response
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone

from apps.payments.models import PaymentStatus, Payment
from apps.payments.serializers import PaymentStatusSerializer
from apps.core.utils import create_audit_log, get_client_ip
from apps.core.permission import IsAdministrator


class PaymentStatusViewSet(GenericViewSet):
    """
    API endpoint para gestionar estados de pago
    """
    queryset = PaymentStatus.objects.filter(is_deleted=False)
    serializer_class = PaymentStatusSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['payment', 'status', 'tenant']
    search_fields = ['comments']
    ordering_fields = ['change_date', 'status']
    ordering = ['-change_date']
    
    def get_permissions(self):
        """
        Permisos para cambiar estado de pagos
        """
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [permissions.IsAuthenticated, IsAdministrator]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        """
        Filtrar estados según permisos del usuario
        """
        queryset = super().get_queryset()
        user = self.request.user
        
        # Superusers ven todos los estados
        if user.is_superuser:
            return queryset
        
        # Administradores ven estados de su organización
        if hasattr(user, 'user_roles') and user.user_roles.filter(
            role__name='Administrator',
            is_active=True,
            is_deleted=False
        ).exists():
            if user.tenant:
                return queryset.filter(tenant=user.tenant)
        
        # Usuarios normales ven estados de pagos donde son propietarios de la factura
        payment_ids = Payment.objects.filter(
            invoice__issuer=user,
            is_active=True,
            is_deleted=False
        ).values_list('id', flat=True)
        
        return queryset.filter(payment_id__in=payment_ids)
    
    def list(self, request):
        """
        Listar estados de pago
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
        Obtener detalle de un estado
        """
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
    
    def create(self, request):
        """
        Crear un nuevo estado para un pago
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
        
        # Validar transición de estado
        payment = serializer.validated_data.get('payment')
        new_status = serializer.validated_data.get('status')
        
        current_status = PaymentStatus.objects.filter(
            payment=payment,
            is_active=True,
            is_deleted=False
        ).order_by('-change_date').first()
        
        current_status_code = current_status.status if current_status else None
        
        # Definir transiciones válidas
        valid_transitions = {
            'PENDING': ['VERIFIED', 'REJECTED'],
            'VERIFIED': ['REJECTED', 'REFUNDED'],
            'REJECTED': ['PENDING'],
            'REFUNDED': [],
            'CANCELLED': []
        }
        
        # Si no hay estado actual, solo PENDING es válido
        if not current_status_code:
            if new_status != 'PENDING':
                return Response(
                    {"detail": "El estado inicial de un pago debe ser PENDING."},
                    status=status.HTTP_400_BAD_REQUEST
                )
        # Verificar si la transición es válida desde el estado actual
        elif new_status not in valid_transitions.get(current_status_code, []):
            return Response(
                {"detail": f"No se puede cambiar del estado '{current_status_code}' al estado '{new_status}'. Transiciones válidas: {', '.join(valid_transitions.get(current_status_code, []))}"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Incluir contexto
        serializer.context['request'] = request
        
        # Crear estado
        status_obj = serializer.save(
            created_by=request.user,
            updated_by=request.user
        )
        
        # Si el estado es VERIFIED, actualizar la factura
        if new_status == 'VERIFIED':
            payment._update_invoice_status()
        
        # Registrar creación
        create_audit_log(
            user=request.user,
            action='CREATE',
            model_name='PaymentStatus',
            instance_id=status_obj.id,
            description=f"Cambio de estado de pago a {status_obj.get_status_display()}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            tenant=request.user.tenant
        )
        
        return Response(
            self.get_serializer(status_obj).data,
            status=status.HTTP_201_CREATED
        )
    
    def update(self, request, pk=None):
        """
        Actualizar un estado existente
        """
        # Los estados de pago no deberían actualizarse, solo crear nuevos
        return Response(
            {"detail": "Los estados de pago no pueden modificarse una vez creados. Cree un nuevo estado si necesita cambiar el estado del pago."},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    def partial_update(self, request, pk=None):
        """
        Actualizar parcialmente un estado
        """
        # Los estados de pago no deberían actualizarse, solo crear nuevos
        return Response(
            {"detail": "Los estados de pago no pueden modificarse una vez creados. Cree un nuevo estado si necesita cambiar el estado del pago."},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    def destroy(self, request, pk=None):
        """
        Eliminar un estado de pago
        """
        instance = self.get_object()
        
        # No permitir eliminar el estado más reciente
        payment = instance.payment
        latest_status = PaymentStatus.objects.filter(
            payment=payment,
            is_active=True,
            is_deleted=False
        ).order_by('-change_date').first()
        
        if latest_status and latest_status.id == instance.id:
            return Response(
                {"detail": "No se puede eliminar el estado más reciente de un pago."},
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
            model_name='PaymentStatus',
            instance_id=instance.id,
            description=f"Eliminación de estado de pago {instance.get_status_display()}",
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
            for choice in PaymentStatus.STATUS_CHOICES
        ])
    
    @action(detail=False, methods=['get'])
    def current_by_payment(self, request):
        """
        Obtener el estado actual de un pago específico
        """
        payment_id = request.query_params.get('payment_id')
        if not payment_id:
            return Response(
                {"detail": "Se requiere el parámetro payment_id."},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        try:
            payment = Payment.objects.get(id=payment_id)
        except Payment.DoesNotExist:
            return Response(
                {"detail": "El pago especificado no existe."},
                status=status.HTTP_404_NOT_FOUND
            )
            
        current_status = PaymentStatus.objects.filter(
            payment=payment,
            is_active=True,
            is_deleted=False
        ).order_by('-change_date').first()
        
        if not current_status:
            return Response(
                {"detail": "El pago no tiene un estado actual definido."},
                status=status.HTTP_404_NOT_FOUND
            )
            
        serializer = self.get_serializer(current_status)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def history_by_payment(self, request):
        """
        Obtener el historial completo de estados de un pago
        """
        payment_id = request.query_params.get('payment_id')
        if not payment_id:
            return Response(
                {"detail": "Se requiere el parámetro payment_id."},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        try:
            payment = Payment.objects.get(id=payment_id)
        except Payment.DoesNotExist:
            return Response(
                {"detail": "El pago especificado no existe."},
                status=status.HTTP_404_NOT_FOUND
            )
            
        statuses = PaymentStatus.objects.filter(
            payment=payment,
            is_active=True,
            is_deleted=False
        ).order_by('-change_date')
        
        serializer = self.get_serializer(statuses, many=True)
        return Response(serializer.data)
