from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.documents.models import Document, DocumentPage
from apps.users.models import User
from apps.vendors.models import Vendor


class DocumentAccessControlTests(TestCase):
    url = '/api/v1/documents/'

    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            username='document_admin', password='admin-pass', role='admin',
            first_name='Market', last_name='Admin',
        )
        self.owner_user = User.objects.create_user(
            username='document_owner', password='owner-pass', role='vendor',
        )
        self.other_user = User.objects.create_user(
            username='other_vendor', password='other-pass', role='vendor',
        )
        self.customer = User.objects.create_user(
            username='document_customer', password='customer-pass', role='customer',
        )
        self.owner = Vendor.objects.create(
            user=self.owner_user, first_name='Owner', last_name='Vendor',
        )
        self.other_vendor = Vendor.objects.create(
            user=self.other_user, first_name='Other', last_name='Vendor',
        )
        self.own_document = self._make_document(
            self.owner, 'owner-permit.pdf', 'OWNER OCR PRIVATE TEXT',
        )
        self.other_document = self._make_document(
            self.other_vendor, 'other-contract.pdf', 'OTHER VENDOR PRIVATE TEXT',
        )

    def _make_document(self, vendor, filename, ocr_text):
        document = Document.objects.create(
            vendor=vendor,
            uploaded_by=vendor.user,
            reviewed_by=self.admin,
            document_type=Document.TYPE_BUSINESS_PERMIT,
            title='Business permit',
            file=f'documents/{filename}',
            status=Document.STATUS_PENDING,
            raw_ocr_text=ocr_text,
            extracted_data={'registration_number': f'PRIVATE-{filename}'},
            validation_results={'result': 'private validation'},
            classification_metadata={'source': 'private classification'},
            review_notes=f'Private reviewer notes for {filename}',
        )
        DocumentPage.objects.create(
            document=document,
            file=f'documents/pages/{filename}',
            page_upload_order=1,
            raw_ocr_text=f'PAGE {ocr_text}',
        )
        return document

    def _authenticate(self, user):
        self.client.force_authenticate(user=user)

    def _assert_private_content_absent(self, response, document):
        content = response.content.decode()
        self.assertNotIn(document.file.name, content)
        self.assertNotIn(document.raw_ocr_text, content)
        self.assertNotIn(document.extracted_data['registration_number'], content)
        self.assertNotIn(document.review_notes, content)

    def test_anonymous_user_cannot_list_or_retrieve_documents(self):
        self.assertEqual(self.client.get(self.url).status_code, status.HTTP_401_UNAUTHORIZED)
        response = self.client.get(f'{self.url}{self.own_document.pk}/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self._assert_private_content_absent(response, self.own_document)

    def test_customer_list_is_empty_and_id_retrieval_is_hidden(self):
        self._authenticate(self.customer)

        list_response = self.client.get(self.url)
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(list_response.json()['results'], [])
        self._assert_private_content_absent(list_response, self.own_document)

        detail_response = self.client.get(f'{self.url}{self.own_document.pk}/')
        self.assertEqual(detail_response.status_code, status.HTTP_404_NOT_FOUND)
        self._assert_private_content_absent(detail_response, self.own_document)

    def test_vendor_can_read_own_document_and_sensitive_review_data(self):
        self._authenticate(self.owner_user)

        list_response = self.client.get(self.url)
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        documents = list_response.json()['results']
        self.assertEqual([item['id'] for item in documents], [self.own_document.pk])
        self.assertEqual(documents[0]['raw_ocr_text'], self.own_document.raw_ocr_text)
        self.assertEqual(documents[0]['review_notes'], self.own_document.review_notes)
        self.assertIn('file', documents[0])
        self.assertEqual(len(documents[0]['pages']), 1)

        detail_response = self.client.get(f'{self.url}{self.own_document.pk}/')
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.json()['extracted_data'], self.own_document.extracted_data)

    def test_vendor_cannot_list_or_retrieve_another_vendors_document_by_id(self):
        self._authenticate(self.owner_user)

        list_response = self.client.get(self.url)
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual([item['id'] for item in list_response.json()['results']], [self.own_document.pk])
        self._assert_private_content_absent(list_response, self.other_document)

        detail_response = self.client.get(f'{self.url}{self.other_document.pk}/')
        self.assertEqual(detail_response.status_code, status.HTTP_404_NOT_FOUND)
        self._assert_private_content_absent(detail_response, self.other_document)

    def test_admin_can_list_retrieve_and_review_all_documents(self):
        self._authenticate(self.admin)

        list_response = self.client.get(self.url)
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            {item['id'] for item in list_response.json()['results']},
            {self.own_document.pk, self.other_document.pk},
        )

        detail_response = self.client.get(f'{self.url}{self.other_document.pk}/')
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.json()['raw_ocr_text'], self.other_document.raw_ocr_text)
        self.assertEqual(detail_response.json()['extracted_data'], self.other_document.extracted_data)

        review_response = self.client.post(
            f'{self.url}{self.other_document.pk}/approve/',
            {'review_notes': 'Reviewed by administrator'},
            format='json',
        )
        self.assertEqual(review_response.status_code, status.HTTP_200_OK)
        self.other_document.refresh_from_db()
        self.assertEqual(self.other_document.status, Document.STATUS_APPROVED)
        self.assertEqual(self.other_document.reviewed_by, self.admin)

    def test_vendor_without_vendor_profile_sees_no_documents(self):
        unlinked_vendor = User.objects.create_user(
            username='unlinked_vendor', password='vendor-pass', role='vendor',
        )
        self._authenticate(unlinked_vendor)

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()['results'], [])
        detail_response = self.client.get(f'{self.url}{self.own_document.pk}/')
        self.assertEqual(detail_response.status_code, status.HTTP_404_NOT_FOUND)
