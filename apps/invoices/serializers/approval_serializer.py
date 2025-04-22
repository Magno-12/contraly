from rest_framework import serializers
from apps.invoices.models import InvoiceApproval


class InvoiceApprovalSerializer(serializers.ModelSerializer):
    """
    Serializador para aprobaciones de cuentas de cobro
    """
    approval_type_display = serializers.CharField(source='get_approval_type_display', read_only=True)
    result_display = serializers.CharField(source='get_result_display', read_only=True)
    approver_name = serializers.SerializerMethodField()
    
    class Meta:
        model = InvoiceApproval
        fields = [
            'id', 'invoice', 'approval_type', 'approval_type_display',
            'approver', 'approver_name', 'assigned_date', 'due_date',
            'result', 'result_display', 'approval_date', 'comments',
            'tenant', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'assigned_date', 'created_at', 'updated_at', 'approver_name']
    
    def get_approver_name(self, obj):
        if obj.approver:
            return f"{obj.approver.first_name} {obj.approver.last_name}"
        return None
    
    def validate(self, data):
        # Validar que el resultado no es PENDING si se proporciona fecha de aprobación
        if data.get('approval_date') and data.get('result') == 'PENDING':
            raise serializers.ValidationError(
                {"result": "No se puede establecer una fecha de aprobación para un resultado pendiente."}
            )
        
        # Validar que se proporciona fecha de aprobación si el resultado no es PENDING
        if data.get('result') and data.get('result') != 'PENDING' and not data.get('approval_date'):
            from django.utils import timezone
            data['approval_date'] = timezone.now()
        
        return data
