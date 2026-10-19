"""
Vendors/Stalls app — critical-path tests.

Covers:
- Stall list returns map coordinate fields (P2-01 fix verification)
- Customer role receives public (limited) vendor serializer (P2-02 fix verification)
- Admin role receives full vendor serializer
- Unauthenticated cannot access vendor list
"""

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from unittest.mock import patch
import logging

from apps.users.models import User
from apps.vendors.models import MarketSection, Stall, Vendor
from apps.vendors.serializers import StallPublicDetailSerializer, VendorPublicSerializer


def _create_section():
    return MarketSection.objects.create(code='T', name='Test Section')


def _create_stall(section, stall_number='T-01', map_x=100, map_y=200):
    return Stall.objects.create(
        stall_number=stall_number,
        section=section,
        category='Vegetables',
        status='owner',
        building='main',
        floor='1',
        map_x=map_x,
        map_y=map_y,
        map_width=50,
        map_height=30,
    )


class StallListSerializerFieldsTest(TestCase):
    """P2-01 — stall list must include map coordinate fields."""

    def setUp(self):
        self.client = APIClient()
        section = _create_section()
        _create_stall(section, 'T-01', map_x=300, map_y=450)

    def test_stall_list_includes_map_coords(self):
        """Map coordinate fields must be present in the list endpoint response."""
        response = self.client.get('/api/v1/stalls/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        results = data.get('results', data)
        self.assertGreater(len(results), 0)
        stall = results[0]
        # Serializer maps map_x→svg_x, map_y→svg_y for frontend compatibility
        self.assertIn('svg_x', stall, "svg_x missing from stall list response")
        self.assertIn('svg_y', stall, "svg_y missing from stall list response")
        self.assertIn('map_width', stall, "map_width missing from stall list response")
        self.assertIn('map_height', stall, "map_height missing from stall list response")
        # Values should match what was seeded (map_x=300 exposed as svg_x)
        self.assertEqual(stall['svg_x'], 300)
        self.assertEqual(stall['svg_y'], 450)

    def test_stall_list_includes_occupancy_status(self):
        response = self.client.get('/api/v1/stalls/')
        results = response.json().get('results', response.json())
        stall = results[0]
        self.assertIn('occupancy_status', stall)

    def test_anonymous_stall_list_includes_only_public_vendor_information(self):
        section = MarketSection.objects.get(code='T')
        stall = _create_stall(section, 'T-03')
        Vendor.objects.create(
            stall=stall,
            first_name='Public',
            last_name='Vendor',
            email='private@example.com',
            phone='private phone',
            address='private address',
            permit_number='private permit',
        )

        response = self.client.get('/api/v1/stalls/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.json().get('results', response.json())
        public_stall = next(item for item in results if item['stall_number'] == 'T-03')
        self.assertEqual(public_stall['vendor_name'], 'Public Vendor')
        for private_field in ('email', 'phone', 'address', 'permit_number', 'user_id'):
            self.assertNotIn(private_field, public_stall)


class VendorSerializerRoleTest(TestCase):
    """P2-02 — customer role receives limited vendor data; admin gets full data."""

    def setUp(self):
        self.client = APIClient()
        section = _create_section()
        stall = _create_stall(section, 'T-02')

        self.vendor = Vendor.objects.create(
            first_name='Juan',
            last_name='Dela Cruz',
            email='juan@example.com',
            phone='09171234567',
            address='123 Market St',
            permit_number='PMT-2024-001',
            stall=stall,
        )

        self.admin = User.objects.create_user(
            username='admin_v', password='adminv123', role='admin'
        )
        self.customer = User.objects.create_user(
            username='cust_v', password='custv123', role='customer'
        )

    def _login(self, username, password):
        resp = self.client.post('/api/v1/auth/login/', {
            'username': username, 'password': password
        }, format='json')
        self.assertEqual(resp.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.json()['access']}")

    def test_customer_does_not_see_private_vendor_fields(self):
        """P2-02 fix — customer must NOT receive email, phone, address, permit_number."""
        self._login('cust_v', 'custv123')
        response = self.client.get(f'/api/v1/vendors/{self.vendor.pk}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        # These fields must NOT be present for customer role
        for private_field in ['email', 'phone', 'address', 'permit_number',
                               'permit_expiry', 'health_cert_expiry', 'compliance_rate']:
            self.assertNotIn(private_field, data,
                             f"Private field '{private_field}' should not be exposed to customer role")

    def test_customer_sees_public_vendor_fields(self):
        self._login('cust_v', 'custv123')
        response = self.client.get(f'/api/v1/vendors/{self.vendor.pk}/')
        data = response.json()
        self.assertIn('full_name', data)
        self.assertIn('stall_number', data)
        self.assertIn('products_list', data)

    def test_admin_sees_full_vendor_fields(self):
        self._login('admin_v', 'adminv123')
        response = self.client.get(f'/api/v1/vendors/{self.vendor.pk}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn('email', data)
        self.assertIn('phone', data)
        self.assertIn('permit_number', data)

    def test_unauthenticated_cannot_access_vendor_list(self):
        self.client.credentials()
        response = self.client.get('/api/v1/vendors/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class StallDetailPrivacyTest(TestCase):
    """Public stall detail must use a strict public allowlist for non-admins."""

    def setUp(self):
        self.client = APIClient()
        section = _create_section()
        self.stall = _create_stall(section, 'T-DETAIL', map_x=321, map_y=654)
        self.owner_user = User.objects.create_user(
            username='stall_owner', password='ownerpass123', role='vendor',
            email='account@example.com',
        )
        self.vendor = Vendor.objects.create(
            user=self.owner_user,
            stall=self.stall,
            first_name='Private',
            last_name='Vendor',
            email='private.vendor@example.com',
            phone='09170000000',
            address='Private residential address',
            permit_number='PRIVATE-PERMIT-001',
            permit_expiry='2030-01-01',
            health_cert_expiry='2030-02-01',
            products='Produce',
        )
        self.customer = User.objects.create_user(
            username='stall_customer', password='customerpass123', role='customer',
        )
        self.other_vendor_user = User.objects.create_user(
            username='other_vendor', password='vendorpass123', role='vendor',
        )
        other_stall = _create_stall(section, 'T-OTHER')
        Vendor.objects.create(user=self.other_vendor_user, stall=other_stall)
        self.admin = User.objects.create_user(
            username='stall_admin', password='adminpass123', role='admin',
        )

    def _get_detail_as(self, user=None):
        self.client.force_authenticate(user=user)
        return self.client.get(f'/api/v1/stalls/{self.stall.pk}/')

    def _assert_public_detail(self, response):
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(set(data), set(StallPublicDetailSerializer.Meta.fields))
        self.assertEqual(data['stall_number'], 'T-DETAIL')
        self.assertEqual(data['svg_x'], 321)
        self.assertEqual(data['svg_y'], 654)
        self.assertEqual(data['vendor_name'], 'Private Vendor')
        self.assertEqual(set(data['vendor']), set(VendorPublicSerializer.Meta.fields))
        self.assertEqual(data['vendor']['products_list'], ['Produce'])
        for private_field in (
            'user_id', 'email', 'phone', 'address', 'permit_number',
            'permit_expiry', 'health_cert_expiry', 'compliance_rate',
        ):
            self.assertNotIn(private_field, data['vendor'])

    def test_anonymous_user_gets_allowlisted_public_stall_detail(self):
        self._assert_public_detail(self._get_detail_as())

    def test_customer_gets_allowlisted_public_stall_detail(self):
        self._assert_public_detail(self._get_detail_as(self.customer))

    def test_unrelated_vendor_gets_allowlisted_public_stall_detail(self):
        self._assert_public_detail(self._get_detail_as(self.other_vendor_user))

    def test_owning_vendor_cannot_get_private_fields_from_public_detail(self):
        self._assert_public_detail(self._get_detail_as(self.owner_user))

    def test_admin_retains_full_stall_and_vendor_detail(self):
        response = self._get_detail_as(self.admin)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn('created_at', data)
        self.assertEqual(data['vendor']['email'], 'private.vendor@example.com')
        self.assertEqual(data['vendor']['phone'], '09170000000')
        self.assertEqual(data['vendor']['address'], 'Private residential address')
        self.assertEqual(data['vendor']['permit_number'], 'PRIVATE-PERMIT-001')
        self.assertEqual(data['vendor']['user_id'], self.owner_user.pk)


class VendorOnboardingTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.section = _create_section()
        self.admin = User.objects.create_user(username='onboard_admin', password='admin-pass-123', role='admin')
        self.vendor = Vendor.objects.create(first_name='Mila', last_name='Reyes', email='', phone='09170000000')

    def test_vendor_creation_without_account_preserves_existing_flow(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post('/api/v1/vendors/', {
            'first_name': 'Ana', 'last_name': 'Santos', 'stall': _create_stall(self.section, 'T-NEW').pk,
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        vendor = Vendor.objects.get(pk=response.json()['id'])
        self.assertIsNone(vendor.user_id)
        self.assertEqual(response.json()['account_status'], 'no_account')
        self.assertNotIn('credentials', response.json())

    def test_create_vendor_with_account_returns_single_use_credentials_and_links_vendor_role(self):
        self.client.force_authenticate(self.admin)
        captured_logs = []
        class CaptureLogs(logging.Handler):
            def emit(self, record):
                captured_logs.append(self.format(record))
        handler = CaptureLogs()
        logging.getLogger().addHandler(handler)
        try:
            response = self.client.post('/api/v1/vendors/', {
                'first_name': 'Ana', 'last_name': 'Santos', 'stall': _create_stall(self.section, 'T-LOGIN').pk,
                'create_account': True,
            }, format='json')
        finally:
            logging.getLogger().removeHandler(handler)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        linked = Vendor.objects.get(pk=data['id']).user
        self.assertEqual(linked.role, User.ROLE_VENDOR)
        self.assertEqual(linked.vendor_profile.pk, data['id'])
        self.assertTrue(linked.must_change_password)
        self.assertTrue(linked.check_password(data['credentials']['temporary_password']))
        self.assertNotEqual(linked.password, data['credentials']['temporary_password'])
        self.assertEqual(data['account_status'], 'pending_setup')
        self.assertEqual(linked.email, '')
        detail = self.client.get(f"/api/v1/vendors/{data['id']}/")
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self.assertNotIn('credentials', detail.json())
        self.assertNotIn(data['credentials']['temporary_password'], str(detail.json()))
        self.assertNotIn(data['credentials']['temporary_password'], linked.password)
        listing = self.client.get('/api/v1/vendors/')
        self.assertNotIn(data['credentials']['temporary_password'], str(listing.json()))
        self.assertNotIn('credentials', listing.json()['results'][0])
        self.assertNotIn(data['credentials']['temporary_password'], '\n'.join(captured_logs))

    def test_existing_vendor_provisioning_and_duplicate_prevention(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(f'/api/v1/vendors/{self.vendor.pk}/create-account/', {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.vendor.refresh_from_db()
        self.assertEqual(self.vendor.user.role, User.ROLE_VENDOR)
        self.assertEqual(response.json()['vendor']['account_status'], 'pending_setup')
        duplicate = self.client.post(f'/api/v1/vendors/{self.vendor.pk}/create-account/', {}, format='json')
        self.assertEqual(duplicate.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unauthorized_user_cannot_create_vendor_account(self):
        customer = User.objects.create_user(username='onboard_customer', password='customer-pass-123', role='customer')
        self.client.force_authenticate(customer)
        response = self.client.post(f'/api/v1/vendors/{self.vendor.pk}/create-account/', {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.vendor.refresh_from_db()
        self.assertIsNone(self.vendor.user_id)

    def test_account_creation_rolls_back_vendor_and_user_on_link_failure(self):
        self.client.force_authenticate(self.admin)
        original_save = Vendor.save
        def fail_account_link(instance, *args, **kwargs):
            if instance.user_id:
                raise RuntimeError('simulated linking failure')
            return original_save(instance, *args, **kwargs)
        with patch.object(Vendor, 'save', fail_account_link):
            with self.assertRaises(RuntimeError):
                self.client.post('/api/v1/vendors/', {
                    'first_name': 'Rollback', 'last_name': 'Vendor', 'stall': _create_stall(self.section, 'T-ROLL').pk,
                    'create_account': True,
                }, format='json')
        self.assertFalse(Vendor.objects.filter(first_name='Rollback').exists())
        self.assertFalse(User.objects.filter(first_name='Rollback').exists())


class FirstLoginPasswordSetupTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='pending-vendor', password='Temp-Strong-995!x', role='vendor', must_change_password=True)
        self.section = _create_section()
        self.vendor = Vendor.objects.create(user=self.user, first_name='Pending', last_name='Vendor')

    def test_temporary_password_login_is_marked_and_normal_vendor_api_is_blocked(self):
        response = self.client.post('/api/v1/auth/login/', {'username': self.user.username, 'password': 'Temp-Strong-995!x'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.json()['must_change_password'])
        self.assertNotIn('Temp-Strong-995!x', str(response.json()))
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.json()['access']}")
        self.assertEqual(self.client.get('/api/v1/vendors/').status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.get('/api/v1/auth/me/').status_code, status.HTTP_200_OK)

    def test_password_setup_clears_gate_and_allows_vendor_api(self):
        response = self.client.post('/api/v1/auth/login/', {'username': self.user.username, 'password': 'Temp-Strong-995!x'}, format='json')
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.json()['access']}")
        changed = self.client.post('/api/v1/auth/setup-password/', {'new_password': 'Vendor-New-Secure-448!'}, format='json')
        self.assertEqual(changed.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertFalse(self.user.must_change_password)
        self.assertTrue(self.user.check_password('Vendor-New-Secure-448!'))
        self.assertEqual(self.client.get('/api/v1/vendors/').status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(self.client.post('/api/v1/auth/refresh/', {'refresh': response.json()['refresh']}, format='json').status_code, status.HTTP_401_UNAUTHORIZED)
        self.client.credentials()
        new_login = self.client.post('/api/v1/auth/login/', {'username': self.user.username, 'password': 'Vendor-New-Secure-448!'}, format='json')
        self.assertEqual(new_login.status_code, status.HTTP_200_OK)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {new_login.json()['access']}")
        self.assertEqual(self.client.get('/api/v1/vendors/').status_code, status.HTTP_200_OK)

    def test_refresh_token_does_not_bypass_setup_gate(self):
        response = self.client.post('/api/v1/auth/login/', {'username': self.user.username, 'password': 'Temp-Strong-995!x'}, format='json')
        refreshed = self.client.post('/api/v1/auth/refresh/', {'refresh': response.json()['refresh']}, format='json')
        self.assertEqual(refreshed.status_code, status.HTTP_401_UNAUTHORIZED)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.json()['access']}")
        self.assertEqual(self.client.get('/api/v1/vendors/').status_code, status.HTTP_403_FORBIDDEN)

    def test_existing_access_session_is_gated_when_setup_is_required(self):
        response = self.client.post('/api/v1/auth/login/', {'username': self.user.username, 'password': 'Temp-Strong-995!x'}, format='json')
        self.user.must_change_password = False
        self.user.save(update_fields=['must_change_password'])
        established = self.client.post('/api/v1/auth/login/', {'username': self.user.username, 'password': 'Temp-Strong-995!x'}, format='json')
        self.user.must_change_password = True
        self.user.save(update_fields=['must_change_password'])
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {established.json()['access']}")
        self.assertEqual(self.client.get('/api/v1/vendors/').status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
