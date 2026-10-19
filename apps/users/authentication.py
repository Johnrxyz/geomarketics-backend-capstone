from rest_framework.exceptions import PermissionDenied
from rest_framework_simplejwt.authentication import JWTAuthentication


class SetupGatedJWTAuthentication(JWTAuthentication):
    """Reject normal API use while a temporary-password account is incomplete."""
    allowed_paths = {
        '/api/v1/auth/me/',
        '/api/v1/auth/setup-password/',
        '/api/v1/auth/logout/',
    }

    def authenticate(self, request):
        result = super().authenticate(request)
        if result:
            user, token = result
            if user.must_change_password and request.path not in self.allowed_paths:
                raise PermissionDenied('Set a new password before using the application.')
            return user, token
        return result
