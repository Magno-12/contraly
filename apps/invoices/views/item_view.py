from rest_framework import status, permissions, filters
from rest_framework.viewsets import GenericViewSet
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from apps.invoices.models import InvoiceItem, Invoice
from apps.invoices.serializers import InvoiceItemSerializer, InvoiceItemCreateSerializer
from apps.core.utils import create_audit_log, get_client_ip


class InvoiceItemViewSet(GenericViewSet):
    """
    API endpoint para gestionar ítems de cuentas de cobro
    """
    queryset = InvoiceItem.objects.filter(is_deleted=False)
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['invoice', 'tenant']
    search_fields = ['description', 'contract_item']
    ordering_fields = ['order', 'created_at']
    ordering = ['order', 'created_at']
    
    def get_serializer_class(self):
        if self.action == 'create':
            return InvoiceItemCreateSerializer
        return InvoiceItemSerializer
    
    def get_permissions(self):
        """
        Solo los propietarios de la cuenta o administradores pueden modificar ítems
        """
        return [permissions.IsAuthenticated()]
    
    def get_queryset(self):
        """
        Filtrar ítems según permisos del usuario
        """
        queryset = super().get_queryset()
        user = self.request.user
        
        # Superusers ven todos los ítems
        if user.is_superuser:
            return queryset
            
        # Administradores ven los ítems de su organización
        if hasattr(user, 'user_roles') and user.user_roles.filter(
            role__name='Administrator',
            is_active=True,
            is_deleted=False
        ).exists():
            if user.tenant:
                return queryset.filter(tenant=user.tenant)
        
        # Usuarios normales ven ítems de cuentas donde son emisores
        invoice_ids = Invoice.objects.filter(
            issuer=user,
            is_active=True,
            is_deleted=False
        ).values_list('id', flat=True)
        
        return queryset.filter(invoice_id__in=invoice_ids)
    
    def list(self, request):
        """
        Listar ítems de cuentas de cobro
        """
        queryset = self.filter_queryset(self.get_queryset())
        
        # Filtro por invoice_id
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
        Obtener detalle de un ítem
        """
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
    
    def create(self, request):
        """
        Crear un nuevo ítem para una cuenta de cobro
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Verificar que la cuenta existe y está en un estado editable
        try:
            invoice = Invoice.objects.get(id=serializer.validated_data['invoice'].id)
        except Invoice.DoesNotExist:
            return Response(
                {"detail": "La cuenta de cobro especificada no existe."},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Verificar que la cuenta está en estado que permite edición
        current_status = invoice.current_status
        if current_status and current_status.status not in ['DRAFT', 'REVIEW', 'REJECTED']:
            return Response(
                {"detail": f"No se pueden modificar los ítems de una cuenta en estado {current_status.get_status_display()}."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verificar que el usuario tiene permisos para esta cuenta
        if invoice.issuer != request.user and not (
            request.user.is_superuser or (
                hasattr(request.user, 'user_roles') and request.user.user_roles.filter(
                    role__name='Administrator',
                    is_active=True,
                    is_deleted=False
                ).exists()
            )
        ):
            return Response(
                {"detail": "No tiene permisos para modificar esta cuenta de cobro."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Establecer tenant si no se proporciona
        if 'tenant' not in serializer.validated_data and request.user.tenant:
            serializer.validated_data['tenant'] = request.user.tenant
            
        # Ajustar el orden si no se especifica
        if 'order' not in serializer.validated_data:
            # Asignar el último orden + 1
            last_order = InvoiceItem.objects.filter(
                invoice=invoice,
                is_active=True,
                is_deleted=False
            ).order_by('-order').first()
            
            serializer.validated_data['order'] = (last_order.order + 1) if last_order else 0
        
        # Crear ítem
        item = serializer.save(
            created_by=request.user,
            updated_by=request.user
        )
        
        # Registrar creación
        create_audit_log(
            user=request.user,
            action='CREATE',
            model_name='InvoiceItem',
            instance_id=item.id,
            description=f"Creación de ítem para cuenta de cobro {invoice.invoice_number}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            tenant=request.user.tenant
        )
        
        return Response(
            self.get_serializer(item).data,
            status=status.HTTP_201_CREATED
        )
    
    def update(self, request, pk=None):
        """
        Actualizar un ítem existente
        """
        instance = self.get_object()
        invoice = instance.invoice
        
        # Verificar que la cuenta está en estado que permite edición
        current_status = invoice.current_status
        if current_status and current_status.status not in ['DRAFT', 'REVIEW', 'REJECTED']:
            return Response(
                {"detail": f"No se pueden modificar los ítems de una cuenta en estado {current_status.get_status_display()}."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verificar permisos
        if invoice.issuer != request.user and not (
            request.user.is_superuser or (
                hasattr(request.user, 'user_roles') and request.user.user_roles.filter(
                    role__name='Administrator',
                    is_active=True,
                    is_deleted=False
                ).exists()
            )
        ):
            return Response(
                {"detail": "No tiene permisos para modificar esta cuenta de cobro."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = self.get_serializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        item = serializer.save(updated_by=request.user)
        
        # Registrar actualización
        create_audit_log(
            user=request.user,
            action='UPDATE',
            model_name='InvoiceItem',
            instance_id=item.id,
            description=f"Actualización de ítem para cuenta de cobro {invoice.invoice_number}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            tenant=request.user.tenant
        )
        
        return Response(serializer.data)
    
    def partial_update(self, request, pk=None):
        """
        Actualizar parcialmente un ítem
        """
        instance = self.get_object()
        invoice = instance.invoice
        
        # Verificar que la cuenta está en estado que permite edición
        current_status = invoice.current_status
        if current_status and current_status.status not in ['DRAFT', 'REVIEW', 'REJECTED']:
            return Response(
                {"detail": f"No se pueden modificar los ítems de una cuenta en estado {current_status.get_status_display()}."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verificar permisos
        if invoice.issuer != request.user and not (
            request.user.is_superuser or (
                hasattr(request.user, 'user_roles') and request.user.user_roles.filter(
                    role__name='Administrator',
                    is_active=True,
                    is_deleted=False
                ).exists()
            )
        ):
            return Response(
                {"detail": "No tiene permisos para modificar esta cuenta de cobro."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        item = serializer.save(updated_by=request.user)
        
        # Registrar actualización
        create_audit_log(
            user=request.user,
            action='UPDATE',
            model_name='InvoiceItem',
            instance_id=item.id,
            description=f"Actualización parcial de ítem para cuenta de cobro {invoice.invoice_number}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            tenant=request.user.tenant
        )
        
        return Response(serializer.data)
    
    def destroy(self, request, pk=None):
        """
        Eliminar un ítem de una cuenta de cobro
        """
        instance = self.get_object()
        invoice = instance.invoice
        
        # Verificar que la cuenta está en estado que permite edición
        current_status = invoice.current_status
        if current_status and current_status.status not in ['DRAFT', 'REVIEW', 'REJECTED']:
            return Response(
                {"detail": f"No se pueden modificar los ítems de una cuenta en estado {current_status.get_status_display()}."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verificar permisos
        if invoice.issuer != request.user and not (
            request.user.is_superuser or (
                hasattr(request.user, 'user_roles') and request.user.user_roles.filter(
                    role__name='Administrator',
                    is_active=True,
                    is_deleted=False
                ).exists()
            )
        ):
            return Response(
                {"detail": "No tiene permisos para modificar esta cuenta de cobro."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Soft delete
        instance.is_active = False
        instance.is_deleted = True
        instance.updated_by = request.user
        instance.save()
        
        # Actualizar los totales de la factura
        instance.update_invoice_totals()
        
        # Registrar eliminación
        create_audit_log(
            user=request.user,
            action='DELETE',
            model_name='InvoiceItem',
            instance_id=instance.id,
            description=f"Eliminación de ítem para cuenta de cobro {invoice.invoice_number}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            tenant=request.user.tenant
        )
        
        return Response(status=status.HTTP_204_NO_CONTENT)
