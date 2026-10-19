from datetime import date, timedelta
from unittest.mock import patch

from django.db import IntegrityError
from django.test import TestCase
from rest_framework.test import APIClient

from apps.users.models import User
from apps.vendors.models import MarketSection, Stall, Vendor
from .models import Penalty, Violation


class ViolationEvidenceAuthorizationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user('synthetic_admin', password='Admin-pass-123!', role='admin')
        self.customer = User.objects.create_user('synthetic_customer', password='Customer-pass-123!', role='customer')
        self.owner_user = User.objects.create_user('synthetic_owner', password='Owner-pass-123!', role='vendor')
        self.other_vendor_user = User.objects.create_user('synthetic_other', password='Other-pass-123!', role='vendor')
        section = MarketSection.objects.create(code='ZX', name='Synthetic Section')
        owner_stall = Stall.objects.create(stall_number='ZX-01', section=section, category='Synthetic')
        other_stall = Stall.objects.create(stall_number='ZX-02', section=section, category='Synthetic')
        self.owner = Vendor.objects.create(
            user=self.owner_user, stall=owner_stall, first_name='Synthetic', last_name='Owner'
        )
        self.other_vendor = Vendor.objects.create(
            user=self.other_vendor_user, stall=other_stall, first_name='Synthetic', last_name='Other'
        )
        self.violation = Violation.objects.create(
            vendor=self.owner,
            issued_by=self.admin,
            violation_date=date.today(),
            violation_type='Synthetic evidence test',
            description='Synthetic record only.',
            photo='data:image/png;base64,SYNTHETIC_PRIVATE_EVIDENCE',
        )
        self.penalty = Penalty.objects.create(
            violation=self.violation,
            amount='1.00',
            due_date=date.today() + timedelta(days=1),
        )

    def test_unrelated_customer_cannot_list_or_retrieve_violation_evidence(self):
        self.client.force_authenticate(self.customer)

        listing = self.client.get('/api/v1/violations/')
        detail = self.client.get(f'/api/v1/violations/{self.violation.pk}/')

        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.data['count'], 0)
        self.assertEqual(detail.status_code, 404)

    def test_unrelated_vendor_cannot_retrieve_another_vendors_violation_evidence(self):
        self.client.force_authenticate(self.other_vendor_user)

        listing = self.client.get('/api/v1/violations/')
        detail = self.client.get(f'/api/v1/violations/{self.violation.pk}/')

        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.data['count'], 0)
        self.assertEqual(detail.status_code, 404)

    def test_violation_owner_and_administrator_retain_access(self):
        for user in (self.owner_user, self.admin):
            with self.subTest(role=user.role):
                self.client.force_authenticate(user)
                response = self.client.get(f'/api/v1/violations/{self.violation.pk}/')
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.data['photo'], 'data:image/png;base64,SYNTHETIC_PRIVATE_EVIDENCE')

    def test_customers_and_unrelated_vendors_cannot_list_or_retrieve_penalties(self):
        for user in (self.customer, self.other_vendor_user):
            with self.subTest(role=user.role):
                self.client.force_authenticate(user)
                listing = self.client.get('/api/v1/penalties/')
                detail = self.client.get(f'/api/v1/penalties/{self.penalty.pk}/')
                self.assertEqual(listing.status_code, 200)
                self.assertEqual(listing.data['count'], 0)
                self.assertEqual(detail.status_code, 404)


class ViolationCreateErrorSecurityTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user('violation_error_admin', password='Admin-pass-123!', role='admin')
        self.vendor_user = User.objects.create_user('violation_error_vendor', password='Vendor-pass-123!', role='vendor')
        section = MarketSection.objects.create(code='ER', name='Error Test Section')
        stall = Stall.objects.create(stall_number='ER-01', section=section, category='Synthetic')
        self.vendor = Vendor.objects.create(user=self.vendor_user, stall=stall, first_name='Synthetic', last_name='Vendor')
        self.client.force_authenticate(self.admin)

    def _payload(self, description='Synthetic violation description.'):
        return {
            'vendor': self.vendor.pk,
            'violation_date': date.today().isoformat(),
            'violation_type': 'Synthetic violation',
            'description': description,
            'severity': 'medium',
        }

    def test_unexpected_create_failure_is_sanitized_and_transaction_rolls_back(self):
        secret_marker = 'SENSITIVE_SYNTHETIC_REQUEST_MARKER'
        with patch(
            'apps.notifications.models.Notification.objects.create',
            side_effect=IntegrityError(f'forced failure containing {secret_marker}'),
        ):
            with self.assertLogs('apps.violations.views', level='ERROR') as captured:
                response = self.client.post('/api/v1/violations/', self._payload(secret_marker), format='json')

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.data, {'detail': 'Unable to create violation at this time.'})
        self.assertNotIn(secret_marker, response.content.decode())
        self.assertNotIn(secret_marker, '\n'.join(captured.output))
        self.assertNotIn('Traceback', '\n'.join(captured.output))
        self.assertEqual(Violation.objects.count(), 0)

    def test_serializer_validation_errors_remain_client_errors(self):
        response = self.client.post('/api/v1/violations/', {'vendor': self.vendor.pk}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertNotIn('traceback', response.data)
