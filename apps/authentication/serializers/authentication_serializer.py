from rest_framework import serializers
from apps.user.models.user import User


class AuthenticationSerializer(serializers.Serializer):
    """
    Serializer para manejar la autenticación de usuarios.
    """
    email = serializers.EmailField(required=True)
    password = serializers.CharField(required=True, write_only=True, style={'input_type': 'password'})
    tenant = serializers.CharField(required=False, allow_blank=True)


class LogoutSerializer(serializers.Serializer):
    """
    Serializer para manejar el cierre de sesión.
    """
    refresh_token = serializers.CharField(required=True)


class UserProfileSerializer(serializers.ModelSerializer):
    """
    Serializer para información del perfil de usuario.
    """
    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'phone_number', 'document_type', 
                  'document_number', 'avatar', 'is_active', 'is_staff', 'is_superuser']
        read_only_fields = fields


class RoleSerializer(serializers.Serializer):
    """
    Serializer para roles de usuario.
    """
    id = serializers.UUIDField()
    name = serializers.CharField()


class UserAuthResponseSerializer(serializers.Serializer):
    """
    Serializer para la respuesta de autenticación con datos del usuario.
    """
    user = UserProfileSerializer()
    roles = RoleSerializer(many=True)
    tenant = serializers.CharField(allow_null=True)
    permissions = serializers.ListField(child=serializers.CharField())
