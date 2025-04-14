from rest_framework import status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from apps.core.models import ConfigurationSetting
from apps.core.serializers import ConfigurationSettingSerializer
from apps.core.permission import IsAdministrator
from apps.core.utils import create_audit_log, get_client_ip


class ConfigurationSettingViewSet(GenericViewSet):
    """
    API endpoint that allows system configuration settings to be viewed or edited.
    """
    queryset = ConfigurationSetting.objects.filter(is_active=True, is_deleted=False)
    serializer_class = ConfigurationSettingSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdministrator]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by category if provided
        category = self.request.query_params.get('category', None)
        if category:
            queryset = queryset.filter(category=category)
            
        # Filter by key prefix if provided
        key_prefix = self.request.query_params.get('key_prefix', None)
        if key_prefix:
            queryset = queryset.filter(key__startswith=key_prefix)
            
        return queryset
    
    def list(self, request):
        """Get all configuration settings"""
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    def retrieve(self, request, pk=None):
        """Get a single configuration setting"""
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
    
    def create(self, request):
        """Create a new configuration setting"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(created_by=request.user, updated_by=request.user)
        
        # Create audit log
        create_audit_log(
            user=request.user,
            action='CREATE',
            model_name='ConfigurationSetting',
            instance_id=serializer.instance.id,
            description=f"Created configuration setting: {serializer.instance.key}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    def update(self, request, pk=None):
        """Update a configuration setting"""
        instance = self.get_object()
        
        # Check if setting is editable
        if not instance.is_editable:
            return Response(
                {"detail": "This configuration setting is not editable."},
                status=status.HTTP_403_FORBIDDEN
            )
            
        serializer = self.get_serializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(updated_by=request.user)
        
        # Create audit log
        create_audit_log(
            user=request.user,
            action='UPDATE',
            model_name='ConfigurationSetting',
            instance_id=instance.id,
            description=f"Updated configuration setting: {instance.key}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        return Response(serializer.data)
    
    def partial_update(self, request, pk=None):
        """Partially update a configuration setting"""
        instance = self.get_object()
        
        # Check if setting is editable
        if not instance.is_editable:
            return Response(
                {"detail": "This configuration setting is not editable."},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(updated_by=request.user)

        # Create audit log
        create_audit_log(
            user=request.user,
            action='UPDATE',
            model_name='ConfigurationSetting',
            instance_id=instance.id,
            description=f"Partially updated configuration setting: {instance.key}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )

        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def categories(self, request):
        """
        Get a list of all available configuration categories.
        """
        categories = ConfigurationSetting.objects.filter(
            is_active=True,
            is_deleted=False
        ).values_list('category', flat=True).distinct()

        return Response(sorted(list(set(categories))))

    @action(detail=False, methods=['get'])
    def by_category(self, request):
        """
        Get configuration settings grouped by category
        """
        categories = ConfigurationSetting.objects.filter(
            is_active=True,
            is_deleted=False
        ).values_list('category', flat=True).distinct()

        result = {}
        for category in categories:
            settings = ConfigurationSetting.objects.filter(
                category=category,
                is_active=True,
                is_deleted=False
            )
            serializer = self.get_serializer(settings, many=True)
            result[category] = serializer.data

        return Response(result)

    @action(detail=False, methods=['get'])
    def by_key(self, request):
        """
        Get a configuration setting by its key
        """
        key = request.query_params.get('key', None)
        if not key:
            return Response(
                {"detail": "Key parameter is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            setting = ConfigurationSetting.objects.get(
                key=key,
                is_active=True,
                is_deleted=False
            )
            serializer = self.get_serializer(setting)
            return Response(serializer.data)
        except ConfigurationSetting.DoesNotExist:
            return Response(
                {"detail": f"No configuration found for key: {key}"},
                status=status.HTTP_404_NOT_FOUND
            )
