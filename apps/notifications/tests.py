from django.test import TestCase
from rest_framework.test import APIClient

from apps.users.models import User
from .models import Notification


class NotificationAuthorizationTests(TestCase):
    url = '/api/v1/notifications/'

    def setUp(self):
        self.client = APIClient()
        self.customer = User.objects.create_user('notification_customer', password='Test-pass-123!', role='customer')
        self.vendor = User.objects.create_user('notification_vendor', password='Test-pass-123!', role='vendor')
        self.admin = User.objects.create_user('notification_admin', password='Test-pass-123!', role='admin')
        self.vendor_notice = Notification.objects.create(
            recipient=self.vendor,
            notification_type=Notification.TYPE_INFO,
            title='Vendor notice',
            message='Synthetic notice.',
            link='/vendor/documents',
        )
        self.customer_notice = Notification.objects.create(
            recipient=self.customer,
            notification_type=Notification.TYPE_INFO,
            title='Customer notice',
            message='Synthetic notice.',
            link='/complaints',
        )

    def test_customer_cannot_forge_notification_for_vendor_or_admin(self):
        self.client.force_authenticate(self.customer)
        for recipient in (self.vendor, self.admin):
            with self.subTest(recipient=recipient.role):
                response = self.client.post(self.url, {
                    'recipient': recipient.pk,
                    'notification_type': Notification.TYPE_WARNING,
                    'title': 'Forged',
                    'message': 'Forged message',
                    'link': '/admin',
                }, format='json')
                self.assertEqual(response.status_code, 403)
        self.assertEqual(Notification.objects.count(), 2)

    def test_ordinary_users_cannot_reassign_or_edit_notifications(self):
        self.client.force_authenticate(self.customer)
        payload = {
            'recipient': self.vendor.pk,
            'notification_type': Notification.TYPE_ERROR,
            'title': 'Changed title',
            'message': 'Changed message',
            'link': '/vendor/violations',
        }
        for method in ('put', 'patch', 'delete'):
            with self.subTest(method=method):
                response = getattr(self.client, method)(
                    f'{self.url}{self.customer_notice.pk}/', payload, format='json'
                )
                self.assertEqual(response.status_code, 403)
        self.customer_notice.refresh_from_db()
        self.assertEqual(self.customer_notice.recipient_id, self.customer.pk)
        self.assertEqual(self.customer_notice.title, 'Customer notice')

    def test_user_can_only_list_and_mark_own_notifications_read(self):
        self.client.force_authenticate(self.customer)
        listing = self.client.get(self.url)
        self.assertEqual(listing.status_code, 200)
        self.assertEqual({row['id'] for row in listing.data['results']}, {self.customer_notice.pk})
        self.assertEqual(self.client.post(f'{self.url}{self.vendor_notice.pk}/mark-read/').status_code, 404)
        self.assertEqual(self.client.post(f'{self.url}mark-all-read/').status_code, 200)
        self.vendor_notice.refresh_from_db()
        self.customer_notice.refresh_from_db()
        self.assertFalse(self.vendor_notice.is_read)
        self.assertTrue(self.customer_notice.is_read)

    def test_admin_can_create_for_another_user_using_internal_route(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(self.url, {
            'recipient': self.vendor.pk,
            'notification_type': Notification.TYPE_WARNING,
            'title': 'Admin notice',
            'message': 'Synthetic admin workflow.',
            'link': '/vendor/violations',
        }, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        notice = Notification.objects.get(pk=response.data['id'])
        self.assertEqual(notice.recipient_id, self.vendor.pk)

    def test_external_and_protocol_relative_links_are_rejected(self):
        self.client.force_authenticate(self.admin)
        for link in ('https://attacker.example/path', '//attacker.example/path', '/%2f%2fattacker.example'):
            with self.subTest(link=link):
                response = self.client.post(self.url, {
                    'recipient': self.vendor.pk,
                    'notification_type': Notification.TYPE_INFO,
                    'title': 'Unsafe link',
                    'message': 'Synthetic notice.',
                    'link': link,
                }, format='json')
                self.assertEqual(response.status_code, 400)
        self.assertEqual(Notification.objects.count(), 2)
