from rest_framework import serializers
from apps.payments.models import PaymentStatus


class PaymentStatusSerializer(serializers.ModelSerializer):
    """
    Serializador para estados de pago
    """
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    changed_by_name = serializers.SerializerMethodField()
    
    class Meta:
        model = PaymentStatus
        fields = [
            'id', 'payment', 'status', 'status_display', 'change_date',
            'comments', 'changed_by', 'changed_by_name', 'tenant',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'change_date', 'created_at', 'updated_at', 'changed_by_name']
    
    def get_changed_by_name(self, obj):
        if obj.changed_by:
            return f"{obj.changed_by.first_name} {obj.changed_by.last_name}"
        return None
    
    def create(self, validated_data):
        # Establecer el usuario que cambia el estado
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            validated_data['changed_by'] = request.user
        
        return super().create(validated_data)
