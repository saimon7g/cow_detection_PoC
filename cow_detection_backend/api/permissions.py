from rest_framework.permissions import BasePermission


def get_user_type(user):
    try:
        return user.profile.user_type
    except AttributeError:
        return None


def is_company_agent(user):
    return user.is_authenticated and get_user_type(user) == 'company_agent'


def is_farmer(user):
    return user.is_authenticated and get_user_type(user) == 'farmer'


def is_admin(user):
    return user.is_authenticated and get_user_type(user) == 'admin'


class IsCompanyAgent(BasePermission):
    """Allow access only to company agents."""
    message = 'Only company agents can perform this action.'

    def has_permission(self, request, view):
        return is_company_agent(request.user)


class IsFarmer(BasePermission):
    """Allow access only to farmers."""
    message = 'Only farmers can perform this action.'

    def has_permission(self, request, view):
        return is_farmer(request.user)


class IsAdminUser(BasePermission):
    """Allow access only to admins."""
    message = 'Only admins can perform this action.'

    def has_permission(self, request, view):
        return is_admin(request.user)


class IsCompanyAgentOrFarmer(BasePermission):
    """Allow access to company agents or farmers."""
    message = 'Only company agents or farmers can perform this action.'

    def has_permission(self, request, view):
        return is_company_agent(request.user) or is_farmer(request.user)


class IsCompanyAgentOrAdmin(BasePermission):
    """Allow access to company agents or admins."""
    message = 'Only company agents or admins can perform this action.'

    def has_permission(self, request, view):
        return is_company_agent(request.user) or is_admin(request.user)
