from rest_framework import status, permissions, filters
from rest_framework.viewsets import GenericViewSet
from rest_framework.response import Response
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Count

from apps.core.models import AuditLog, SystemLog
from apps.core.serializers import AuditLogSerializer, SystemLogSerializer
from apps.core.permissions import IsAdministrator

class AuditLogViewSet(GenericViewSet):
    """
    API endpoint that allows audit logs to be viewed.
    """
    queryset = AuditLog.objects.all()
    serializer_class = AuditLogSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdministrator]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['action', 'model_name', 'tenant']
    search_fields = ['description', 'instance_id']
    ordering_fields = ['created_at', 'action', 'model_name']
    ordering = ['-created_at']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Date range filtering
        start_date = self.request.query_params.get('start_date', None)
        end_date = self.request.query_params.get('end_date', None)
        
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)
            
        # Filter by user
        user_id = self.request.query_params.get('user_id', None)
        if user_id:
            queryset = queryset.filter(created_by_id=user_id)
            
        return queryset
    
    def list(self, request):
        """Get all audit logs with pagination"""
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
            
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    def retrieve(self, request, pk=None):
        """Get a single audit log by ID"""
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def actions(self, request):
        """Get list of all action types"""
        actions = AuditLog.objects.values_list('action', flat=True).distinct()
        return Response(sorted(list(set(actions))))
    
    @action(detail=False, methods=['get'])
    def models(self, request):
        """Get list of all model names in the logs"""
        models = AuditLog.objects.values_list('model_name', flat=True).distinct()
        return Response(sorted(list(set(models))))
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get statistics about audit logs"""
        # Date range filtering
        start_date = request.query_params.get('start_date', None)
        end_date = request.query_params.get('end_date', None)
        
        queryset = AuditLog.objects.all()
        
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)
        
        # Get count by action
        actions = queryset.values('action').annotate(count=Count('action')).order_by('-count')
        
        # Get count by model
        models = queryset.values('model_name').annotate(count=Count('model_name')).order_by('-count')
        
        # Get count by user
        users = queryset.values('created_by__email').annotate(count=Count('created_by')).order_by('-count')
        
        return Response({
            'total_logs': queryset.count(),
            'by_action': actions,
            'by_model': models,
            'by_user': users
        })

class SystemLogViewSet(GenericViewSet):
    """
    API endpoint that allows system logs to be viewed.
    """
    queryset = SystemLog.objects.all()
    serializer_class = SystemLogSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdministrator]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['level', 'source', 'tenant']
    search_fields = ['message']
    ordering_fields = ['created_at', 'level', 'source']
    ordering = ['-created_at']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Date range filtering
        start_date = self.request.query_params.get('start_date', None)
        end_date = self.request.query_params.get('end_date', None)
        
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)
            
        return queryset
    
    def list(self, request):
        """Get all system logs with pagination"""
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
            
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    def retrieve(self, request, pk=None):
        """Get a single system log by ID"""
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def levels(self, request):
        """Get list of all log levels"""
        levels = SystemLog.objects.values_list('level', flat=True).distinct()
        return Response(sorted(list(set(levels))))
    
    @action(detail=False, methods=['get'])
    def sources(self, request):
        """Get list of all log sources"""
        sources = SystemLog.objects.values_list('source', flat=True).distinct()
        return Response(sorted(list(set(sources))))
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get statistics about system logs"""
        # Date range filtering
        start_date = request.query_params.get('start_date', None)
        end_date = request.query_params.get('end_date', None)
        
        queryset = SystemLog.objects.all()
        
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)
        
        # Get count by level
        levels = queryset.values('level').annotate(count=Count('level')).order_by('-count')
        
        # Get count by source
        sources = queryset.values('source').annotate(count=Count('source')).order_by('-count')
        
        return Response({
            'total_logs': queryset.count(),
            'by_level': levels,
            'by_source': sources
        })
    
    @action(detail=False, methods=['get'])
    def errors(self, request):
        """Get only error and critical logs"""
        queryset = SystemLog.objects.filter(level__in=['ERROR', 'CRITICAL']).order_by('-created_at')
        
        # Date range filtering
        start_date = request.query_params.get('start_date', None)
        end_date = request.query_params.get('end_date', None)
        
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)
        
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
            
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
