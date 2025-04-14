from rest_framework import serializers

from apps.core.models import ConfigurationSetting


class ConfigurationSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConfigurationSetting
        fields = ['id', 'key', 'value', 'description', 'is_editable', 'is_encrypted',
                 'category', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate(self, attrs):
        # If updating, check if setting is editable
        if self.instance and not self.instance.is_editable:
            raise serializers.ValidationError({"detail": "This configuration setting is not editable."})
        return attrs
