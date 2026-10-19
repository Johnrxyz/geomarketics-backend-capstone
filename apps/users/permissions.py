from rest_framework.permissions import IsAuthenticated


class PasswordSetupPermission(IsAuthenticated):
    """Keep temporary-password vendor sessions inside the password setup flow."""
    allowed_paths = {
        '/api/v1/auth/me/',
        '/api/v1/auth/setup-password/',
        '/api/v1/auth/logout/',
    }

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        user = request.user
        if user.is_authenticated and user.must_change_password:
            return request.path in self.allowed_paths
        return True
