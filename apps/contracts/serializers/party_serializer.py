from rest_framework import serializers
from apps.contracts.models import ContractParty


class ContractPartySerializer(serializers.ModelSerializer):
    """
    Serializador para partes de contratos
    """
    party_type_display = serializers.CharField(source='get_party_type_display', read_only=True)
    user_details = serializers.SerializerMethodField()
    organization_details = serializers.SerializerMethodField()
    
    class Meta:
        model = ContractParty
        fields = [
            'id', 'contract', 'party_type', 'party_type_display',
            'user', 'user_details', 'organization', 'organization_details', 
            'name', 'identification_type', 'identification_number',
            'email', 'phone', 'address', 'role', 'notes',
            'tenant', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'user_details', 'organization_details']
    
    def get_user_details(self, obj):
        if obj.user:
            return {
                'id': obj.user.id,
                'email': obj.user.email,
                'full_name': f"{obj.user.first_name} {obj.user.last_name}",
                'is_active': obj.user.is_active
            }
        return None
    
    def get_organization_details(self, obj):
        if obj.organization:
            return {
                'id': obj.organization.id,
                'name': obj.organization.name,
                'tax_id': obj.organization.tax_id,
                'is_active': obj.organization.is_active
            }
        return None
    
    def validate(self, data):
        # Verificar que al menos una de las tres opciones de parte esté presente
        if not data.get('user') and not data.get('organization') and not data.get('name'):
            raise serializers.ValidationError(
                "Debe especificar al menos un usuario, organización o nombre para la parte."
            )
            
        # Si el tipo de parte es CONTRACTOR o CONTRACTING, debería tener usuario u organización
        if data.get('party_type') in ['CONTRACTOR', 'CONTRACTING'] and not data.get('user') and not data.get('organization'):
            raise serializers.ValidationError(
                f"Para el tipo de parte '{data.get('party_type')}' debe especificar un usuario o una organización."
            )
            
        return data
