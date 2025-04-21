from rest_framework import serializers
from apps.contracts.models import ContractStatus, ContractType


class ContractStatusSerializer(serializers.ModelSerializer):
    """
    Serializador para estados de contratos
    """
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    changed_by_name = serializers.SerializerMethodField()
    
    class Meta:
        model = ContractStatus
        fields = [
            'id', 'contract', 'status', 'status_display',
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


class ContractTypeSerializer(serializers.ModelSerializer):
    """
    Serializador para tipos de contratos
    """
    contract_count = serializers.SerializerMethodField()
    
    class Meta:
        model = ContractType
        fields = [
            'id', 'name', 'code', 'description', 'template',
            'requires_approval', 'sequential_number', 'tenant',
            'is_active', 'created_at', 'updated_at', 'contract_count'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'contract_count']
    
    def get_contract_count(self, obj):
        return obj.contracts.filter(is_active=True, is_deleted=False).count()
