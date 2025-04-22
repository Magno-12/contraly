from rest_framework import status, permissions, filters
from rest_framework.viewsets import GenericViewSet
from rest_framework.response import Response
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.db.models import Q
import datetime
from dateutil.relativedelta import relativedelta

from apps.invoices.models import InvoiceSchedule, Invoice, InvoiceStatus, InvoiceItem
from apps.invoices.serializers import InvoiceScheduleSerializer
from apps.core.utils import create_audit_log, get_client_ip
from apps.core.permission import IsAdministrator


class InvoiceScheduleViewSet(GenericViewSet):
    """
    API endpoint para gestionar programaciones de cuentas de cobro recurrentes
    """
    queryset = InvoiceSchedule.objects.filter(is_deleted=False)
    serializer_class = InvoiceScheduleSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['contract', 'schedule_type', 'is_active', 'tenant']
    search_fields = ['name', 'description']
    ordering_fields = ['start_date', 'next_generation', 'created_at']
    ordering = ['next_generation', 'start_date']
    
    def get_permissions(self):
        """
        Permisos para gestionar programaciones
        """
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
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
        
        # Usuarios normales ven programaciones de contratos donde son supervisores
        contract_ids = user.supervised_contracts.filter(
            is_active=True,
            is_deleted=False
        ).values_list('id', flat=True)
        
        return queryset.filter(contract_id__in=contract_ids)
    
    def list(self, request):
        """
        Listar programaciones de cuentas de cobro
        """
        queryset = self.filter_queryset(self.get_queryset())
        
        # Filtros adicionales
        is_active_only = request.query_params.get('is_active_only', None)
        if is_active_only and is_active_only.lower() == 'true':
            queryset = queryset.filter(is_active=True)
        
        # Filtro por fecha de próxima generación
        next_before = request.query_params.get('next_before', None)
        if next_before:
            queryset = queryset.filter(next_generation__lte=next_before)
            
        # Filtro por contrato
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
        Obtener detalle de una programación
        """
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
    
    def create(self, request):
        """
        Crear una nueva programación de cuentas de cobro
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
            model_name='InvoiceSchedule',
            instance_id=schedule.id,
            description=f"Creación de programación de cuentas de cobro: {schedule.name}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            tenant=request.user.tenant
        )
        
        return Response(
            self.get_serializer(schedule).data,
            status=status.HTTP_201_CREATED
        )
    
    def update(self, request, pk=None):
        """
        Actualizar una programación existente
        """
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        schedule = serializer.save(updated_by=request.user)
        
        # Registrar actualización
        create_audit_log(
            user=request.user,
            action='UPDATE',
            model_name='InvoiceSchedule',
            instance_id=schedule.id,
            description=f"Actualización de programación de cuentas de cobro: {schedule.name}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            tenant=request.user.tenant
        )
        
        return Response(serializer.data)
    
    def partial_update(self, request, pk=None):
        """
        Actualizar parcialmente una programación
        """
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        schedule = serializer.save(updated_by=request.user)
        
        # Registrar actualización
        create_audit_log(
            user=request.user,
            action='UPDATE',
            model_name='InvoiceSchedule',
            instance_id=schedule.id,
            description=f"Actualización parcial de programación de cuentas de cobro: {schedule.name}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            tenant=request.user.tenant
        )
        
        return Response(serializer.data)
    
    def destroy(self, request, pk=None):
        """
        Eliminar (soft delete) una programación
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
            model_name='InvoiceSchedule',
            instance_id=instance.id,
            description=f"Eliminación de programación de cuentas de cobro: {instance.name}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            tenant=request.user.tenant
        )
        
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    @action(detail=False, methods=['get'])
    def schedule_types(self, request):
        """
        Obtener lista de tipos de programación
        """
        return Response([
            {'value': choice[0], 'label': choice[1]}
            for choice in InvoiceSchedule.SCHEDULE_TYPES
        ])
    
    @action(detail=True, methods=['post'])
    def generate_invoice(self, request, pk=None):
        """
        Generar manualmente una cuenta de cobro basada en la programación
        """
        schedule = self.get_object()
        
        # Verificar que la programación esté activa
        if not schedule.is_active:
            return Response(
                {"detail": "No se puede generar una cuenta de cobro para una programación inactiva."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verificar que el contrato siga activo
        contract = schedule.contract
        if not contract.is_active or contract.is_deleted:
            return Response(
                {"detail": "No se puede generar una cuenta de cobro para un contrato inactivo."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verificar si ya pasó la fecha de fin
        today = timezone.now().date()
        if schedule.end_date and schedule.end_date < today:
            return Response(
                {"detail": "Esta programación ya ha finalizado y no puede generar más cuentas."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Generar cuenta de cobro
        invoice = self._create_invoice_from_schedule(schedule)
        
        # Actualizar fecha de última y próxima generación
        schedule.last_generated = today
        schedule.next_generation = schedule.calculate_next_generation()
        schedule.save()
        
        # Registrar generación
        create_audit_log(
            user=request.user,
            action='CREATE',
            model_name='Invoice',
            instance_id=invoice.id,
            description=f"Generación manual de cuenta de cobro {invoice.invoice_number} desde programación",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            tenant=request.user.tenant
        )
        
        # Devolver datos de la cuenta generada
        from apps.invoices.serializers import InvoiceDetailSerializer
        return Response({
            "detail": "Cuenta de cobro generada exitosamente.",
            "invoice": InvoiceDetailSerializer(invoice).data
        })
    
    @action(detail=False, methods=['post'])
    def process_scheduled(self, request):
        """
        Procesar todas las programaciones pendientes de generación
        """
        # Solo administradores pueden ejecutar este proceso
        if not (
            request.user.is_superuser or (
                hasattr(request.user, 'user_roles') and request.user.user_roles.filter(
                    role__name='Administrator',
                    is_active=True,
                    is_deleted=False
                ).exists()
            )
        ):
            return Response(
                {"detail": "No tiene permisos para ejecutar este proceso."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Filtrar programaciones a procesar
        today = timezone.now().date()
        
        # Programaciones activas con fecha de próxima generación menor o igual a hoy
        schedules = InvoiceSchedule.objects.filter(
            is_active=True,
            is_deleted=False,
            is_auto_generate=True,
            next_generation__lte=today
        )
        
        # Aplicar filtro por tenant según el usuario
        if not request.user.is_superuser and request.user.tenant:
            schedules = schedules.filter(tenant=request.user.tenant)
        
        # Procesar cada programación
        results = []
        for schedule in schedules:
            try:
                # Verificar que el contrato siga activo
                contract = schedule.contract
                if not contract.is_active or contract.is_deleted:
                    results.append({
                        "schedule_id": str(schedule.id),
                        "schedule_name": schedule.name,
                        "success": False,
                        "message": "Contrato inactivo"
                    })
                    continue
                
                # Verificar si ya pasó la fecha de fin
                if schedule.end_date and schedule.end_date < today:
                    results.append({
                        "schedule_id": str(schedule.id),
                        "schedule_name": schedule.name,
                        "success": False,
                        "message": "Programación finalizada"
                    })
                    continue
                
                # Generar cuenta de cobro
                invoice = self._create_invoice_from_schedule(schedule)
                
                # Actualizar fecha de última y próxima generación
                schedule.last_generated = today
                schedule.next_generation = schedule.calculate_next_generation()
                schedule.save()
                
                # Registrar éxito
                results.append({
                    "schedule_id": str(schedule.id),
                    "schedule_name": schedule.name,
                    "success": True,
                    "invoice_id": str(invoice.id),
                    "invoice_number": invoice.invoice_number
                })
                
                # Registrar generación
                create_audit_log(
                    user=request.user,
                    action='CREATE',
                    model_name='Invoice',
                    instance_id=invoice.id,
                    description=f"Generación automática de cuenta de cobro {invoice.invoice_number} desde programación",
                    ip_address=get_client_ip(request),
                    user_agent=request.META.get('HTTP_USER_AGENT', ''),
                    tenant=schedule.tenant
                )
                
            except Exception as e:
                # Registrar error
                results.append({
                    "schedule_id": str(schedule.id),
                    "schedule_name": schedule.name,
                    "success": False,
                    "message": str(e)
                })
        
        return Response({
            "processed": len(schedules),
            "successful": sum(1 for r in results if r.get('success')),
            "failed": sum(1 for r in results if not r.get('success')),
            "results": results
        })
    
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """
        Activar una programación
        """
        schedule = self.get_object()
        
        if schedule.is_active:
            return Response(
                {"detail": "Esta programación ya está activa."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        schedule.is_active = True
        schedule.updated_by = request.user
        
        # Recalcular próxima fecha de generación
        today = timezone.now().date()
        if not schedule.next_generation or schedule.next_generation < today:
            schedule.next_generation = schedule.calculate_next_generation()
        
        schedule.save()
        
        # Registrar activación
        create_audit_log(
            user=request.user,
            action='UPDATE',
            model_name='InvoiceSchedule',
            instance_id=schedule.id,
            description=f"Activación de programación de cuentas de cobro: {schedule.name}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            tenant=request.user.tenant
        )
        
        return Response(self.get_serializer(schedule).data)
    
    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """
        Desactivar una programación
        """
        schedule = self.get_object()
        
        if not schedule.is_active:
            return Response(
                {"detail": "Esta programación ya está inactiva."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        schedule.is_active = False
        schedule.updated_by = request.user
        schedule.save()
        
        # Registrar desactivación
        create_audit_log(
            user=request.user,
            action='UPDATE',
            model_name='InvoiceSchedule',
            instance_id=schedule.id,
            description=f"Desactivación de programación de cuentas de cobro: {schedule.name}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            tenant=request.user.tenant
        )
        
        return Response(self.get_serializer(schedule).data)
    
    def _create_invoice_from_schedule(self, schedule):
        """
        Método interno para crear una cuenta de cobro a partir de una programación
        """
        # Obtener contrato
        contract = schedule.contract
        
        # Determinar el período de la cuenta
        today = timezone.now().date()
        
        # Calcular fecha de inicio y fin del período según tipo de programación
        if schedule.schedule_type == 'WEEKLY':
            period_start = today
            period_end = today + datetime.timedelta(days=6)
        elif schedule.schedule_type == 'BIWEEKLY':
            period_start = today
            period_end = today + datetime.timedelta(days=13)
        elif schedule.schedule_type == 'MONTHLY':
            period_start = today
            period_end = today + relativedelta(months=1) - datetime.timedelta(days=1)
        elif schedule.schedule_type == 'BIMONTHLY':
            period_start = today
            period_end = today + relativedelta(months=2) - datetime.timedelta(days=1)
        elif schedule.schedule_type == 'QUARTERLY':
            period_start = today
            period_end = today + relativedelta(months=3) - datetime.timedelta(days=1)
        elif schedule.schedule_type == 'SEMIANNUAL':
            period_start = today
            period_end = today + relativedelta(months=6) - datetime.timedelta(days=1)
        elif schedule.schedule_type == 'ANNUAL':
            period_start = today
            period_end = today + relativedelta(years=1) - datetime.timedelta(days=1)
        elif schedule.schedule_type == 'CUSTOM' and schedule.custom_days:
            period_start = today
            period_end = today + datetime.timedelta(days=schedule.custom_days - 1)
        else:
            # Por defecto, un mes
            period_start = today
            period_end = today + relativedelta(months=1) - datetime.timedelta(days=1)
        
        # Generador de número de factura
        # Formato: YYYY-MM-SEC-#### (Año-Mes-Secuencial-ContractNumber)
        year_month = today.strftime('%Y-%m')
        seq_number = Invoice.objects.filter(
            invoice_number__startswith=f"{year_month}-",
            tenant=schedule.tenant
        ).count() + 1
        
        invoice_number = f"{year_month}-{seq_number:03d}-{contract.contract_number}"
        
        # Crear la cuenta de cobro
        invoice = Invoice.objects.create(
            invoice_number=invoice_number,
            title=f"Cuenta de cobro {schedule.name} - {period_start.strftime('%d/%m/%Y')} a {period_end.strftime('%d/%m/%Y')}",
            contract=contract,
            issuer=contract.supervisor or schedule.created_by,
            recipient_type='ORGANIZATION',
            recipient_organization=contract.tenant,
            issue_date=today,
            due_date=today + datetime.timedelta(days=30),  # 30 días para pago
            period_start=period_start,
            period_end=period_end,
            subtotal=schedule.value,
            tax_amount=0,
            discount_amount=0,
            total_amount=schedule.value,
            currency=contract.currency,
            notes=f"Cuenta de cobro generada automáticamente desde programación '{schedule.name}'",
            payment_terms="30 días",
            reference=f"Programación-{schedule.id}",
            tenant=schedule.tenant,
            created_by=schedule.created_by,
            updated_by=schedule.created_by
        )
        
        # Crear el ítem principal
        InvoiceItem.objects.create(
            invoice=invoice,
            description=f"Servicios según contrato {contract.contract_number} para el período {period_start.strftime('%d/%m/%Y')} a {period_end.strftime('%d/%m/%Y')}",
            quantity=1,
            unit_price=schedule.value,
            tax_percentage=0,
            tax_amount=0,
            discount_percentage=0,
            discount_amount=0,
            subtotal=schedule.value,
            total=schedule.value,
            contract_item=contract.title,
            order=1,
            tenant=schedule.tenant,
            created_by=schedule.created_by,
            updated_by=schedule.created_by
        )
        
        # Crear estado inicial
        InvoiceStatus.objects.create(
            invoice=invoice,
            status='DRAFT',
            comments="Generado automáticamente desde programación",
            changed_by=schedule.created_by,
            created_by=schedule.created_by,
            updated_by=schedule.created_by,
            tenant=schedule.tenant
        )
        
        # Si la configuración indica aprobar automáticamente
        if schedule.auto_approve:
            # Cambiar a estado SUBMITTED
            InvoiceStatus.objects.create(
                invoice=invoice,
                status='SUBMITTED',
                comments="Enviado automáticamente desde programación",
                changed_by=schedule.created_by,
                created_by=schedule.created_by,
                updated_by=schedule.created_by,
                tenant=schedule.tenant
            )
            
            # Cambiar a estado REVIEW
            InvoiceStatus.objects.create(
                invoice=invoice,
                status='REVIEW',
                comments="En revisión automáticamente desde programación",
                changed_by=schedule.created_by,
                created_by=schedule.created_by,
                updated_by=schedule.created_by,
                tenant=schedule.tenant
            )
            
            # Cambiar a estado PENDING_APPROVAL
            InvoiceStatus.objects.create(
                invoice=invoice,
                status='PENDING_APPROVAL',
                comments="Pendiente de aprobación automáticamente desde programación",
                changed_by=schedule.created_by,
                created_by=schedule.created_by,
                updated_by=schedule.created_by,
                tenant=schedule.tenant
            )
            
            # Cambiar a estado APPROVED
            InvoiceStatus.objects.create(
                invoice=invoice,
                status='APPROVED',
                comments="Aprobado automáticamente desde programación",
                changed_by=schedule.created_by,
                created_by=schedule.created_by,
                updated_by=schedule.created_by,
                tenant=schedule.tenant
            )
        
        return invoice
