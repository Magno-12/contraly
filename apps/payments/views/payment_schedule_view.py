from rest_framework import status, permissions, filters
from rest_framework.viewsets import GenericViewSet
from rest_framework.response import Response
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q
from django.utils import timezone
import datetime
from dateutil.relativedelta import relativedelta

from apps.payments.models import PaymentSchedule
from apps.payments.serializers import (
    PaymentScheduleSerializer, PaymentScheduleCreateSerializer,
    PaymentScheduleBulkCreateSerializer
)
from apps.core.utils import create_audit_log, get_client_ip
from apps.core.permission import IsAdministrator
from apps.invoices.models import Invoice


class PaymentScheduleViewSet(GenericViewSet):
    """
    API endpoint para gestionar programaciones de pago
    """
    queryset = PaymentSchedule.objects.filter(is_deleted=False)
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['invoice', 'status', 'tenant']
    search_fields = ['notes', 'invoice__invoice_number']
    ordering_fields = ['due_date', 'installment_number', 'created_at']
    ordering = ['due_date']
    
    def get_serializer_class(self):
        if self.action == 'create':
            return PaymentScheduleCreateSerializer
        elif self.action == 'bulk_create':
            return PaymentScheduleBulkCreateSerializer
        return PaymentScheduleSerializer
    
    def get_permissions(self):
        """
        Permisos para gestionar programaciones de pago
        """
        if self.action in ['create', 'bulk_create', 'update', 'partial_update', 'destroy']:
            permission_classes = [permissions.IsAuthenticated, IsAdministrator]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        """
        Filtrar programaciones según permisos del usuario
        """
        queryset = super().get_queryset()
        user = self.request.user
        
        # Superusers ven todas las programaciones
        if user.is_superuser:
            return queryset
            
        # Administradores ven programaciones de su organización
        if hasattr(user, 'user_roles') and user.user_roles.filter(
            role__name='Administrator',
            is_active=True,
            is_deleted=False
        ).exists():
            if user.tenant:
                return queryset.filter(tenant=user.tenant)
        
        # Usuarios normales ven programaciones de facturas donde son emisores
        return queryset.filter(invoice__issuer=user)
    
    def list(self, request):
        """
        Listar programaciones de pago
        """
        queryset = self.filter_queryset(self.get_queryset())
        
        # Filtros adicionales
        invoice_id = request.query_params.get('invoice_id', None)
        if invoice_id:
            queryset = queryset.filter(invoice_id=invoice_id)
        
        # Filtro por estado
        status = request.query_params.get('status', None)
        if status:
            queryset = queryset.filter(status=status)
        
        # Filtro por fecha de vencimiento
        due_after = request.query_params.get('due_after', None)
        due_before = request.query_params.get('due_before', None)
        
        if due_after:
            queryset = queryset.filter(due_date__gte=due_after)
        if due_before:
            queryset = queryset.filter(due_date__lte=due_before)
        
        # Paginación
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
            
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    def retrieve(self, request, pk=None):
        """
        Obtener detalle de una programación de pago
        """
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
    
    def create(self, request):
        """
        Crear una nueva programación de pago
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Establecer tenant si no se proporciona
        if 'tenant' not in serializer.validated_data and request.user.tenant:
            serializer.validated_data['tenant'] = request.user.tenant
        
        # Crear programación
        schedule = serializer.save(
            created_by=request.user,
            updated_by=request.user
        )
        
        # Registrar creación
        create_audit_log(
            user=request.user,
            action='CREATE',
            model_name='PaymentSchedule',
            instance_id=schedule.id,
            description=f"Creación de programación de pago para factura {schedule.invoice.invoice_number}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            tenant=request.user.tenant
        )
        
        return Response(
            self.get_serializer(schedule).data,
            status=status.HTTP_201_CREATED
        )
    
    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        """
        Crear múltiples programaciones de pago
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        invoice_id = serializer.validated_data['invoice']
        total_amount = serializer.validated_data['total_amount']
        installments = serializer.validated_data['installments']
        start_date = serializer.validated_data['start_date']
        frequency = serializer.validated_data['frequency']
        custom_days = serializer.validated_data.get('custom_days')
        equal_amounts = serializer.validated_data.get('equal_amounts', True)
        notes = serializer.validated_data.get('notes', '')
        
        # Verificar que la factura existe
        try:
            invoice = Invoice.objects.get(id=invoice_id)
        except Invoice.DoesNotExist:
            return Response(
                {"detail": "La factura especificada no existe."},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Verificar que la factura no está pagada
        if invoice.is_paid:
            return Response(
                {"detail": "Esta factura ya está pagada."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verificar que no hay programaciones existentes
        if PaymentSchedule.objects.filter(invoice=invoice, is_deleted=False).exists():
            return Response(
                {"detail": "Esta factura ya tiene programaciones de pago."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Calcular fechas de vencimiento
        due_dates = []
        current_date = start_date
        
        for i in range(installments):
            due_dates.append(current_date)
            
            # Calcular siguiente fecha según frecuencia
            if frequency == 'MONTHLY':
                current_date = current_date + relativedelta(months=1)
            elif frequency == 'BIMONTHLY':
                current_date = current_date + relativedelta(months=2)
            elif frequency == 'QUARTERLY':
                current_date = current_date + relativedelta(months=3)
            elif frequency == 'SEMIANNUAL':
                current_date = current_date + relativedelta(months=6)
            elif frequency == 'ANNUAL':
                current_date = current_date + relativedelta(years=1)
            elif frequency == 'CUSTOM' and custom_days:
                current_date = current_date + datetime.timedelta(days=custom_days)
            else:
                # Por defecto, mensual
                current_date = current_date + relativedelta(months=1)
        
        # Calcular montos
        amounts = []
        if equal_amounts:
            # Dividir el monto total en partes iguales
            amount_per_installment = total_amount / installments
            
            # Ajustar para evitar errores de redondeo
            for i in range(installments - 1):
                amounts.append(round(amount_per_installment, 2))
            
            # El último pago ajusta cualquier diferencia por redondeo
            amounts.append(round(total_amount - sum(amounts), 2))
        else:
            # Implementar alguna lógica personalizada si se requiere
            # Por ahora, simplemente dividimos en partes iguales
            amount_per_installment = total_amount / installments
            
            for i in range(installments - 1):
                amounts.append(round(amount_per_installment, 2))
            
            amounts.append(round(total_amount - sum(amounts), 2))
        
        # Crear las programaciones
        created_schedules = []
        for i in range(installments):
            schedule = PaymentSchedule.objects.create(
                invoice=invoice,
                due_date=due_dates[i],
                amount=amounts[i],
                installment_number=i + 1,
                total_installments=installments,
                notes=notes,
                tenant=request.user.tenant,
                created_by=request.user,
                updated_by=request.user
            )
            created_schedules.append(schedule)
        
        # Registrar creación
        create_audit_log(
            user=request.user,
            action='CREATE',
            model_name='PaymentSchedule',
            instance_id=None,
            description=f"Creación masiva de {installments} programaciones de pago para factura {invoice.invoice_number}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            tenant=request.user.tenant
        )
        
        return Response({
            "detail": f"Se crearon {len(created_schedules)} programaciones de pago.",
            "schedules": PaymentScheduleSerializer(created_schedules, many=True).data
        })
    
    def update(self, request, pk=None):
        """
        Actualizar una programación de pago
        """
        instance = self.get_object()
        
        # Verificar que no esté pagada
        if instance.status == 'PAID':
            return Response(
                {"detail": "No se puede modificar una programación que ya ha sido pagada."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = self.get_serializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        schedule = serializer.save(updated_by=request.user)
        
        # Actualizar estado
        schedule.update_status()
        
        # Registrar actualización
        create_audit_log(
            user=request.user,
            action='UPDATE',
            model_name='PaymentSchedule',
            instance_id=schedule.id,
            description=f"Actualización de programación de pago para factura {schedule.invoice.invoice_number}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            tenant=request.user.tenant
        )
        
        return Response(self.get_serializer(schedule).data)
    
    def partial_update(self, request, pk=None):
        """
        Actualizar parcialmente una programación de pago
        """
        instance = self.get_object()
        
        # Verificar que no esté pagada
        if instance.status == 'PAID':
            return Response(
                {"detail": "No se puede modificar una programación que ya ha sido pagada."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        schedule = serializer.save(updated_by=request.user)
        
        # Actualizar estado
        schedule.update_status()
        
        # Registrar actualización
        create_audit_log(
            user=request.user,
            action='UPDATE',
            model_name='PaymentSchedule',
            instance_id=schedule.id,
            description=f"Actualización parcial de programación de pago para factura {schedule.invoice.invoice_number}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            tenant=request.user.tenant
        )
        
        return Response(self.get_serializer(schedule).data)
    
    def destroy(self, request, pk=None):
        """
        Eliminar (soft delete) una programación de pago
        """
        instance = self.get_object()
        
        # Verificar que no esté pagada
        if instance.status == 'PAID':
            return Response(
                {"detail": "No se puede eliminar una programación que ya ha sido pagada."},
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
            model_name='PaymentSchedule',
            instance_id=instance.id,
            description=f"Eliminación de programación de pago para factura {instance.invoice.invoice_number}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            tenant=request.user.tenant
        )
        
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    @action(detail=True, methods=['post'])
    def update_status(self, request, pk=None):
        """
        Actualizar el estado de una programación de pago
        """
        schedule = self.get_object()
        schedule.update_status()
        
        return Response({
            "detail": "Estado actualizado correctamente.",
            "schedule": self.get_serializer(schedule).data
        })
    
    @action(detail=False, methods=['get'])
    def by_invoice(self, request):
        """
        Obtener programaciones para una factura específica
        """
        invoice_id = request.query_params.get('invoice_id')
        if not invoice_id:
            return Response(
                {"detail": "Se requiere el parámetro invoice_id."},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        queryset = self.get_queryset().filter(invoice_id=invoice_id)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def upcoming(self, request):
        """
        Obtener programaciones próximas a vencer
        """
        today = timezone.now().date()
        days = int(request.query_params.get('days', 30))
        future_date = today + datetime.timedelta(days=days)
        
        queryset = self.get_queryset().filter(
            Q(status='PENDING') | Q(status='PARTIALLY_PAID'),
            due_date__gte=today,
            due_date__lte=future_date
        ).order_by('due_date')
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def overdue(self, request):
        """
        Obtener programaciones vencidas
        """
        today = timezone.now().date()
        
        queryset = self.get_queryset().filter(
            Q(status='PENDING') | Q(status='PARTIALLY_PAID'),
            due_date__lt=today
        ).order_by('due_date')
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
