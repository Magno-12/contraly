from rest_framework import serializers
from django.db.transaction import atomic
from apps.invoices.models import Invoice, InvoiceStatus, InvoiceItem


class InvoiceListSerializer(serializers.ModelSerializer):
    """
    Serializador simplificado para listar cuentas de cobro
    """
    issuer_name = serializers.SerializerMethodField()
    recipient_name = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    
    class Meta:
        model = Invoice
        fields = [
            'id', 'invoice_number', 'title', 'issuer', 'issuer_name',
            'recipient_name', 'issue_date', 'due_date', 'total_amount', 
            'currency', 'is_paid', 'status', 'contract', 'tenant', 'created_at'
        ]
        read_only_fields = ['id', 'created_at', 'status']
    
    def get_issuer_name(self, obj):
        if obj.issuer:
            return f"{obj.issuer.first_name} {obj.issuer.last_name}"
        return None
    
    def get_recipient_name(self, obj):
        if obj.recipient_type == 'ORGANIZATION' and obj.recipient_organization:
            return obj.recipient_organization.name
        elif obj.recipient_type == 'USER' and obj.recipient_user:
            return f"{obj.recipient_user.first_name} {obj.recipient_user.last_name}"
        else:
            return obj.recipient_name
    
    def get_status(self, obj):
        current_status = obj.current_status
        if current_status:
            return {
                'id': current_status.id,
                'status': current_status.status,
                'status_display': current_status.get_status_display(),
                'start_date': current_status.start_date
            }
        return None


