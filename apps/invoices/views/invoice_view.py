from rest_framework import status, permissions, filters
from rest_framework.viewsets import GenericViewSet
from rest_framework.response import Response
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Sum
from django.utils import timezone

from apps.invoices.models import Invoice, InvoiceItem, InvoiceStatus, InvoiceApproval
from apps.invoices.serializers import (
    InvoiceSerializer, InvoiceListSerializer, InvoiceDetailSerializer, 
    InvoiceCreateSerializer, InvoiceStatusSerializer
)
from apps.core.utils import create_audit_log, get_client_ip
from apps.core.permission import IsAdministrator


class InvoiceViewSet(GenericViewSet):
    """
    API endpoint para gestionar cuentas de cobro
    """
    queryset = Invoice.objects.filter(is_deleted=False)
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['issuer', 'recipient_type', 'recipient_organization', 
                       'recipient_user', 'is_paid', 'contract', 'tenant']
    search_fields = ['invoice_number', 'title', 'reference', 'notes']
    ordering_fields = ['issue_date', 'due_date', 'total_amount', 'created_at']
    ordering = ['-issue_date']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return InvoiceListSerializer
        elif self.action == 'retrieve':
            return InvoiceDetailSerializer
        elif self.action == 'create':
            return InvoiceCreateSerializer
        return InvoiceSerializer
    
    def get_permissions(self):
        """
        Instantiates and returns the list of permissions that this view requires.
        """
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [permissions.IsAuthenticated, IsAdministrator]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        """
        Filtrar cuentas de cobro según permisos del usuario
        """
        queryset = super().get_queryset()
        user = self.request.user
        
        # Superusers ven todas las cuentas de cobro
        if user.is_superuser:
            return queryset
            
        # Administradores ven las cuentas de cobro de su organización
        if hasattr(user, 'user_roles') and user.user_roles.filter(
            role__name='Administrator',
            is_active=True,
            is_deleted=False
        ).exists():
            if user.tenant:
                return queryset.filter(tenant=user.tenant)
            
        # Los usuarios ven las cuentas de cobro donde son emisores o receptores
        issuer_invoices = queryset.filter(issuer=user)
        recipient_invoices = queryset.filter(
            Q(recipient_type='USER', recipient_user=user) |
            Q(recipient_type='ORGANIZATION', recipient_organization=user.tenant)
        )
        
        # Combinar y eliminar duplicados
        return (issuer_invoices | recipient_invoices).distinct()
    
    def list(self, request):
        """
        Listar cuentas de cobro con filtros
        """
        queryset = self.filter_queryset(self.get_queryset())
        
        # Filtro por estado actual
        status = request.query_params.get('status', None)
        if status:
            invoice_ids = InvoiceStatus.objects.filter(
                status=status,
                is_active=True,
                is_deleted=False,
                end_date__isnull=True  # Es el estado actual
            ).values_list('invoice_id', flat=True)
            queryset = queryset.filter(id__in=invoice_ids)
        
        # Filtro por fecha
        issue_after = request.query_params.get('issue_after', None)
        issue_before = request.query_params.get('issue_before', None)
        due_after = request.query_params.get('due_after', None)
        due_before = request.query_params.get('due_before', None)
        
        if issue_after:
            queryset = queryset.filter(issue_date__gte=issue_after)
        if issue_before:
            queryset = queryset.filter(issue_date__lte=issue_before)
        if due_after:
            queryset = queryset.filter(due_date__gte=due_after)
        if due_before:
            queryset = queryset.filter(due_date__lte=due_before)
        
        # Filtro por término de búsqueda general
        search = request.query_params.get('q', None)
        if search:
            queryset = queryset.filter(
                Q(invoice_number__icontains=search) |
                Q(title__icontains=search) |
                Q(reference__icontains=search) |
                Q(notes__icontains=search)
            )
            
        # Paginación
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
            
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    def retrieve(self, request, pk=None):
        """
        Obtener detalle de una cuenta de cobro
        """
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        
        # Registrar visualización
        create_audit_log(
            user=request.user,
            action='VIEW',
            model_name='Invoice',
            instance_id=instance.id,
            description=f"Visualización de cuenta de cobro {instance.invoice_number}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            tenant=request.user.tenant
        )
        
        return Response(serializer.data)
    
    def create(self, request):
        """
        Crear una nueva cuenta de cobro
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Establecer tenant si no se proporciona
        if 'tenant' not in serializer.validated_data and request.user.tenant:
            serializer.validated_data['tenant'] = request.user.tenant
        
        # Crear cuenta de cobro
        invoice = serializer.save(
            created_by=request.user,
            updated_by=request.user
        )
        
        # Registrar creación
        create_audit_log(
            user=request.user,
            action='CREATE',
            model_name='Invoice',
            instance_id=invoice.id,
            description=f"Creación de cuenta de cobro {invoice.invoice_number}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            data=request.data,
            tenant=request.user.tenant
        )
        
        return Response(
            InvoiceDetailSerializer(invoice).data,
            status=status.HTTP_201_CREATED
        )
    
    def update(self, request, pk=None):
        """
        Actualizar una cuenta de cobro existente
        """
        instance = self.get_object()
        
        # Verificar que la cuenta no esté pagada
        if instance.is_paid:
            return Response(
                {"detail": "No se puede editar una cuenta de cobro que ya ha sido pagada."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verificar que el estado permita edición
        current_status = instance.current_status
        if current_status and current_status.status not in ['DRAFT', 'REVIEW', 'REJECTED']:
            return Response(
                {"detail": f"No se puede editar una cuenta en estado {current_status.get_status_display()}."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = self.get_serializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        invoice = serializer.save(updated_by=request.user)
        
        # Registrar actualización
        create_audit_log(
            user=request.user,
            action='UPDATE',
            model_name='Invoice',
            instance_id=invoice.id,
            description=f"Actualización de cuenta de cobro {invoice.invoice_number}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            data=request.data,
            tenant=request.user.tenant
        )
        
        return Response(InvoiceDetailSerializer(invoice).data)
    
    def partial_update(self, request, pk=None):
        """
        Actualizar parcialmente una cuenta de cobro
        """
        instance = self.get_object()
        
        # Verificar que la cuenta no esté pagada
        if instance.is_paid:
            return Response(
                {"detail": "No se puede editar una cuenta de cobro que ya ha sido pagada."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verificar que el estado permita edición
        current_status = instance.current_status
        if current_status and current_status.status not in ['DRAFT', 'REVIEW', 'REJECTED']:
            return Response(
                {"detail": f"No se puede editar una cuenta en estado {current_status.get_status_display()}."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        invoice = serializer.save(updated_by=request.user)
        
        # Registrar actualización
        create_audit_log(
            user=request.user,
            action='UPDATE',
            model_name='Invoice',
            instance_id=invoice.id,
            description=f"Actualización parcial de cuenta de cobro {invoice.invoice_number}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            data=request.data,
            tenant=request.user.tenant
        )
        
        return Response(InvoiceDetailSerializer(invoice).data)
    
    def destroy(self, request, pk=None):
        """
        Eliminar (soft delete) una cuenta de cobro
        """
        instance = self.get_object()
        
        # Verificar que la cuenta no esté pagada
        if instance.is_paid:
            return Response(
                {"detail": "No se puede eliminar una cuenta de cobro que ya ha sido pagada."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verificar que el estado permita eliminación
        current_status = instance.current_status
        if current_status and current_status.status not in ['DRAFT', 'REJECTED', 'CANCELLED']:
            return Response(
                {"detail": f"No se puede eliminar una cuenta en estado {current_status.get_status_display()}."},
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
            model_name='Invoice',
            instance_id=instance.id,
            description=f"Eliminación de cuenta de cobro {instance.invoice_number}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            tenant=request.user.tenant
        )
        
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    @action(detail=True, methods=['get'])
    def items(self, request, pk=None):
        """
        Obtener ítems de una cuenta de cobro
        """
        invoice = self.get_object()
        from apps.invoices.serializers import InvoiceItemSerializer
        
        items = InvoiceItem.objects.filter(
            invoice=invoice,
            is_active=True,
            is_deleted=False
        ).order_by('order')
        
        serializer = InvoiceItemSerializer(items, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def status_history(self, request, pk=None):
        """
        Obtener historial de estados de una cuenta de cobro
        """
        invoice = self.get_object()
        from apps.invoices.serializers import InvoiceStatusSerializer
        
        statuses = InvoiceStatus.objects.filter(
            invoice=invoice,
            is_active=True,
            is_deleted=False
        ).order_by('-start_date')
        
        serializer = InvoiceStatusSerializer(statuses, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def approvals(self, request, pk=None):
        """
        Obtener aprobaciones de una cuenta de cobro
        """
        invoice = self.get_object()
        from apps.invoices.serializers import InvoiceApprovalSerializer
        
        approvals = InvoiceApproval.objects.filter(
            invoice=invoice,
            is_active=True,
            is_deleted=False
        ).order_by('approval_type')
        
        serializer = InvoiceApprovalSerializer(approvals, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def change_status(self, request, pk=None):
        """
        Cambiar el estado de una cuenta de cobro
        """
        invoice = self.get_object()
        from apps.invoices.serializers import InvoiceStatusSerializer
        
        # Validar datos del nuevo estado
        serializer = InvoiceStatusSerializer(data={
            'invoice': invoice.id,
            'status': request.data.get('status'),
            'comments': request.data.get('comments', ''),
            'tenant': invoice.tenant.id if invoice.tenant else None
        })
        serializer.is_valid(raise_exception=True)
        serializer.context['request'] = request
        
        # Validar transición de estado
        new_status = request.data.get('status')
        current_status = invoice.current_status
        current_status_code = current_status.status if current_status else None
        
        # Definir transiciones válidas
        valid_transitions = {
            'DRAFT': ['SUBMITTED', 'CANCELLED'],
            'SUBMITTED': ['REVIEW', 'DRAFT', 'CANCELLED'],
            'REVIEW': ['PENDING_APPROVAL', 'DRAFT', 'REJECTED', 'CANCELLED'],
            'PENDING_APPROVAL': ['APPROVED', 'REJECTED', 'CANCELLED'],
            'APPROVED': ['PAID', 'CANCELLED'],
            'REJECTED': ['DRAFT', 'CANCELLED'],
            'PAID': ['ARCHIVED'],
            'CANCELLED': ['ARCHIVED'],
            'ARCHIVED': []
        }
        
        # Si no hay estado actual, cualquier estado inicial es válido
        if not current_status_code:
            valid_initial_states = ['DRAFT', 'SUBMITTED']
            if new_status not in valid_initial_states:
                return Response(
                    {"detail": f"Para una cuenta nueva, solo se permiten los estados iniciales: {', '.join(valid_initial_states)}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        # Verificar si la transición es válida desde el estado actual
        elif new_status not in valid_transitions.get(current_status_code, []):
            return Response(
                {"detail": f"No se puede cambiar del estado '{current_status_code}' al estado '{new_status}'. Transiciones válidas: {', '.join(valid_transitions.get(current_status_code, []))}"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Crear el nuevo estado
        status_obj = serializer.save(
            created_by=request.user,
            updated_by=request.user,
            changed_by=request.user
        )
        
        # Si el estado es PAID, actualizar la factura
        if new_status == 'PAID' and not invoice.is_paid:
            invoice.is_paid = True
            invoice.payment_date = timezone.now().date()
            invoice.save(update_fields=['is_paid', 'payment_date', 'updated_by', 'updated_at'])
        
        # Registrar cambio de estado
        create_audit_log(
            user=request.user,
            action='UPDATE',
            model_name='InvoiceStatus',
            instance_id=status_obj.id,
            description=f"Cambio de estado de cuenta de cobro {invoice.invoice_number} a {status_obj.get_status_display()}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            tenant=request.user.tenant
        )
        
        return Response(InvoiceStatusSerializer(status_obj).data)
    
    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """
        Enviar una cuenta de cobro para revisión
        """
        invoice = self.get_object()
        
        # Verificar que la cuenta esté en estado borrador
        current_status = invoice.current_status
        if not current_status or current_status.status != 'DRAFT':
            return Response(
                {"detail": "Solo se pueden enviar cuentas de cobro en estado borrador."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verificar que la cuenta tenga ítems
        if not invoice.items.filter(is_active=True, is_deleted=False).exists():
            return Response(
                {"detail": "No se puede enviar una cuenta de cobro sin ítems."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Cambiar estado a enviado
        from apps.invoices.models import InvoiceStatus
        status_obj = InvoiceStatus.objects.create(
            invoice=invoice,
            status='SUBMITTED',
            comments=request.data.get('comments', 'Cuenta de cobro enviada para revisión'),
            changed_by=request.user,
            created_by=request.user,
            updated_by=request.user,
            tenant=invoice.tenant
        )
        
        # Registrar acción
        create_audit_log(
            user=request.user,
            action='UPDATE',
            model_name='Invoice',
            instance_id=invoice.id,
            description=f"Cuenta de cobro {invoice.invoice_number} enviada para revisión",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            tenant=request.user.tenant
        )
        
        return Response({
            "detail": "Cuenta de cobro enviada correctamente para revisión.",
            "status": InvoiceStatusSerializer(status_obj).data
        })
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """
        Aprobar una cuenta de cobro
        """
        invoice = self.get_object()
        
        # Verificar que la cuenta esté en estado pendiente de aprobación
        current_status = invoice.current_status
        if not current_status or current_status.status != 'PENDING_APPROVAL':
            return Response(
                {"detail": "Solo se pueden aprobar cuentas de cobro en estado pendiente de aprobación."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verificar que el usuario tenga permisos para aprobar
        if not (
            request.user.is_superuser or 
            (hasattr(request.user, 'user_roles') and request.user.user_roles.filter(
                role__role_permissions__permission__code='invoices.approve_invoice',
                is_active=True,
                is_deleted=False
            ).exists())
        ):
            return Response(
                {"detail": "No tiene permisos para aprobar cuentas de cobro."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Cambiar estado a aprobado
        from apps.invoices.models import InvoiceStatus, InvoiceApproval
        status_obj = InvoiceStatus.objects.create(
            invoice=invoice,
            status='APPROVED',
            comments=request.data.get('comments', 'Cuenta de cobro aprobada'),
            changed_by=request.user,
            created_by=request.user,
            updated_by=request.user,
            tenant=invoice.tenant
        )
        
        # Registrar aprobación
        InvoiceApproval.objects.create(
            invoice=invoice,
            approval_type='FINAL_APPROVAL',
            approver=request.user,
            result='APPROVED',
            approval_date=timezone.now(),
            comments=request.data.get('comments', 'Cuenta de cobro aprobada'),
            created_by=request.user,
            updated_by=request.user,
            tenant=invoice.tenant
        )
        
        # Registrar acción
        create_audit_log(
            user=request.user,
            action='APPROVE',
            model_name='Invoice',
            instance_id=invoice.id,
            description=f"Cuenta de cobro {invoice.invoice_number} aprobada",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            tenant=request.user.tenant
        )
        
        return Response({
            "detail": "Cuenta de cobro aprobada correctamente.",
            "status": InvoiceStatusSerializer(status_obj).data
        })
    
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """
        Rechazar una cuenta de cobro
        """
        invoice = self.get_object()
        
        # Verificar que la cuenta esté en un estado que permita rechazo
        current_status = invoice.current_status
        if not current_status or current_status.status not in ['REVIEW', 'PENDING_APPROVAL']:
            return Response(
                {"detail": f"No se puede rechazar una cuenta en estado {current_status.get_status_display() if current_status else 'desconocido'}."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verificar que el usuario tenga permisos para rechazar
        if not (
            request.user.is_superuser or 
            (hasattr(request.user, 'user_roles') and request.user.user_roles.filter(
                role__role_permissions__permission__code__in=['invoices.approve_invoice', 'invoices.review_invoice'],
                is_active=True,
                is_deleted=False
            ).exists())
        ):
            return Response(
                {"detail": "No tiene permisos para rechazar cuentas de cobro."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Verificar que se proporcionó un motivo de rechazo
        if not request.data.get('comments'):
            return Response(
                {"detail": "Debe proporcionar un motivo para el rechazo."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Cambiar estado a rechazado
        from apps.invoices.models import InvoiceStatus, InvoiceApproval
        status_obj = InvoiceStatus.objects.create(
            invoice=invoice,
            status='REJECTED',
            comments=request.data.get('comments'),
            changed_by=request.user,
            created_by=request.user,
            updated_by=request.user,
            tenant=invoice.tenant
        )
        
        # Registrar rechazo
        approval_type = 'FIRST_APPROVAL' if current_status.status == 'REVIEW' else 'FINAL_APPROVAL'
        InvoiceApproval.objects.create(
            invoice=invoice,
            approval_type=approval_type,
            approver=request.user,
            result='REJECTED',
            approval_date=timezone.now(),
            comments=request.data.get('comments'),
            created_by=request.user,
            updated_by=request.user,
            tenant=invoice.tenant
        )
        
        # Registrar acción
        create_audit_log(
            user=request.user,
            action='REJECT',
            model_name='Invoice',
            instance_id=invoice.id,
            description=f"Cuenta de cobro {invoice.invoice_number} rechazada",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            tenant=request.user.tenant
        )
        
        return Response({
            "detail": "Cuenta de cobro rechazada.",
            "status": InvoiceStatusSerializer(status_obj).data
        })
    
    @action(detail=True, methods=['post'])
    def mark_as_paid(self, request, pk=None):
        """
        Marcar una cuenta de cobro como pagada
        """
        invoice = self.get_object()
        
        # Verificar que la cuenta esté en estado aprobado
        current_status = invoice.current_status
        if not current_status or current_status.status != 'APPROVED':
            return Response(
                {"detail": "Solo se pueden marcar como pagadas las cuentas de cobro aprobadas."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verificar que el usuario tenga permisos para marcar como pagada
        if not (
            request.user.is_superuser or 
            (hasattr(request.user, 'user_roles') and request.user.user_roles.filter(
                role__role_permissions__permission__code='invoices.register_payment',
                is_active=True,
                is_deleted=False
            ).exists())
        ):
            return Response(
                {"detail": "No tiene permisos para registrar pagos."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Establecer la fecha de pago si se proporciona, sino usar fecha actual
        payment_date = request.data.get('payment_date', timezone.now().date())
        
        # Actualizar la cuenta de cobro
        invoice.is_paid = True
        invoice.payment_date = payment_date
        invoice.updated_by = request.user
        invoice.save()
        
        # Cambiar estado a pagado
        from apps.invoices.models import InvoiceStatus
        status_obj = InvoiceStatus.objects.create(
            invoice=invoice,
            status='PAID',
            comments=request.data.get('comments', 'Pago registrado'),
            changed_by=request.user,
            created_by=request.user,
            updated_by=request.user,
            tenant=invoice.tenant
        )
        
        # Registrar acción
        create_audit_log(
            user=request.user,
            action='PAYMENT',
            model_name='Invoice',
            instance_id=invoice.id,
            description=f"Pago registrado para cuenta de cobro {invoice.invoice_number}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            tenant=request.user.tenant
        )
        
        return Response({
            "detail": "Pago registrado correctamente.",
            "status": InvoiceStatusSerializer(status_obj).data
        })
    
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
            # Usuarios sin tenant solo ven facturas donde son emisores o receptores
            issuer_invoices = self.queryset.filter(issuer=request.user)
            recipient_invoices = self.queryset.filter(
                Q(recipient_type='USER', recipient_user=request.user)
            )
            queryset = (issuer_invoices | recipient_invoices).distinct()
        
        # Filtrar por fecha si se proporciona
        start_date = request.query_params.get('start_date', None)
        end_date = request.query_params.get('end_date', None)
        
        if start_date:
            queryset = queryset.filter(issue_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(issue_date__lte=end_date)
        
        # Estadísticas generales
        total_count = queryset.count()
        paid_count = queryset.filter(is_paid=True).count()
        unpaid_count = total_count - paid_count
        total_amount = queryset.aggregate(total=Sum('total_amount'))['total'] or 0
        paid_amount = queryset.filter(is_paid=True).aggregate(total=Sum('total_amount'))['total'] or 0
        pending_amount = total_amount - paid_amount
        
        # Cuentas por estado
        from django.db.models import Count
        status_counts = {}
        for invoice_id, status in InvoiceStatus.objects.filter(
            invoice__in=queryset,
            is_active=True,
            is_deleted=False,
            end_date__isnull=True
        ).values_list('invoice_id', 'status'):
            if status not in status_counts:
                status_counts[status] = 0
            status_counts[status] += 1
        
        # Cuentas próximas a vencer (dentro de 7 días)
        today = timezone.now().date()
        week_ahead = today + timezone.timedelta(days=7)
        due_soon = queryset.filter(
            is_paid=False,
            due_date__gte=today,
            due_date__lte=week_ahead
        ).count()
        
        # Cuentas vencidas
        overdue = queryset.filter(
            is_paid=False,
            due_date__lt=today
        ).count()
        
        return Response({
            'total_count': total_count,
            'paid_count': paid_count,
            'unpaid_count': unpaid_count,
            'total_amount': float(total_amount),
            'paid_amount': float(paid_amount),
            'pending_amount': float(pending_amount),
            'status_counts': status_counts,
            'due_soon': due_soon,
            'overdue': overdue
        })
