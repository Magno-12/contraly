from rest_framework import serializers
from apps.payments.models import Withholding


class WithholdingSerializer(serializers.ModelSerializer):
    """
    Serializador para retenciones
    """
    withholding_type_display = serializers.CharField(source='get_withholding_type_display', read_only=True)
    
    class Meta:
        model = Withholding
        fields = [
            'id', 'payment', 'name', 'code', 'percentage', 'amount',
            'withholding_type', 'withholding_type_display', 'certificate',
            'description', 'tenant', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'withholding_type_display']


class WithholdingCreateSerializer(serializers.ModelSerializer):
    """
    Serializador para crear retenciones
    """
    class Meta:
        model = Withholding
        fields = [
            'payment', 'name', 'code', 'percentage', 'amount',
            'withholding_type', 'certificate', 'description', 'tenant'
        ]
    
    def validate(self, data):
        # Verificar que se proporcione porcentaje o monto
        if 'percentage' not in data and 'amount' not in data:
            raise serializers.ValidationError(
                "Debe proporcionar el porcentaje o el monto de la retención."
            )
        
        # Si se proporciona porcentaje, verificar que sea válido
        if 'percentage' in data and (data['percentage'] <= 0 or data['percentage'] >= 100):
            raise serializers.ValidationError(
                {"percentage": "El porcentaje debe estar entre 0 y 100."}
            )
        
        # Si se proporciona monto, verificar que sea positivo
        if 'amount' in data and data['amount'] <= 0:
            raise serializers.ValidationError(
                {"amount": "El monto debe ser positivo."}
            )
        
        return data
