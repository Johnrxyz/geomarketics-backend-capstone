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
