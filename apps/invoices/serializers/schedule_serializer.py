from rest_framework import serializers
from apps.invoices.models import InvoiceSchedule


class InvoiceScheduleSerializer(serializers.ModelSerializer):
    """
    Serializador para programaciones de cuentas de cobro
    """
    schedule_type_display = serializers.CharField(source='get_schedule_type_display', read_only=True)
    contract_info = serializers.SerializerMethodField()
    
    class Meta:
        model = InvoiceSchedule
        fields = [
            'id', 'contract', 'contract_info', 'name', 'description',
            'schedule_type', 'schedule_type_display', 'start_date', 'end_date',
            'custom_days', 'day_of_month', 'is_auto_generate', 'auto_approve',
            'is_active', 'last_generated', 'next_generation', 'value',
            'tenant', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'created_at', 'updated_at', 'contract_info',
            'schedule_type_display', 'last_generated', 'next_generation'
        ]
    
    def get_contract_info(self, obj):
        if obj.contract:
            return {
                'id': obj.contract.id,
                'contract_number': obj.contract.contract_number,
                'title': obj.contract.title,
                'start_date': obj.contract.start_date,
                'end_date': obj.contract.end_date
            }
        return None
    
    def validate(self, data):
        # Validar que la fecha de inicio es futura o igual a hoy
        from django.utils import timezone
        today = timezone.now().date()
        
        if data.get('start_date') and data.get('start_date') < today:
            raise serializers.ValidationError(
                {"start_date": "La fecha de inicio no puede ser anterior a hoy."}
            )
        
        # Validar que la fecha de fin es posterior a la de inicio
        if data.get('start_date') and data.get('end_date') and data.get('end_date') < data.get('start_date'):
            raise serializers.ValidationError(
                {"end_date": "La fecha de finalización debe ser posterior a la fecha de inicio."}
            )
        
        # Validar configuración específica según el tipo de programación
        schedule_type = data.get('schedule_type')
        
        if schedule_type == 'CUSTOM' and not data.get('custom_days'):
            raise serializers.ValidationError(
                {"custom_days": "Para programación personalizada se requiere especificar los días."}
            )
        
        if schedule_type in ['MONTHLY', 'BIMONTHLY', 'QUARTERLY'] and data.get('day_of_month'):
            if data.get('day_of_month') < 1 or data.get('day_of_month') > 31:
                raise serializers.ValidationError(
                    {"day_of_month": "El día del mes debe estar entre 1 y 31."}
                )
        
        return data
    
    def create(self, validated_data):
        # Forzar recálculo de la próxima fecha de generación
        instance = super().create(validated_data)
        instance.save(recalculate=True)
        return instance
    
    def update(self, instance, validated_data):
        # Forzar recálculo de la próxima fecha de generación si cambian parámetros relevantes
        recalculate = False
        for field in ['schedule_type', 'start_date', 'end_date', 'custom_days', 'day_of_month', 'is_active']:
            if field in validated_data and validated_data[field] != getattr(instance, field):
                recalculate = True
                break
        
        instance = super().update(instance, validated_data)
        
        if recalculate:
            instance.save(recalculate=True)
        
        return instance
