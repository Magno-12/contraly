from rest_framework import status, permissions, filters
from rest_framework.viewsets import GenericViewSet
from rest_framework.response import Response
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Sum
from django.utils import timezone

from apps.payments.models import Payment, PaymentStatus, Withholding
from apps.payments.serializers import (
    PaymentListSerializer, PaymentDetailSerializer, PaymentCreateSerializer,
    PaymentStatusSerializer, WithholdingSerializer
)
from apps.core.utils import create_audit_log, get_client_ip
from apps.core.permission import IsAdministrator


class PaymentViewSet(GenericViewSet):
    """
    API endpoint para gestionar pagos
    """
    queryset = Payment.objects.filter(is_deleted=False)
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['invoice', 'payment_method', 'is_partial', 'tenant']
    search_fields = ['reference', 'notes', 'invoice__invoice_number', 'transaction_id']
    ordering_fields = ['payment_date', 'amount', 'created_at']
    ordering = ['-payment_date']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return PaymentListSerializer
        elif self.action == 'retrieve':
            return PaymentDetailSerializer
        elif self.action == 'create':
            return PaymentCreateSerializer
        return PaymentDetailSerializer
    
    def get_permissions(self):
        """
        Solo usuarios autorizados pueden registrar pagos
        """
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [permissions.IsAuthenticated, IsAdministrator]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        """
        Filtrar pagos según permisos del usuario
        """
        queryset = super().get_queryset()
        user = self.request.user
        
        # Superusers ven todos los pagos
        if user.is_superuser:
            return queryset
            
        # Administradores ven los pagos de su organización
        if hasattr(user, 'user_roles') and user.user_roles.filter(
            role__name='Administrator',
            is_active=True,
            is_deleted=False
        ).exists():
            if user.tenant:
                return queryset.filter(tenant=user.tenant)
        
        # Usuarios normales ven pagos donde son propietarios de la factura
        return queryset.filter(invoice__issuer=user)
    
    def list(self, request):
        """
        Listar pagos con filtros
        """
        queryset = self.filter_queryset(self.get_queryset())
        
        # Filtros adicionales
        invoice_id = request.query_params.get('invoice_id', None)
        if invoice_id:
            queryset = queryset.filter(invoice_id=invoice_id)
        
        # Filtro por fecha
        payment_after = request.query_params.get('payment_after', None)
        payment_before = request.query_params.get('payment_before', None)
        
        if payment_after:
            queryset = queryset.filter(payment_date__gte=payment_after)
        if payment_before:
            queryset = queryset.filter(payment_date__lte=payment_before)
        
        # Filtro por estado
        status = request.query_params.get('status', None)
        if status:
            # Obtener IDs de pagos con el estado solicitado
            payment_ids = PaymentStatus.objects.filter(
                status=status,
                is_active=True,
                is_deleted=False
            ).values_list('payment_id', flat=True).distinct()
            
            queryset = queryset.filter(id__in=payment_ids)
        
        # Paginación
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
            
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    def retrieve(self, request, pk=None):
        """
        Obtener detalles de un pago
        """
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        
        # Registrar visualización
        create_audit_log(
            user=request.user,
            action='VIEW',
            model_name='Payment',
            instance_id=instance.id,
            description=f"Visualización de pago para factura {instance.invoice.invoice_number}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            tenant=request.user.tenant
        )
        
        return Response(serializer.data)
    
    def create(self, request):
        """
        Registrar un nuevo pago
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Establecer tenant si no se proporciona
        if 'tenant' not in serializer.validated_data and request.user.tenant:
            serializer.validated_data['tenant'] = request.user.tenant
        
        # Incluir contexto
        serializer.context['request'] = request
        
        # Crear pago
        payment = serializer.save(
            created_by=request.user,
            updated_by=request.user
        )
        
        # Registrar creación
        create_audit_log(
            user=request.user,
            action='CREATE',
            model_name='Payment',
            instance_id=payment.id,
            description=f"Registro de pago para factura {payment.invoice.invoice_number}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            tenant=request.user.tenant
        )
        
        return Response(
            PaymentDetailSerializer(payment).data,
            status=status.HTTP_201_CREATED
        )
    
    def update(self, request, pk=None):
        """
        Actualizar un pago existente
        """
        instance = self.get_object()
        
        # Verificar que no esté verificado
        current_status = PaymentStatus.objects.filter(
            payment=instance,
            is_active=True,
            is_deleted=False
        ).order_by('-change_date').first()
        
        if current_status and current_status.status not in ['PENDING', 'REJECTED']:
            return Response(
                {"detail": f"No se puede modificar un pago que ya ha sido {current_status.get_status_display().lower()}."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = self.get_serializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        payment = serializer.save(updated_by=request.user)
        
        # Registrar actualización
        create_audit_log(
            user=request.user,
            action='UPDATE',
            model_name='Payment',
            instance_id=payment.id,
            description=f"Actualización de pago para factura {payment.invoice.invoice_number}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            tenant=request.user.tenant
        )
        
        return Response(PaymentDetailSerializer(payment).data)
    
    def partial_update(self, request, pk=None):
        """
        Actualizar parcialmente un pago
        """
        instance = self.get_object()
        
        # Verificar que no esté verificado
        current_status = PaymentStatus.objects.filter(
            payment=instance,
            is_active=True,
            is_deleted=False
        ).order_by('-change_date').first()
        
        if current_status and current_status.status not in ['PENDING', 'REJECTED']:
            return Response(
                {"detail": f"No se puede modificar un pago que ya ha sido {current_status.get_status_display().lower()}."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        payment = serializer.save(updated_by=request.user)
        
        # Registrar actualización
        create_audit_log(
            user=request.user,
            action='UPDATE',
            model_name='Payment',
            instance_id=payment.id,
            description=f"Actualización parcial de pago para factura {payment.invoice.invoice_number}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            tenant=request.user.tenant
        )
        
        return Response(PaymentDetailSerializer(payment).data)
    
    def destroy(self, request, pk=None):
        """
        Eliminar (soft delete) un pago
        """
        instance = self.get_object()
        
        # Verificar que no esté verificado
        current_status = PaymentStatus.objects.filter(
            payment=instance,
            is_active=True,
            is_deleted=False
        ).order_by('-change_date').first()
        
        if current_status and current_status.status not in ['PENDING', 'REJECTED']:
            return Response(
                {"detail": f"No se puede eliminar un pago que ya ha sido {current_status.get_status_display().lower()}."},
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
            model_name='Payment',
            instance_id=instance.id,
            description=f"Eliminación de pago para factura {instance.invoice.invoice_number}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            tenant=request.user.tenant
        )
        
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    @action(detail=True, methods=['get'])
    def withholdings(self, request, pk=None):
        """
        Obtener retenciones de un pago
        """
        payment = self.get_object()
        
        withholdings = Withholding.objects.filter(
            payment=payment,
            is_active=True,
            is_deleted=False
        )
        
        serializer = WithholdingSerializer(withholdings, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def status_history(self, request, pk=None):
        """
        Obtener historial de estados de un pago
        """
        payment = self.get_object()
        
        statuses = PaymentStatus.objects.filter(
            payment=payment,
            is_active=True,
            is_deleted=False
        ).order_by('-change_date')
        
        serializer = PaymentStatusSerializer(statuses, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def verify(self, request, pk=None):
        """
        Verificar un pago
        """
        payment = self.get_object()
        
        # Verificar estado actual
        current_status = PaymentStatus.objects.filter(
            payment=payment,
            is_active=True,
            is_deleted=False
        ).order_by('-change_date').first()
        
        if not current_status or current_status.status != 'PENDING':
            return Response(
                {"detail": "Solo se pueden verificar pagos en estado pendiente."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Crear nuevo estado
        status_obj = PaymentStatus.objects.create(
            payment=payment,
            status='VERIFIED',
            comments=request.data.get('comments', 'Pago verificado'),
            changed_by=request.user,
            created_by=request.user,
            updated_by=request.user,
            tenant=payment.tenant
        )
        
        # Registrar verificación
        create_audit_log(
            user=request.user,
            action='VERIFY',
            model_name='Payment',
            instance_id=payment.id,
            description=f"Verificación de pago para factura {payment.invoice.invoice_number}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            tenant=request.user.tenant
        )
        
        # Actualizar estado de la factura si es necesario
        payment._update_invoice_status()
        
        return Response({
            "detail": "Pago verificado correctamente.",
            "status": PaymentStatusSerializer(status_obj).data
        })
    
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """
        Rechazar un pago
        """
        payment = self.get_object()
        
        # Verificar estado actual
        current_status = PaymentStatus.objects.filter(
            payment=payment,
            is_active=True,
            is_deleted=False
        ).order_by('-change_date').first()
        
        if not current_status or current_status.status not in ['PENDING', 'VERIFIED']:
            return Response(
                {"detail": "Solo se pueden rechazar pagos en estado pendiente o verificado."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verificar que se proporciona un motivo
        if not request.data.get('comments'):
            return Response(
                {"detail": "Debe proporcionar un motivo para el rechazo."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Crear nuevo estado
        status_obj = PaymentStatus.objects.create(
            payment=payment,
            status='REJECTED',
            comments=request.data.get('comments'),
            changed_by=request.user,
            created_by=request.user,
            updated_by=request.user,
            tenant=payment.tenant
        )
        
        # Registrar rechazo
        create_audit_log(
            user=request.user,
            action='REJECT',
            model_name='Payment',
            instance_id=payment.id,
            description=f"Rechazo de pago para factura {payment.invoice.invoice_number}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            tenant=request.user.tenant
        )
        
        return Response({
            "detail": "Pago rechazado.",
            "status": PaymentStatusSerializer(status_obj).data
        })
    
    @action(detail=False, methods=['get'])
    def by_invoice(self, request):
        """
        Obtener pagos para una factura específica
        """
        invoice_id = request.query_params.get('invoice_id')
        if not invoice_id:
            return Response(
                {"detail": "Se requiere el parámetro invoice_id."},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        queryset = self.get_queryset().filter(invoice_id=invoice_id)
        serializer = PaymentListSerializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def dashboard(self, request):
        """
        Obtener resumen para el dashboard
        """
        # Filtrar por tenant del usuario
        if request.user.is_superuser:
            queryset = self.queryset
        elif request.user.tenant:
            queryset = self.queryset.filter(tenant=request.user.tenant)
        else:
            # Usuarios sin tenant solo ven pagos de facturas donde son emisores
            queryset = self.queryset.filter(invoice__issuer=request.user)
        
        # Filtrar por fecha si se proporciona
        start_date = request.query_params.get('start_date', None)
        end_date = request.query_params.get('end_date', None)
        
        if start_date:
            queryset = queryset.filter(payment_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(payment_date__lte=end_date)
        
        # Estadísticas generales
        total_count = queryset.count()
        total_amount = queryset.aggregate(total=Sum('amount'))['total'] or 0
        
        # Pagos por estado
        from django.db.models import Count
        status_counts = {}
        payment_ids = queryset.values_list('id', flat=True)
        
        for payment_id, payment_status in PaymentStatus.objects.filter(
            payment_id__in=payment_ids,
            is_active=True,
            is_deleted=False
        ).values_list('payment_id', 'status').order_by('payment_id', '-change_date').distinct('payment_id'):
            if payment_status not in status_counts:
                status_counts[payment_status] = 0
            status_counts[payment_status] += 1
        
        # Pagos recientes (últimos 30 días)
        today = timezone.now().date()
        month_ago = today - timezone.timedelta(days=30)
        recent_payments = queryset.filter(
            payment_date__gte=month_ago,
            payment_date__lte=today
        ).count()
        
        # Montos por método de pago
        from django.db.models import Sum
        payment_methods = queryset.values(
            'payment_method__name'
        ).annotate(
            total=Sum('amount')
        ).order_by('-total')
        
        return Response({
            'total_count': total_count,
            'total_amount': float(total_amount),
            'status_counts': status_counts,
            'recent_payments': recent_payments,
            'payment_methods': payment_methods
        })