class InvoiceSerializer(serializers.ModelSerializer):
    """
    Serializador base para cuentas de cobro
    """
    class Meta:
        model = Invoice
        fields = [
            'id', 'invoice_number', 'title', 'contract',
            'issuer', 'recipient_type', 'recipient_organization', 
            'recipient_user', 'recipient_name', 'recipient_identification',
            'issue_date', 'due_date', 'period_start', 'period_end',
            'subtotal', 'tax_amount', 'discount_amount', 'total_amount',
            'currency', 'notes', 'payment_terms', 'reference', 
            'payment_method', 'is_paid', 'payment_date', 'document',
            'tenant', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class InvoiceDetailSerializer(serializers.ModelSerializer):
    """
    Serializador detallado para cuentas de cobro con relaciones incluidas
    """
    issuer_name = serializers.SerializerMethodField()
    recipient_info = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    items = serializers.SerializerMethodField()
    approvals = serializers.SerializerMethodField()
    contract_info = serializers.SerializerMethodField()
    
    class Meta:
        model = Invoice
        fields = [
            'id', 'invoice_number', 'title', 'contract', 'contract_info',
            'issuer', 'issuer_name', 'recipient_type', 'recipient_info',
            'issue_date', 'due_date', 'period_start', 'period_end',
            'subtotal', 'tax_amount', 'discount_amount', 'total_amount',
            'currency', 'notes', 'payment_terms', 'reference', 
            'payment_method', 'is_paid', 'payment_date', 'document',
            'tenant', 'is_active', 'created_at', 'updated_at',
            'status', 'items', 'approvals'
        ]
        read_only_fields = [
            'id', 'created_at', 'updated_at', 'status', 'items',
            'approvals', 'issuer_name', 'recipient_info', 'contract_info'
        ]
    
    def get_issuer_name(self, obj):
        if obj.issuer:
            return {
                'id': obj.issuer.id,
                'email': obj.issuer.email,
                'name': f"{obj.issuer.first_name} {obj.issuer.last_name}"
            }
        return None
    
    def get_recipient_info(self, obj):
        if obj.recipient_type == 'ORGANIZATION' and obj.recipient_organization:
            return {
                'type': 'ORGANIZATION',
                'id': obj.recipient_organization.id,
                'name': obj.recipient_organization.name,
                'identification': obj.recipient_organization.tax_id
            }
        elif obj.recipient_type == 'USER' and obj.recipient_user:
            return {
                'type': 'USER',
                'id': obj.recipient_user.id,
                'name': f"{obj.recipient_user.first_name} {obj.recipient_user.last_name}",
                'identification': obj.recipient_user.document_number
            }
        else:
            return {
                'type': 'EXTERNAL',
                'name': obj.recipient_name,
                'identification': obj.recipient_identification
            }
    
    def get_status(self, obj):
        from apps.invoices.serializers.status_serializer import InvoiceStatusSerializer
        current_status = obj.current_status
        if current_status:
            return InvoiceStatusSerializer(current_status).data
        return None
    
    def get_items(self, obj):
        from apps.invoices.serializers.item_serializer import InvoiceItemSerializer
        items = InvoiceItem.objects.filter(
            invoice=obj,
            is_active=True,
            is_deleted=False
        ).order_by('order')
        return InvoiceItemSerializer(items, many=True).data
    
    def get_approvals(self, obj):
        from apps.invoices.serializers.approval_serializer import InvoiceApprovalSerializer
        approvals = obj.approvals.filter(
            is_active=True,
            is_deleted=False
        ).order_by('approval_type')
        return InvoiceApprovalSerializer(approvals, many=True).data
    
    def get_contract_info(self, obj):
        if obj.contract:
            return {
                'id': obj.contract.id,
                'contract_number': obj.contract.contract_number,
                'title': obj.contract.title
            }
        return None


class InvoiceCreateSerializer(serializers.ModelSerializer):
    """
    Serializador para crear nuevas cuentas de cobro con ítems
    """
    items = serializers.ListField(
        child=serializers.JSONField(),
        required=False,
        write_only=True
    )
    
    status = serializers.ChoiceField(
        choices=InvoiceStatus.STATUS_CHOICES,
        write_only=True,
        default='DRAFT'
    )
    
    class Meta:
        model = Invoice
        fields = [
            'invoice_number', 'title', 'contract',
            'issuer', 'recipient_type', 'recipient_organization', 
            'recipient_user', 'recipient_name', 'recipient_identification',
            'issue_date', 'due_date', 'period_start', 'period_end',
            'subtotal', 'tax_amount', 'discount_amount', 'total_amount',
            'currency', 'notes', 'payment_terms', 'reference', 
            'payment_method', 'document', 'tenant', 'items', 'status'
        ]
    
    def validate(self, data):
        # Verificar que se proporcione un destinatario según el tipo
        recipient_type = data.get('recipient_type', 'ORGANIZATION')
        
        if recipient_type == 'ORGANIZATION' and not data.get('recipient_organization'):
            raise serializers.ValidationError(
                {"recipient_organization": "Se requiere una organización como destinatario."}
            )
        elif recipient_type == 'USER' and not data.get('recipient_user'):
            raise serializers.ValidationError(
                {"recipient_user": "Se requiere un usuario como destinatario."}
            )
        elif recipient_type == 'EXTERNAL' and not data.get('recipient_name'):
            raise serializers.ValidationError(
                {"recipient_name": "Se requiere un nombre para el destinatario externo."}
            )
        
        # Verificar que la fecha de vencimiento sea posterior a la fecha de emisión
        issue_date = data.get('issue_date')
        due_date = data.get('due_date')
        
        if issue_date and due_date and due_date < issue_date:
            raise serializers.ValidationError(
                {"due_date": "La fecha de vencimiento debe ser posterior a la fecha de emisión."}
            )
        
        return data
    
    @atomic
    def create(self, validated_data):
        # Extraer datos de ítems y estado
        items_data = validated_data.pop('items', [])
        status_data = validated_data.pop('status', 'DRAFT')
        
        # Crear la cuenta de cobro
        invoice = super().create(validated_data)
        
        # Crear ítems
        if items_data:
            self._create_items(invoice, items_data)
        
        # Crear estado inicial
        InvoiceStatus.objects.create(
            invoice=invoice,
            status=status_data,
            created_by=self.context.get('request').user if 'request' in self.context else None,
            updated_by=self.context.get('request').user if 'request' in self.context else None,
            tenant=invoice.tenant
        )
        
        return invoice
    
    def _create_items(self, invoice, items_data):
        """
        Crea los ítems de la cuenta de cobro
        """
        from apps.invoices.serializers.item_serializer import InvoiceItemCreateSerializer
        
        for i, item_data in enumerate(items_data):
            # Añadir invoice y orden
            item_data['invoice'] = invoice.id
            item_data['order'] = i
            
            # Añadir tenant si no está presente
            if 'tenant' not in item_data and invoice.tenant:
                item_data['tenant'] = invoice.tenant.id
            
            # Crear ítem
            serializer = InvoiceItemCreateSerializer(data=item_data)
            serializer.is_valid(raise_exception=True)
            serializer.context['request'] = self.context.get('request')
            serializer.save()
