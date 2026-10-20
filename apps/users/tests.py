from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.users.models import User


class LogoutTokenRevocationTests(TestCase):
    def test_logout_blacklists_refresh_token(self):
        user = User.objects.create_user(
            username='logout_vendor', password='Vendor-pass-123!', role='vendor',
        )
        refresh = RefreshToken.for_user(user)
        client = APIClient()

        logout = client.post(
            '/api/v1/auth/logout/', {'refresh': str(refresh)}, format='json',
        )
        self.assertEqual(logout.status_code, 200)

        refresh_response = client.post(
            '/api/v1/auth/refresh/', {'refresh': str(refresh)}, format='json',
        )
        self.assertEqual(refresh_response.status_code, 401)

    def test_logout_rejects_missing_or_invalid_refresh_tokens(self):
        client = APIClient()
        missing = client.post('/api/v1/auth/logout/', {}, format='json')
        invalid = client.post('/api/v1/auth/logout/', {'refresh': 'not-a-token'}, format='json')
        malformed = client.post('/api/v1/auth/logout/', {'refresh': []}, format='json')

        self.assertEqual(missing.status_code, 400)
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(malformed.status_code, 400)
