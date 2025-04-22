from rest_framework import status, permissions, filters
from rest_framework.viewsets import GenericViewSet
from rest_framework.response import Response
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone

from apps.invoices.models import InvoiceStatus, Invoice
from apps.invoices.serializers import InvoiceStatusSerializer
from apps.core.utils import create_audit_log, get_client_ip
from apps.core.permission import IsAdministrator


class InvoiceStatusViewSet(GenericViewSet):
    """
    API endpoint para gestionar estados de cuentas de cobro
    """
    queryset = InvoiceStatus.objects.filter(is_deleted=False)
    serializer_class = InvoiceStatusSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['invoice', 'status', 'tenant']
    search_fields = ['comments']
    ordering_fields = ['start_date', 'status']
    ordering = ['-start_date']
    
    def get_permissions(self):
        """
        Permisos para cambiar estado de cuentas
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
        
        # Usuarios normales ven estados de cuentas donde son emisores o receptores
        invoice_ids = Invoice.objects.filter(
            (
                Q(issuer=user) |
                Q(recipient_type='USER', recipient_user=user) |
                Q(recipient_type='ORGANIZATION', recipient_organization=user.tenant)
            ),
            is_active=True,
            is_deleted=False
        ).values_list('id', flat=True)
        
        return queryset.filter(invoice_id__in=invoice_ids)
    
    def list(self, request):
        """
        Listar estados de cuentas de cobro
        """
        queryset = self.filter_queryset(self.get_queryset())
        
        # Filtros adicionales
        invoice_id = request.query_params.get('invoice_id', None)
        if invoice_id:
            queryset = queryset.filter(invoice_id=invoice_id)
            
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
        Crear un nuevo estado para una cuenta de cobro
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Establecer tenant si no se proporciona
        if 'tenant' not in serializer.validated_data:
            invoice = serializer.validated_data.get('invoice')
            if invoice and invoice.tenant:
                serializer.validated_data['tenant'] = invoice.tenant
            elif request.user.tenant:
                serializer.validated_data['tenant'] = request.user.tenant
        
        # Validar transición de estado
        invoice = serializer.validated_data.get('invoice')
        new_status = serializer.validated_data.get('status')
        
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
        
        # Verificar permisos para transiciones específicas
        if new_status in ['APPROVED', 'REJECTED'] and not (
            request.user.is_superuser or (
                hasattr(request.user, 'user_roles') and request.user.user_roles.filter(
                    role__role_permissions__permission__code__in=['invoices.approve_invoice', 'invoices.review_invoice'],
                    is_active=True,
                    is_deleted=False
                ).exists()
            )
        ):
            return Response(
                {"detail": f"No tiene permisos para cambiar el estado a {new_status}."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Crear estado
        serializer.context['request'] = request
        status_obj = serializer.save(
            created_by=request.user,
            updated_by=request.user,
            changed_by=request.user
        )
        
        # Actualizar la factura si el estado es PAID
        if new_status == 'PAID' and not invoice.is_paid:
            invoice.is_paid = True
            invoice.payment_date = timezone.now().date()
            invoice.save(update_fields=['is_paid', 'payment_date', 'updated_by'])
        
        # Registrar creación
        create_audit_log(
            user=request.user,
            action='CREATE',
            model_name='InvoiceStatus',
            instance_id=status_obj.id,
            description=f"Cambio de estado de cuenta de cobro {invoice.invoice_number} a {status_obj.get_status_display()}",
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
            model_name='InvoiceStatus',
            instance_id=status_obj.id,
            description=f"Actualización de estado de cuenta de cobro {status_obj.invoice.invoice_number}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            tenant=request.user.tenant
        )
        
        return Response(serializer.data)
    
    def partial_update(self, request, pk=None):
        """
        Actualizar parcialmente un estado
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
            model_name='InvoiceStatus',
            instance_id=status_obj.id,
            description=f"Actualización parcial de estado de cuenta de cobro {status_obj.invoice.invoice_number}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            tenant=request.user.tenant
        )
        
        return Response(serializer.data)
    
    def destroy(self, request, pk=None):
        """
        Eliminar un estado de cuenta de cobro
        """
        instance = self.get_object()
        
        # No permitir eliminar el estado actual de una cuenta
        invoice = instance.invoice
        current_status = invoice.current_status
        
        if current_status and current_status.id == instance.id:
            return Response(
                {"detail": "No se puede eliminar el estado actual de una cuenta de cobro."},
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
            model_name='InvoiceStatus',
            instance_id=instance.id,
            description=f"Eliminación de estado de cuenta de cobro {instance.invoice.invoice_number}",
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
            for choice in InvoiceStatus.STATUS_CHOICES
        ])
    
    @action(detail=False, methods=['get'])
    def current_by_invoice(self, request):
        """
        Obtener el estado actual de una cuenta específica
        """
        invoice_id = request.query_params.get('invoice_id')
        if not invoice_id:
            return Response(
                {"detail": "Se requiere el parámetro invoice_id."},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        try:
            invoice = Invoice.objects.get(id=invoice_id)
        except Invoice.DoesNotExist:
            return Response(
                {"detail": "La cuenta de cobro especificada no existe."},
                status=status.HTTP_404_NOT_FOUND
            )
            
        current_status = invoice.current_status
        if not current_status:
            return Response(
                {"detail": "La cuenta de cobro no tiene un estado actual definido."},
                status=status.HTTP_404_NOT_FOUND
            )
            
        serializer = self.get_serializer(current_status)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def history_by_invoice(self, request):
        """
        Obtener el historial completo de estados de una cuenta
        """
        invoice_id = request.query_params.get('invoice_id')
        if not invoice_id:
            return Response(
                {"detail": "Se requiere el parámetro invoice_id."},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        try:
            invoice = Invoice.objects.get(id=invoice_id)
        except Invoice.DoesNotExist:
            return Response(
                {"detail": "La cuenta de cobro especificada no existe."},
                status=status.HTTP_404_NOT_FOUND
            )
            
        statuses = InvoiceStatus.objects.filter(
            invoice=invoice,
            is_active=True,
            is_deleted=False
        ).order_by('-start_date')
        
        serializer = self.get_serializer(statuses, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def transition(self, request):
        """
        Realizar una transición de estado para una cuenta
        """
        # Validar datos requeridos
        invoice_id = request.data.get('invoice_id')
        new_status = request.data.get('status')
        comments = request.data.get('comments', '')
        
        if not invoice_id or not new_status:
            return Response(
                {"detail": "Se requieren los parámetros invoice_id y status."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verificar que el estado solicitado es válido
        valid_statuses = [choice[0] for choice in InvoiceStatus.STATUS_CHOICES]
        if new_status not in valid_statuses:
            return Response(
                {"detail": f"El estado '{new_status}' no es válido. Opciones válidas: {', '.join(valid_statuses)}"},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        # Obtener la cuenta
        try:
            invoice = Invoice.objects.get(id=invoice_id)
        except Invoice.DoesNotExist:
            return Response(
                {"detail": "La cuenta de cobro especificada no existe."},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Validar transición de estado
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
        
        # Verificar permisos especiales para ciertos estados
        if new_status in ['APPROVED', 'REJECTED'] and not (
            request.user.is_superuser or (
                hasattr(request.user, 'user_roles') and request.user.user_roles.filter(
                    role__role_permissions__permission__code__in=['invoices.approve_invoice', 'invoices.review_invoice'],
                    is_active=True,
                    is_deleted=False
                ).exists()
            )
        ):
            return Response(
                {"detail": f"No tiene permisos para cambiar el estado a {new_status}."},
                status=status.HTTP_403_FORBIDDEN
            )
            
        # Si es transición a PAID, verificar permisos
        if new_status == 'PAID' and not (
            request.user.is_superuser or (
                hasattr(request.user, 'user_roles') and request.user.user_roles.filter(
                    role__role_permissions__permission__code='invoices.register_payment',
                    is_active=True,
                    is_deleted=False
                ).exists()
            )
        ):
            return Response(
                {"detail": "No tiene permisos para registrar pagos."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Crear el nuevo estado
        status_obj = InvoiceStatus.objects.create(
            invoice=invoice,
            status=new_status,
            comments=comments,
            changed_by=request.user,
            created_by=request.user,
            updated_by=request.user,
            tenant=invoice.tenant
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
            description=f"Transición de estado de '{current_status_code}' a '{new_status}' para cuenta {invoice.invoice_number}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            tenant=request.user.tenant
        )
        
        return Response(self.get_serializer(status_obj).data)
