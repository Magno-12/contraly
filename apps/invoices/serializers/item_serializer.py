from rest_framework import serializers
from apps.invoices.models import InvoiceItem


class InvoiceItemSerializer(serializers.ModelSerializer):
    """
    Serializador para ítems de cuentas de cobro
    """
    class Meta:
        model = InvoiceItem
        fields = [
            'id', 'invoice', 'description', 'quantity', 'unit_price',
            'tax_percentage', 'tax_amount', 'discount_percentage',
            'discount_amount', 'subtotal', 'total', 'contract_item',
            'notes', 'order', 'tenant', 'is_active', 'created_at'
        ]
        read_only_fields = ['id', 'created_at', 'subtotal', 'total']


class InvoiceItemCreateSerializer(serializers.ModelSerializer):
    """
    Serializador para crear ítems de cuentas de cobro
    """
    class Meta:
        model = InvoiceItem
        fields = [
            'invoice', 'description', 'quantity', 'unit_price',
            'tax_percentage', 'discount_percentage', 'contract_item',
            'notes', 'order', 'tenant'
        ]
    
    def validate(self, data):
        # Validar que cantidad y precio son positivos
        if data.get('quantity', 0) <= 0:
            raise serializers.ValidationError(
                {"quantity": "La cantidad debe ser mayor que cero."}
            )
        
        if data.get('unit_price', 0) <= 0:
            raise serializers.ValidationError(
                {"unit_price": "El precio unitario debe ser mayor que cero."}
            )
        
        return data
