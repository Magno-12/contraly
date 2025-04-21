from rest_framework import serializers
from apps.contracts.models import ContractRevision


class ContractRevisionSerializer(serializers.ModelSerializer):
    """
    Serializador para revisiones de contratos
    """
    revision_type_display = serializers.CharField(source='get_revision_type_display', read_only=True)
    user_name = serializers.SerializerMethodField()
    
    class Meta:
        model = ContractRevision
        fields = [
            'id', 'contract', 'revision_type', 'revision_type_display',
            'description', 'previous_data', 'new_data', 'document',
            'revision_date', 'tenant', 'is_active', 'created_by',
            'user_name', 'created_at'
        ]
        read_only_fields = ['id', 'revision_date', 'created_at', 'user_name']
    
    def get_user_name(self, obj):
        if obj.created_by:
            return f"{obj.created_by.first_name} {obj.created_by.last_name}"
        return None
