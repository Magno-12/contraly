from rest_framework import serializers

from apps.core.models import AuditLog, SystemLog


class AuditLogSerializer(serializers.ModelSerializer):
    created_by_email = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = ['id', 'action', 'model_name', 'instance_id', 'description',
                 'ip_address', 'user_agent', 'tenant', 'data', 'created_at',
                 'created_by', 'created_by_email']
        read_only_fields = ['id', 'created_at', 'created_by', 'created_by_email']

    def get_created_by_email(self, obj):
        if obj.created_by:
            return obj.created_by.email
        return None


class SystemLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemLog
        fields = ['id', 'level', 'source', 'message', 'stack_trace',
                 'tenant', 'created_at']
        read_only_fields = ['id', 'created_at']
