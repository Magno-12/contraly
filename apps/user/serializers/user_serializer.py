from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from apps.user.models.user import User, UserProfile

class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ['bio', 'position', 'department', 'address', 'birth_date', 
                  'timezone', 'language', 'linkedin', 'twitter', 'facebook',
                  'bank_name', 'bank_account_type', 'bank_account_number', 
                  'contract_role', 'contract_value']


class UserListSerializer(serializers.ModelSerializer):
    """Serializer for listing users"""
    full_name = serializers.CharField(read_only=True)
    role_names = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'full_name', 
                  'is_active', 'role_names', 'tenant', 'date_joined', 
                  'last_login', 'avatar']
        read_only_fields = ['id', 'date_joined', 'last_login']
    
    def get_role_names(self, obj):
        return list(obj.user_roles.filter(
            is_active=True, 
            is_deleted=False
        ).values_list('role__name', flat=True))


class UserDetailSerializer(serializers.ModelSerializer):
    """Serializer for detailed user information"""
    full_name = serializers.CharField(read_only=True)
    profile = UserProfileSerializer(required=False)
    role_names = serializers.SerializerMethodField()
    roles = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'full_name', 
                  'phone_number', 'is_active', 'is_staff', 'is_superuser',
                  'avatar', 'document_type', 'document_number', 
                  'date_joined', 'last_login', 'last_login_ip',
                  'tenant', 'profile', 'role_names', 'roles']
        read_only_fields = ['id', 'date_joined', 'last_login', 'last_login_ip']
    
    def get_role_names(self, obj):
        return list(obj.user_roles.filter(
            is_active=True, 
            is_deleted=False
        ).values_list('role__name', flat=True))
    
    def get_roles(self, obj):
        return list(obj.user_roles.filter(
            is_active=True, 
            is_deleted=False
        ).values('role__id', 'role__name'))
    
    def create(self, validated_data):
        profile_data = validated_data.pop('profile', None)
        user = User.objects.create(**validated_data)
        
        if profile_data:
            UserProfile.objects.create(user=user, **profile_data)
        else:
            # Create default empty profile
            UserProfile.objects.create(user=user)
            
        return user
    
    def update(self, instance, validated_data):
        profile_data = validated_data.pop('profile', None)
        
        # Update user instance
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Update profile if provided
        if profile_data and hasattr(instance, 'profile'):
            for attr, value in profile_data.items():
                setattr(instance.profile, attr, value)
            instance.profile.save()
        elif profile_data:
            UserProfile.objects.create(user=instance, **profile_data)
            
        return instance


class UserCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating new users"""
    password = serializers.CharField(write_only=True, required=True)
    password_confirm = serializers.CharField(write_only=True, required=True)
    profile = UserProfileSerializer(required=False)
    roles = serializers.ListField(
        child=serializers.UUIDField(), 
        required=False, 
        write_only=True
    )
    
    class Meta:
        model = User
        fields = ['id', 'email', 'password', 'password_confirm', 'first_name', 
                  'last_name', 'phone_number', 'is_active', 'is_staff', 
                  'avatar', 'document_type', 'document_number', 'tenant', 
                  'profile', 'roles']
        read_only_fields = ['id']
    
    def validate(self, data):
        # Validate that passwords match
        if data.get('password') != data.get('password_confirm'):
            raise serializers.ValidationError({"password_confirm": "Passwords do not match."})
        
        # Validate password strength
        try:
            validate_password(data.get('password'), self.instance)
        except ValidationError as e:
            raise serializers.ValidationError({"password": list(e.messages)})
            
        return data
    
    def create(self, validated_data):
        # Remove password_confirm and roles field from validated data
        validated_data.pop('password_confirm', None)
        roles = validated_data.pop('roles', [])
        profile_data = validated_data.pop('profile', None)
        
        # Create user with password
        password = validated_data.pop('password')
        user = User.objects.create(**validated_data)
        user.set_password(password)
        user.save()
        
        # Create user profile
        if profile_data:
            UserProfile.objects.create(user=user, **profile_data)
        else:
            UserProfile.objects.create(user=user)
        
        # Assign roles if provided
        from apps.user.models import Role, UserRole
        for role_id in roles:
            try:
                role = Role.objects.get(id=role_id)
                UserRole.objects.create(
                    user=user,
                    role=role,
                    created_by=self.context['request'].user if 'request' in self.context else None
                )
            except Role.DoesNotExist:
                pass
                
        return user


class PasswordChangeSerializer(serializers.Serializer):
    """Serializer for changing password"""
    current_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True)
    new_password_confirm = serializers.CharField(required=True)
    
    def validate(self, data):
        # Validate that new passwords match
        if data.get('new_password') != data.get('new_password_confirm'):
            raise serializers.ValidationError(
                {"new_password_confirm": "New passwords do not match."}
            )
            
        # Validate current password
        user = self.context['request'].user
        if not user.check_password(data.get('current_password')):
            raise serializers.ValidationError(
                {"current_password": "Current password is incorrect."}
            )
            
        # Validate new password strength
        try:
            validate_password(data.get('new_password'), user)
        except ValidationError as e:
            raise serializers.ValidationError({"new_password": list(e.messages)})
            
        return data
