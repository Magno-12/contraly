from rest_framework import serializers
from apps.payments.models import PaymentSchedule, Payment


class PaymentScheduleSerializer(serializers.ModelSerializer):
    """
    Serializador para programaciones de pago
    """
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    invoice_number = serializers.CharField(source='invoice.invoice_number', read_only=True)
    invoice_title = serializers.CharField(source='invoice.title', read_only=True)
    remaining_amount = serializers.SerializerMethodField()
    associated_payments = serializers.SerializerMethodField()
    
    class Meta:
        model = PaymentSchedule
        fields = [
            'id', 'invoice', 'invoice_number', 'invoice_title', 'due_date',
            'amount', 'status', 'status_display', 'paid_amount', 'remaining_amount',
            'payment_date', 'installment_number', 'total_installments',
            'notes', 'associated_payments', 'tenant', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'status_display', 
                           'invoice_number', 'invoice_title', 'remaining_amount',
                           'associated_payments']
    
    def get_remaining_amount(self, obj):
        return obj.amount - obj.paid_amount
    
    def get_associated_payments(self, obj):
        from apps.payments.serializers.payment_serializer import PaymentListSerializer
        payments = obj.payments.filter(is_active=True, is_deleted=False)
        return PaymentListSerializer(payments, many=True).data


class PaymentScheduleCreateSerializer(serializers.ModelSerializer):
    """
    Serializador para crear programaciones de pago
    """
    class Meta:
        model = PaymentSchedule
        fields = [
            'invoice', 'due_date', 'amount', 'installment_number', 
            'total_installments', 'notes', 'tenant'
        ]
    
    def validate(self, data):
        # Verificar que la fecha de vencimiento sea posterior a hoy
        from django.utils import timezone
        today = timezone.now().date()
        if data.get('due_date') < today:
            raise serializers.ValidationError(
                {"due_date": "La fecha de vencimiento debe ser posterior a hoy."}
            )
        
        # Verificar que el monto sea positivo
        if data.get('amount', 0) <= 0:
            raise serializers.ValidationError(
                {"amount": "El monto debe ser mayor que cero."}
            )
        
        # Verificar que el número de cuota sea válido
        if data.get('installment_number', 1) > data.get('total_installments', 1):
            raise serializers.ValidationError(
                {"installment_number": "El número de cuota no puede ser mayor que el total de cuotas."}
            )
        
        return data


class PaymentScheduleBulkCreateSerializer(serializers.Serializer):
    """
    Serializador para crear múltiples programaciones de pago
    """
    invoice = serializers.UUIDField(required=True)
    total_amount = serializers.DecimalField(max_digits=15, decimal_places=2, required=True)
    installments = serializers.IntegerField(min_value=1, required=True)
    start_date = serializers.DateField(required=True)
    frequency = serializers.ChoiceField(
        choices=[
            ('MONTHLY', 'Mensual'),
            ('BIMONTHLY', 'Bimestral'),
            ('QUARTERLY', 'Trimestral'),
            ('SEMIANNUAL', 'Semestral'),
            ('ANNUAL', 'Anual'),
            ('CUSTOM', 'Personalizado')
        ],
        default='MONTHLY'
    )
    custom_days = serializers.IntegerField(required=False, min_value=1)
    equal_amounts = serializers.BooleanField(default=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    
    def validate(self, data):
        # Verificar que la fecha de inicio sea posterior a hoy
        from django.utils import timezone
        today = timezone.now().date()
        if data.get('start_date') < today:
            raise serializers.ValidationError(
                {"start_date": "La fecha de inicio debe ser posterior o igual a hoy."}
            )
        
        # Verificar que el monto total sea positivo
        if data.get('total_amount', 0) <= 0:
            raise serializers.ValidationError(
                {"total_amount": "El monto total debe ser mayor que cero."}
            )
        
        # Si la frecuencia es CUSTOM, verificar que se proporcionen los días
        if data.get('frequency') == 'CUSTOM' and not data.get('custom_days'):
            raise serializers.ValidationError(
                {"custom_days": "Debe especificar los días para la frecuencia personalizada."}
            )
        
        return data
