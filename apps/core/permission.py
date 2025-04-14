from rest_framework import permissions


class IsAdministrator(permissions.BasePermission):
    """
    Permission to only allow administrators to access the view.
    """

    def has_permission(self, request, view):
        # Check if user has admin role
        if request.user and request.user.is_authenticated:
            # Check for superuser
            if request.user.is_superuser:
                return True

            # Check if the user has an admin role
            return hasattr(request.user, 'user_roles') and request.user.user_roles.filter(
                role__name='Administrator',
                is_active=True,
                is_deleted=False
            ).exists()
        return False


class IsTenantMember(permissions.BasePermission):
    """
    Permission to only allow members of the current tenant to access the view.
    """

    def has_permission(self, request, view):
        if request.user and request.user.is_authenticated:
            # Superusers have access to all tenants
            if request.user.is_superuser:
                return True

            # If tenant is not set on the user, deny access
            if not hasattr(request.user, 'tenant') or not request.user.tenant:
                return False

            # Get tenant from request
            tenant_id = request.parser_context.get('kwargs', {}).get('tenant_id')

            # If tenant_id is not in URL, allow access to user's assigned tenant
            if not tenant_id:
                return True

            # Check if user belongs to the requested tenant
            return str(request.user.tenant.id) == str(tenant_id)
        return False
