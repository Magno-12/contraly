from rest_framework import serializers
from apps.contracts.models import Contract, ContractType
from apps.contracts.models import ContractStatus


class ContractListSerializer(serializers.ModelSerializer):
    """
    Serializador simplificado para listar contratos
    """
    contract_type_name = serializers.CharField(source='contract_type.name', read_only=True)
    status = serializers.SerializerMethodField()
    
    class Meta:
        model = Contract
        fields = [
            'id', 'contract_number', 'title', 'contract_type', 'contract_type_name',
            'start_date', 'end_date', 'value', 'currency', 'status', 'is_active',
            'created_at'
        ]
        read_only_fields = ['id', 'created_at', 'status']
    
    def get_status(self, obj):
        current_status = obj.current_status
        if current_status:
            return {
                'id': current_status.id,
                'status': current_status.status,
                'status_display': current_status.get_status_display(),
                'start_date': current_status.start_date
            }
        return None


class ContractSerializer(serializers.ModelSerializer):
    """
    Serializador base para contratos
    """
    class Meta:
        model = Contract
        fields = [
            'id', 'contract_number', 'title', 'contract_type', 'description',
            'start_date', 'end_date', 'signing_date', 'value', 'currency',
            'supervisor', 'special_clauses', 'reference_number', 'department',
            'is_renewal', 'parent_contract', 'requires_performance_bond',
            'tenant', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ContractDetailSerializer(serializers.ModelSerializer):
    """
    Serializador detallado para contratos con relaciones incluidas
    """
    contract_type_name = serializers.CharField(source='contract_type.name', read_only=True)
    supervisor_name = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    parties = serializers.SerializerMethodField()
    documents = serializers.SerializerMethodField()
    
    class Meta:
        model = Contract
        fields = [
            'id', 'contract_number', 'title', 'contract_type', 'contract_type_name',
            'description', 'start_date', 'end_date', 'signing_date', 'value', 
            'currency', 'supervisor', 'supervisor_name', 'special_clauses', 
            'reference_number', 'department', 'is_renewal', 'parent_contract', 
            'requires_performance_bond', 'tenant', 'is_active', 'created_at', 
            'updated_at', 'status', 'parties', 'documents'
        ]
        read_only_fields = [
            'id', 'created_at', 'updated_at', 'status', 'parties', 'documents',
            'contract_type_name', 'supervisor_name'
        ]
    
    def get_supervisor_name(self, obj):
        if obj.supervisor:
            return f"{obj.supervisor.first_name} {obj.supervisor.last_name}"
        return None
    
    def get_status(self, obj):
        from apps.contracts.serializers.status_serializer import ContractStatusSerializer
        current_status = obj.current_status
        if current_status:
            return ContractStatusSerializer(current_status).data
        return None
    
    def get_parties(self, obj):
        from apps.contracts.serializers.party_serializer import ContractPartySerializer
        parties = obj.parties.filter(is_active=True, is_deleted=False)
        return ContractPartySerializer(parties, many=True).data
    
    def get_documents(self, obj):
        from apps.contracts.serializers.document_serializer import ContractDocumentSerializer
        documents = obj.documents.filter(is_active=True, is_deleted=False)
        return ContractDocumentSerializer(documents, many=True).data


class ContractCreateSerializer(serializers.ModelSerializer):
    """
    Serializador para crear nuevos contratos
    """
    status = serializers.ChoiceField(
        choices=ContractStatus.STATUS_CHOICES,
        write_only=True,
        default='DRAFT'
    )
    
    class Meta:
        model = Contract
        fields = [
            'contract_number', 'title', 'contract_type', 'description',
            'start_date', 'end_date', 'signing_date', 'value', 'currency',
            'supervisor', 'special_clauses', 'reference_number', 'department',
            'is_renewal', 'parent_contract', 'requires_performance_bond',
            'tenant', 'status'
        ]
    
    def validate(self, data):
        # Verificar que la fecha de fin sea posterior a la fecha de inicio
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        
        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError(
                {"end_date": "La fecha de finalización debe ser posterior a la fecha de inicio."}
            )
        
        return data
    
    def create(self, validated_data):
        # Extraer datos del estado para crear el estado inicial del contrato
        status_data = validated_data.pop('status', 'DRAFT')
        
        # Crear contrato
        contract = super().create(validated_data)
        
        # Crear estado inicial
        ContractStatus.objects.create(
            contract=contract,
            status=status_data,
            created_by=self.context.get('request').user if 'request' in self.context else None,
            updated_by=self.context.get('request').user if 'request' in self.context else None,
            tenant=contract.tenant
        )
        
        return contract
