from rest_framework import serializers
from apps.invoices.models import InvoiceStatus


class InvoiceStatusSerializer(serializers.ModelSerializer):
    """
    Serializador para estados de cuentas de cobro
    """
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    changed_by_name = serializers.SerializerMethodField()
    
    class Meta:
        model = InvoiceStatus
        fields = [
            'id', 'invoice', 'status', 'status_display',
            'start_date', 'end_date', 'comments', 'changed_by',
            'changed_by_name', 'tenant', 'is_active', 'created_at'
        ]
        read_only_fields = ['id', 'start_date', 'created_at', 'changed_by_name']
    
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
