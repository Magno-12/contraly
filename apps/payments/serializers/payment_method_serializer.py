from rest_framework import serializers
from apps.payments.models import PaymentMethod


class PaymentMethodSerializer(serializers.ModelSerializer):
    """
    Serializador para métodos de pago
    """
    payment_type_display = serializers.CharField(source='get_payment_type_display', read_only=True)
    
    class Meta:
        model = PaymentMethod
        fields = [
            'id', 'name', 'code', 'description', 'payment_type', 'payment_type_display',
            'requires_reference', 'requires_receipt', 'requires_bank_info',
            'allow_partial', 'tenant', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'payment_type_display']
    
    def validate_code(self, value):
        """
        Validar que el código sea único para este tenant
        """
        tenant = self.context.get('tenant')
        instance = getattr(self, 'instance', None)
        
        # Si hay instancia, es una actualización
        if instance and instance.code == value:
            return value
        
        # Verificar que no exista para este tenant
        if tenant and PaymentMethod.objects.filter(code=value, tenant=tenant).exists():
            raise serializers.ValidationError(
                f"Ya existe un método de pago con el código '{value}' para esta organización."
            )
        
        return value
