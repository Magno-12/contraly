from django.contrib.auth.hashers import check_password
from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.viewsets import GenericViewSet
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import AuthenticationFailed
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from apps.user.models import User, UserRole, RolePermission
from apps.authentication.serializers.authentication_serializer import (
    AuthenticationSerializer,
    LogoutSerializer,
    UserAuthResponseSerializer,
    UserProfileSerializer,
    RoleSerializer
)
from apps.core.utils import get_client_ip, create_audit_log


class AuthenticationViewSet(GenericViewSet):
    """
    ViewSet para manejar la autenticación de usuarios en el sistema Contraly.
    """
    authentication_classes = [JWTAuthentication]

    def get_serializer_class(self):
        if self.action == 'login':
            return AuthenticationSerializer
        return LogoutSerializer

    def get_permissions(self):
        if self.action == 'login':
            permission_classes = [AllowAny]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    @swagger_auto_schema(
        operation_description="Inicia sesión de usuario con email y password",
        request_body=AuthenticationSerializer,
        responses={
            200: openapi.Response(
                description="Login exitoso",
                schema=UserAuthResponseSerializer
            ),
            401: "Credenciales inválidas"
        }
    )
    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def login(self, request):
        """
        Maneja el inicio de sesión de usuarios y proporciona tokens JWT.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user_data = serializer.validated_data

        try:
            user = User.objects.get(email=user_data['email'])
        except User.DoesNotExist:
            raise AuthenticationFailed(
                "El usuario con este email no existe"
            )

        if not check_password(user_data['password'], user.password):
            raise AuthenticationFailed("Contraseña incorrecta")

        if not user.is_active:
            raise AuthenticationFailed("Esta cuenta ha sido desactivada")
            
        if user.is_deleted:
            raise AuthenticationFailed("Esta cuenta ha sido eliminada")

        # Verificar tenant si se especificó
        tenant = user_data.get('tenant')
        if tenant and hasattr(user, 'tenant') and user.tenant:
            if user.tenant.subdomain != tenant:
                raise AuthenticationFailed("Usuario no tiene acceso a este tenant")

        # Generar tokens
        refresh = RefreshToken.for_user(user)

        # Registrar la actividad de inicio de sesión
        create_audit_log(
            user=user,
            action='LOGIN',
            model_name='User',
            instance_id=user.id,
            description=f"Inicio de sesión exitoso: {user.email}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            tenant=user.tenant
        )

        # Obtener roles y permisos del usuario
        roles = []
        permissions = []
        
        user_roles = UserRole.objects.filter(
            user=user,
            is_active=True,
            is_deleted=False
        ).select_related('role')
        
        for user_role in user_roles:
            roles.append({
                'id': user_role.role.id,
                'name': user_role.role.name
            })
            
            # Obtener permisos asociados a este rol
            role_permissions = RolePermission.objects.filter(
                role=user_role.role,
                is_active=True,
                is_deleted=False
            ).select_related('permission')
            
            for role_permission in role_permissions:
                permission_code = role_permission.permission.code
                if permission_code not in permissions:
                    permissions.append(permission_code)

        return Response({
            "tokens": {
                "refresh": str(refresh),
                "access": str(refresh.access_token),
            },
            "user": UserProfileSerializer(user).data,
            "roles": roles,
            "tenant": user.tenant.subdomain if user.tenant else None,
            "permissions": permissions
        }, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_description="Cierra la sesión del usuario",
        request_body=LogoutSerializer,
        responses={
            200: "Sesión cerrada exitosamente",
            400: "Token inválido"
        }
    )
    @action(detail=False, methods=['post'])
    def logout(self, request):
        """
        Cierra la sesión del usuario y añade el token de refresco a la lista negra.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        refresh_token = serializer.validated_data['refresh_token']

        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
            
            # Registrar la actividad de cierre de sesión
            create_audit_log(
                user=request.user,
                action='LOGOUT',
                model_name='User',
                instance_id=request.user.id,
                description=f"Cierre de sesión exitoso: {request.user.email}",
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                tenant=request.user.tenant
            )
            
        except Exception:
            return Response(
                {"error": "Token inválido o expirado"},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response(
            {"message": "Sesión cerrada exitosamente"},
            status=status.HTTP_200_OK
        )

    @swagger_auto_schema(
        operation_description="Verifica si el token actual es válido",
        responses={
            200: "Token válido",
            401: "Token inválido o expirado"
        }
    )
    @action(detail=False, methods=['get'])
    def verify(self, request):
        """
        Verifica si el token actual es válido.
        """
        user = request.user
        
        # Obtener roles y permisos del usuario
        roles = []
        permissions = []
        
        user_roles = UserRole.objects.filter(
            user=user,
            is_active=True,
            is_deleted=False
        ).select_related('role')
        
        for user_role in user_roles:
            roles.append({
                'id': user_role.role.id,
                'name': user_role.role.name
            })
            
            # Obtener permisos asociados a este rol
            role_permissions = RolePermission.objects.filter(
                role=user_role.role,
                is_active=True,
                is_deleted=False
            ).select_related('permission')
            
            for role_permission in role_permissions:
                permission_code = role_permission.permission.code
                if permission_code not in permissions:
                    permissions.append(permission_code)

        return Response({
            "user": UserProfileSerializer(user).data,
            "roles": roles,
            "tenant": user.tenant.subdomain if user.tenant else None,
            "permissions": permissions
        }, status=status.HTTP_200_OK)
