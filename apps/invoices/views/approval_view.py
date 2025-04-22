from rest_framework import status, permissions, filters
from rest_framework.viewsets import GenericViewSet
from rest_framework.response import Response
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.db.models import Q

from apps.invoices.models import InvoiceApproval, Invoice, InvoiceStatus
from apps.invoices.serializers import InvoiceApprovalSerializer
from apps.core.utils import create_audit_log, get_client_ip
from apps.core.permission import IsAdministrator


class InvoiceApprovalViewSet(GenericViewSet):
    """
    API endpoint para gestionar aprobaciones de cuentas de cobro
    """
    queryset = InvoiceApproval.objects.filter(is_deleted=False)
    serializer_class = InvoiceApprovalSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['invoice', 'approval_type', 'approver', 'result', 'tenant']
    search_fields = ['comments']
    ordering_fields = ['assigned_date', 'approval_date']
    ordering = ['-assigned_date']
    
    def get_permissions(self):
        """
        Permisos para gestionar aprobaciones
        """
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [permissions.IsAuthenticated, IsAdministrator]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        """
        Filtrar aprobaciones según permisos del usuario
        """
        queryset = super().get_queryset()
        user = self.request.user
        
        # Superusers ven todas las aprobaciones
        if user.is_superuser:
            return queryset
        
        # Administradores ven aprobaciones de su organización
        if hasattr(user, 'user_roles') and user.user_roles.filter(
            role__name='Administrator',
            is_active=True,
            is_deleted=False
        ).exists():
            if user.tenant:
                return queryset.filter(tenant=user.tenant)
        
        # Usuarios con rol de aprobador ven aprobaciones asignadas a ellos
        return queryset.filter(
            Q(approver=user) |  # Aprobaciones asignadas a mi
            Q(invoice__issuer=user)  # Aprobaciones de mis cuentas
        )
    
    def list(self, request):
        """
        Listar aprobaciones de cuentas de cobro
        """
        queryset = self.filter_queryset(self.get_queryset())
        
        # Filtros adicionales
        invoice_id = request.query_params.get('invoice_id', None)
        if invoice_id:
            queryset = queryset.filter(invoice_id=invoice_id)
            
        # Filtro por resultado
        result = request.query_params.get('result', None)
        if result:
            queryset = queryset.filter(result=result)
            
        # Filtro por mis aprobaciones pendientes
        my_pending = request.query_params.get('my_pending', None)
        if my_pending and my_pending.lower() == 'true':
            queryset = queryset.filter(
                approver=request.user,
                result='PENDING'
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
        Obtener detalle de una aprobación
        """
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
    
    def create(self, request):
        """
        Crear una nueva aprobación para una cuenta de cobro
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
        
        # Verificar que no exista una aprobación del mismo tipo para esta cuenta
        invoice = serializer.validated_data.get('invoice')
        approval_type = serializer.validated_data.get('approval_type')
        approver = serializer.validated_data.get('approver')
        
        existing = InvoiceApproval.objects.filter(
            invoice=invoice,
            approval_type=approval_type,
            is_active=True,
            is_deleted=False
        ).first()
        
        if existing:
            return Response(
                {"detail": f"Ya existe una aprobación de tipo {approval_type} para esta cuenta."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Crear aprobación
        approval = serializer.save(
            created_by=request.user,
            updated_by=request.user
        )
        
        # Registrar creación
        create_audit_log(
            user=request.user,
            action='CREATE',
            model_name='InvoiceApproval',
            instance_id=approval.id,
            description=f"Asignación de aprobación de cuenta {invoice.invoice_number} a {approver.email}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            tenant=request.user.tenant
        )
        
        return Response(
            self.get_serializer(approval).data,
            status=status.HTTP_201_CREATED
        )
    
    def update(self, request, pk=None):
        """
        Actualizar una aprobación existente
        """
        instance = self.get_object()
        
        # No permitir actualizar aprobaciones que ya tienen resultado
        if instance.result != 'PENDING':
            return Response(
                {"detail": f"No se puede modificar una aprobación que ya ha sido {instance.get_result_display().lower()}."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = self.get_serializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        approval = serializer.save(updated_by=request.user)
        
        # Registrar actualización
        create_audit_log(
            user=request.user,
            action='UPDATE',
            model_name='InvoiceApproval',
            instance_id=approval.id,
            description=f"Actualización de aprobación para cuenta {approval.invoice.invoice_number}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            tenant=request.user.tenant
        )
        
        return Response(serializer.data)
    
    def partial_update(self, request, pk=None):
        """
        Actualizar parcialmente una aprobación
        """
        instance = self.get_object()
        
        # No permitir actualizar aprobaciones que ya tienen resultado
        if instance.result != 'PENDING' and 'result' in request.data:
            return Response(
                {"detail": f"No se puede modificar una aprobación que ya ha sido {instance.get_result_display().lower()}."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        approval = serializer.save(updated_by=request.user)
        
        # Registrar actualización
        create_audit_log(
            user=request.user,
            action='UPDATE',
            model_name='InvoiceApproval',
            instance_id=approval.id,
            description=f"Actualización parcial de aprobación para cuenta {approval.invoice.invoice_number}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            tenant=request.user.tenant
        )
        
        return Response(serializer.data)
    
    def destroy(self, request, pk=None):
        """
        Eliminar (soft delete) una aprobación
        """
        instance = self.get_object()
        
        # No permitir eliminar aprobaciones que ya tienen resultado
        if instance.result != 'PENDING':
            return Response(
                {"detail": f"No se puede eliminar una aprobación que ya ha sido {instance.get_result_display().lower()}."},
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
            model_name='InvoiceApproval',
            instance_id=instance.id,
            description=f"Eliminación de aprobación para cuenta {instance.invoice.invoice_number}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            tenant=request.user.tenant
        )
        
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    @action(detail=False, methods=['get'])
    def approval_types(self, request):
        """
        Obtener lista de tipos de aprobación
        """
        return Response([
            {'value': choice[0], 'label': choice[1]}
            for choice in InvoiceApproval.APPROVAL_TYPES
        ])
    
    @action(detail=False, methods=['get'])
    def result_types(self, request):
        """
        Obtener lista de resultados posibles
        """
        return Response([
            {'value': choice[0], 'label': choice[1]}
            for choice in InvoiceApproval.APPROVAL_RESULTS
        ])
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """
        Aprobar una solicitud de aprobación
        """
        approval = self.get_object()
        
        # Verificar que la aprobación esté pendiente
        if approval.result != 'PENDING':
            return Response(
                {"detail": f"Esta aprobación ya ha sido {approval.get_result_display().lower()}."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verificar que el usuario sea el aprobador asignado
        if approval.approver != request.user:
            return Response(
                {"detail": "Solo el aprobador asignado puede aprobar esta solicitud."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Actualizar la aprobación
        approval.result = 'APPROVED'
        approval.approval_date = timezone.now()
        approval.comments = request.data.get('comments', 'Aprobado')
        approval.updated_by = request.user
        approval.save()
        
        # Registrar aprobación
        create_audit_log(
            user=request.user,
            action='APPROVE',
            model_name='InvoiceApproval',
            instance_id=approval.id,
            description=f"Aprobación de cuenta {approval.invoice.invoice_number}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            tenant=request.user.tenant
        )
        
        # Si todas las aprobaciones están completas, actualizar el estado de la cuenta
        invoice = approval.invoice
        pending_approvals = InvoiceApproval.objects.filter(
            invoice=invoice,
            result='PENDING',
            is_active=True,
            is_deleted=False
        ).exists()
        
        if not pending_approvals:
            # Verificar que no haya rechazos
            rejected = InvoiceApproval.objects.filter(
                invoice=invoice,
                result='REJECTED',
                is_active=True,
                is_deleted=False
            ).exists()
            
            if not rejected:
                # Si es aprobación final, cambiar estado a APPROVED
                if approval.approval_type == 'FINAL_APPROVAL':
                    InvoiceStatus.objects.create(
                        invoice=invoice,
                        status='APPROVED',
                        comments='Todas las aprobaciones completadas',
                        changed_by=request.user,
                        created_by=request.user,
                        updated_by=request.user,
                        tenant=invoice.tenant
                    )
                # Si es primera aprobación, cambiar estado a PENDING_APPROVAL
                elif approval.approval_type == 'FIRST_APPROVAL':
                    current_status = invoice.current_status
                    if current_status and current_status.status == 'REVIEW':
                        InvoiceStatus.objects.create(
                            invoice=invoice,
                            status='PENDING_APPROVAL',
                            comments='Primera aprobación completada',
                            changed_by=request.user,
                            created_by=request.user,
                            updated_by=request.user,
                            tenant=invoice.tenant
                        )
        
        return Response(self.get_serializer(approval).data)
    
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """
        Rechazar una solicitud de aprobación
        """
        approval = self.get_object()
        
        # Verificar que la aprobación esté pendiente
        if approval.result != 'PENDING':
            return Response(
                {"detail": f"Esta aprobación ya ha sido {approval.get_result_display().lower()}."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verificar que el usuario sea el aprobador asignado
        if approval.approver != request.user:
            return Response(
                {"detail": "Solo el aprobador asignado puede rechazar esta solicitud."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Verificar que se proporcionó un motivo
        if not request.data.get('comments'):
            return Response(
                {"detail": "Debe proporcionar un motivo para el rechazo."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Actualizar la aprobación
        approval.result = 'REJECTED'
        approval.approval_date = timezone.now()
        approval.comments = request.data.get('comments')
        approval.updated_by = request.user
        approval.save()
        
        # Registrar rechazo
        create_audit_log(
            user=request.user,
            action='REJECT',
            model_name='InvoiceApproval',
            instance_id=approval.id,
            description=f"Rechazo de cuenta {approval.invoice.invoice_number}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            tenant=request.user.tenant
        )
        
        # Cambiar estado de la cuenta a REJECTED
        invoice = approval.invoice
        InvoiceStatus.objects.create(
            invoice=invoice,
            status='REJECTED',
            comments=f"Rechazado por {request.user.email}: {request.data.get('comments')}",
            changed_by=request.user,
            created_by=request.user,
            updated_by=request.user,
            tenant=invoice.tenant
        )
        
        return Response(self.get_serializer(approval).data)
    
    @action(detail=False, methods=['get'])
    def my_pending(self, request):
        """
        Obtener aprobaciones pendientes del usuario actual
        """
        queryset = InvoiceApproval.objects.filter(
            approver=request.user,
            result='PENDING',
            is_active=True,
            is_deleted=False
        ).order_by('-assigned_date')
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
            
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def by_invoice(self, request):
        """
        Obtener aprobaciones para una cuenta específica
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
