from rest_framework import serializers
from apps.user.models import LoginAttempt, UserActivity, UserSession


class LoginAttemptSerializer(serializers.ModelSerializer):
    """Serializer for login attempts"""
    
    class Meta:
        model = LoginAttempt
        fields = ['id', 'email', 'ip_address', 'user_agent', 'successful', 
                 'created_at', 'tenant']
        read_only_fields = ['id', 'created_at']


class UserActivitySerializer(serializers.ModelSerializer):
    """Serializer for user activities"""
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_full_name = serializers.CharField(source='user.full_name', read_only=True)
    
    class Meta:
        model = UserActivity
        fields = ['id', 'user', 'user_email', 'user_full_name', 'activity_type', 
                 'description', 'ip_address', 'user_agent', 'module', 'page', 
                 'tenant', 'created_at']
        read_only_fields = ['id', 'created_at', 'user_email', 'user_full_name']


class UserSessionSerializer(serializers.ModelSerializer):
    """Serializer for user sessions"""
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_full_name = serializers.CharField(source='user.full_name', read_only=True)
    
    class Meta:
        model = UserSession
        fields = ['id', 'user', 'user_email', 'user_full_name', 'session_key', 
                 'ip_address', 'user_agent', 'device_type', 'browser', 'os', 
                 'expires_at', 'is_expired', 'logout_time', 'last_activity', 
                 'tenant', 'created_at']
        read_only_fields = ['id', 'created_at', 'user_email', 'user_full_name', 'last_activity']
