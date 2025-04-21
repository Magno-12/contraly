from rest_framework import serializers
from apps.contracts.models import ContractDocument


class ContractDocumentSerializer(serializers.ModelSerializer):
    """
    Serializador para documentos de contratos
    """
    document_type_display = serializers.CharField(source='get_document_type_display', read_only=True)
    file_url = serializers.SerializerMethodField()
    
    class Meta:
        model = ContractDocument
        fields = [
            'id', 'contract', 'document_type', 'document_type_display',
            'title', 'description', 'file', 'file_url', 
            'is_signed', 'signing_date', 'reference_number',
            'version', 'is_current_version', 'parent_document',
            'tenant', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'file_url']
    
    def get_file_url(self, obj):
        if obj.file:
            return obj.file.url
        return None
    
    def validate(self, data):
        # Si es una nueva versión, verificar que existe un documento padre
        if data.get('is_current_version') and not data.get('parent_document'):
            if 'version' in data and data['version'] != '1.0':
                raise serializers.ValidationError(
                    "Para una versión mayor a 1.0, debe especificar el documento original."
                )
                
        return data
