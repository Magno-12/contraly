from rest_framework import serializers
from django.db import models
from apps.payments.models import Payment, PaymentStatus, Withholding


class PaymentListSerializer(serializers.ModelSerializer):
    """
    Serializador simplificado para listar pagos
    """
    invoice_number = serializers.CharField(source='invoice.invoice_number', read_only=True)
    invoice_title = serializers.CharField(source='invoice.title', read_only=True)
    payment_method_name = serializers.CharField(source='payment_method.name', read_only=True)
    status_display = serializers.SerializerMethodField()
    
    class Meta:
        model = Payment
        fields = [
            'id', 'invoice', 'invoice_number', 'invoice_title', 'amount', 'payment_date',
            'reference', 'payment_method', 'payment_method_name', 'is_partial',
            'status_display', 'tenant', 'created_at'
        ]
        read_only_fields = ['id', 'created_at', 'status_display']
    
    def get_status_display(self, obj):
        status = PaymentStatus.objects.filter(
            payment=obj,
            is_active=True,
            is_deleted=False
        ).order_by('-change_date').first()
        
        if status:
            return {
                'status': status.status,
                'display': status.get_status_display(),
                'date': status.change_date
            }
        return None


class PaymentDetailSerializer(serializers.ModelSerializer):
    """
    Serializador detallado para pagos
    """
    invoice_details = serializers.SerializerMethodField()
    payment_method_details = serializers.SerializerMethodField()
    status_history = serializers.SerializerMethodField()
    withholdings = serializers.SerializerMethodField()
    
    class Meta:
        model = Payment
        fields = [
            'id', 'invoice', 'invoice_details', 'amount', 'payment_date',
            'reference', 'payment_method', 'payment_method_details', 'status_history',
            'is_partial', 'bank_name', 'account_number', 'transaction_id',
            'receipt', 'withholdings', 'notes', 'tenant', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'invoice_details', 
                           'payment_method_details', 'status_history', 'withholdings']
    
    def get_invoice_details(self, obj):
        invoice = obj.invoice
        return {
            'id': invoice.id,
            'invoice_number': invoice.invoice_number,
            'title': invoice.title,
            'issue_date': invoice.issue_date,
            'due_date': invoice.due_date,
            'total_amount': float(invoice.total_amount),
            'is_paid': invoice.is_paid
        }
    
    def get_payment_method_details(self, obj):
        if obj.payment_method:
            return {
                'id': obj.payment_method.id,
                'name': obj.payment_method.name,
                'payment_type': obj.payment_method.payment_type,
                'payment_type_display': obj.payment_method.get_payment_type_display()
            }
        return None
    
    def get_status_history(self, obj):
        from apps.payments.serializers.payment_status_serializer import PaymentStatusSerializer
        statuses = PaymentStatus.objects.filter(
            payment=obj,
            is_active=True,
            is_deleted=False
        ).order_by('-change_date')
        
        return PaymentStatusSerializer(statuses, many=True).data
    
    def get_withholdings(self, obj):
        from apps.payments.serializers.withholding_serializer import WithholdingSerializer
        withholdings = Withholding.objects.filter(
            payment=obj,
            is_active=True,
            is_deleted=False
        )
        
        return WithholdingSerializer(withholdings, many=True).data


class PaymentCreateSerializer(serializers.ModelSerializer):
    """
    Serializador para crear pagos
    """
    status = serializers.CharField(
        write_only=True,
        required=False,
        default='PENDING'
    )
    
    withholdings = serializers.ListField(
        child=serializers.JSONField(),
        required=False,
        write_only=True
    )
    
    class Meta:
        model = Payment
        fields = [
            'invoice', 'amount', 'payment_date', 'reference', 'payment_method',
            'is_partial', 'bank_name', 'account_number', 'transaction_id',
            'receipt', 'notes', 'tenant', 'status', 'withholdings'
        ]
    
    def validate(self, data):
        # Verificar que la factura existe y no está pagada
        invoice = data.get('invoice')
        if invoice.is_paid:
            raise serializers.ValidationError(
                {"invoice": "Esta cuenta de cobro ya está pagada."}
            )
        
        # Verificar que el monto no exceda el pendiente
        amount = data.get('amount')
        total_paid = Payment.objects.filter(
            invoice=invoice,
            is_active=True,
            is_deleted=False
        ).aggregate(models.Sum('amount'))['amount__sum'] or 0
        
        remaining = invoice.total_amount - total_paid
        
        if amount > remaining:
            raise serializers.ValidationError(
                {"amount": f"El monto excede el saldo pendiente de {remaining}."}
            )
        
        # Si no es pago parcial, verificar que cubra el total pendiente
        if not data.get('is_partial') and amount < remaining:
            raise serializers.ValidationError(
                {"amount": "Para un pago completo, el monto debe cubrir el saldo pendiente."}
            )
        
        return data
    
    def create(self, validated_data):
        # Extraer datos adicionales
        status_data = validated_data.pop('status', 'PENDING')
        withholdings_data = validated_data.pop('withholdings', [])
        
        # Crear el pago
        payment = Payment.objects.create(**validated_data)
        
        # Crear estado inicial
        from apps.payments.models import PaymentStatus
        PaymentStatus.objects.create(
            payment=payment,
            status=status_data,
            changed_by=self.context.get('request').user if 'request' in self.context else None,
            created_by=self.context.get('request').user if 'request' in self.context else None,
            updated_by=self.context.get('request').user if 'request' in self.context else None,
            tenant=payment.tenant
        )
        
        # Crear retenciones
        from apps.payments.serializers.withholding_serializer import WithholdingCreateSerializer
        for withholding_data in withholdings_data:
            withholding_data['payment'] = payment.id
            
            if 'tenant' not in withholding_data and payment.tenant:
                withholding_data['tenant'] = payment.tenant.id
            
            serializer = WithholdingCreateSerializer(data=withholding_data)
            serializer.is_valid(raise_exception=True)
            serializer.save(
                created_by=self.context.get('request').user if 'request' in self.context else None,
                updated_by=self.context.get('request').user if 'request' in self.context else None
            )
        
        return payment
