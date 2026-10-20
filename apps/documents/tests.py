from pathlib import Path
import time
from django.test import TestCase, override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.conf import settings
from unittest.mock import Mock, patch
import requests
from rest_framework import status
from rest_framework.test import APIClient

from apps.documents.models import Document, DocumentPage
from apps.users.models import User
from apps.vendors.models import Vendor
from apps.documents.storage import private_document_storage


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
        self.assertIn('file_url', documents[0])
        self.assertNotIn('file', documents[0])
        self.assertNotIn('/media/', documents[0]['file_url'])
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


class DocumentWorkflowTests(TestCase):
    url = '/api/v1/documents/'

    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(username='workflow_admin', password='Admin-pass-123!', role='admin')
        self.vendor_user = User.objects.create_user(username='workflow_vendor', password='Vendor-pass-123!', role='vendor')
        self.other_user = User.objects.create_user(username='workflow_other', password='Other-pass-123!', role='vendor')
        self.customer = User.objects.create_user(username='workflow_customer', password='Customer-pass-123!', role='customer')
        self.vendor = Vendor.objects.create(user=self.vendor_user, first_name='Workflow', last_name='Vendor')
        self.other_vendor = Vendor.objects.create(user=self.other_user, first_name='Other', last_name='Vendor')

    def tearDown(self):
        for document in Document.objects.all():
            for field in [document.file, *(page.file for page in document.pages.all())]:
                if field and field.name.startswith(('documents/phase3b_', 'documents/pages/phase3b_')):
                    private_document_storage.delete(field.name)

    def _pdf(self, name='phase3b_document.pdf'):
        return SimpleUploadedFile(name, b'%PDF-1.4\nmanual review test\n%%EOF', content_type='application/pdf')

    def _upload(self, filename='phase3b_permit.pdf', **extra):
        self.client.force_authenticate(self.vendor_user)
        data = {'document_type': Document.TYPE_BUSINESS_PERMIT, 'title': 'Pilot permit', 'file': self._pdf(filename), **extra}
        return self.client.post(self.url, data, format='multipart')

    @override_settings(DOCUMENT_PROCESSING_MODE='manual', GEMINI_API_KEY='')
    def test_upload_is_pending_without_running_ocr_and_file_is_private(self):
        with patch('apps.documents.views.run_task_async') as run_ocr:
            response = self._upload()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)
        self.assertEqual(response.data['status'], Document.STATUS_PENDING)
        self.assertEqual(response.data['ocr_status'], 'skipped')
        self.assertEqual(response.data['vendor'], self.vendor.pk)
        self.assertIn('/api/v1/documents/', response.data['file_url'])
        self.assertNotIn('/media/', response.data['file_url'])
        self.assertNotIn('temp', response.content.decode().lower())
        run_ocr.assert_not_called()
        document = Document.objects.get(pk=response.data['id'])
        self.assertTrue(document.file.storage.path(document.file.name).startswith(str(document.file.storage.location)))
        self.assertFalse(document.file.storage.path(document.file.name).startswith(str(settings.MEDIA_ROOT)))
        self.assertNotIn('file', response.data)

    def test_unsupported_and_mismatched_files_are_rejected(self):
        self.client.force_authenticate(self.vendor_user)
        unsupported = self.client.post(self.url, {
            'document_type': Document.TYPE_BUSINESS_PERMIT, 'title': 'Unsupported',
            'file': SimpleUploadedFile('phase3b_document.svg', b'<svg/>', content_type='image/svg+xml'),
        }, format='multipart')
        mismatch = self.client.post(self.url, {
            'document_type': Document.TYPE_BUSINESS_PERMIT, 'title': 'Mismatch',
            'file': SimpleUploadedFile('phase3b_document.pdf', b'not a pdf', content_type='application/pdf'),
        }, format='multipart')
        self.assertEqual(unsupported.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(mismatch.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Document.objects.count(), 0)

    @override_settings(DOCUMENT_MAX_UPLOAD_BYTES=16)
    def test_file_size_limit_is_enforced(self):
        response = self._upload()
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Document.objects.count(), 0)

    def test_contract_pages_submit_for_manual_review_without_ocr(self):
        self.client.force_authenticate(self.vendor_user)
        create = self.client.post(self.url, {'document_type': Document.TYPE_CONTRACT, 'title': 'Pilot contract'}, format='multipart')
        self.assertEqual(create.status_code, status.HTTP_201_CREATED, create.content)
        doc_id = create.data['id']
        for index in range(1, 4):
            page = self.client.post(f'{self.url}{doc_id}/add-page/', {
                'page': self._pdf(f'phase3b_contract_{index}.pdf')
            }, format='multipart')
            self.assertEqual(page.status_code, status.HTTP_200_OK, page.content)
        detail = self.client.get(f'{self.url}{doc_id}/')
        page_url = detail.data['pages'][0]['file_url']
        self.assertNotIn('/media/', page_url)
        self.assertEqual(self.client.get(page_url).status_code, status.HTTP_200_OK)
        self.client.force_authenticate(self.other_user)
        self.assertEqual(self.client.get(page_url).status_code, status.HTTP_404_NOT_FOUND)
        self.client.force_authenticate(self.vendor_user)
        with patch('apps.documents.views.run_task_async') as run_ocr:
            submitted = self.client.post(f'{self.url}{doc_id}/submit-contract/', {}, format='json')
        self.assertEqual(submitted.data['status'], Document.STATUS_PENDING)
        run_ocr.assert_not_called()

    def test_vendor_ownership_anonymous_and_admin_preview_access(self):
        created = self._upload()
        file_url = created.data['file_url']
        self.client.force_authenticate(self.other_user)
        self.assertEqual(self.client.get(file_url).status_code, status.HTTP_404_NOT_FOUND)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(file_url).status_code, status.HTTP_401_UNAUTHORIZED)
        self.client.force_authenticate(self.admin)
        preview = self.client.get(file_url)
        self.assertEqual(preview.status_code, status.HTTP_200_OK)
        self.assertEqual(preview['Content-Type'], 'application/pdf')
        self.assertEqual(preview['Cache-Control'], 'private, no-store')
        self.assertIn(b'%PDF-1.4', b''.join(preview.streaming_content))
        self.assertEqual(self.client.get('/media/documents/phase3b_document.pdf').status_code, status.HTTP_404_NOT_FOUND)

    def test_admin_review_actions_store_history_and_vendor_sees_feedback(self):
        document = self._upload().data
        self.client.force_authenticate(self.admin)
        rejected = self.client.post(f"{self.url}{document['id']}/request_resubmission/", {'review_notes': 'Please upload a clearer scan.'}, format='json')
        self.assertEqual(rejected.status_code, status.HTTP_200_OK)
        self.assertEqual(len(rejected.data['review_history']), 1)
        self.assertEqual(rejected.data['review_history'][0]['notes'], 'Please upload a clearer scan.')
        self.client.force_authenticate(self.vendor_user)
        own_doc = self.client.get(f"{self.url}{document['id']}/")
        self.assertEqual(own_doc.data['status'], Document.STATUS_RESUBMISSION)
        self.assertEqual(own_doc.data['review_notes'], 'Please upload a clearer scan.')
        rejected_document = self._upload('phase3b_rejected.pdf').data
        self.client.force_authenticate(self.admin)
        rejected = self.client.post(f"{self.url}{rejected_document['id']}/reject/", {'review_notes': 'Document is unreadable.'}, format='json')
        self.assertEqual(rejected.data['status'], Document.STATUS_REJECTED)
        self.assertEqual(rejected.data['review_notes'], 'Document is unreadable.')
        approved_document = self._upload('phase3b_approved.pdf').data
        self.client.force_authenticate(self.admin)
        approved = self.client.post(f"{self.url}{approved_document['id']}/approve/", {'review_notes': 'Accepted'}, format='json')
        self.assertEqual(approved.data['status'], Document.STATUS_APPROVED)
        self.assertEqual(len(approved.data['review_history']), 1)

    def test_non_admin_cannot_review_and_vendor_cannot_edit_status(self):
        document = self._upload().data
        self.client.force_authenticate(self.vendor_user)
        for action, payload in (
            ('approve', {}),
            ('reject', {'review_notes': 'Vendor must not review this document.'}),
            ('request_resubmission', {'review_notes': 'Vendor must not request resubmission.'}),
        ):
            with self.subTest(action=action):
                response = self.client.post(
                    f"{self.url}{document['id']}/{action}/", payload, format='json',
                )
                self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.patch(f"{self.url}{document['id']}/", {'status': 'approved'}, format='json').status_code, status.HTTP_403_FORBIDDEN)
        persisted = Document.objects.get(pk=document['id'])
        self.assertEqual(persisted.status, Document.STATUS_PENDING)
        self.assertIsNone(persisted.reviewed_by)
        self.assertEqual(persisted.review_history.count(), 0)
        self.client.force_authenticate(self.customer)
        self.assertEqual(self.client.post(self.url, {'document_type': Document.TYPE_BUSINESS_PERMIT, 'title': 'forbidden'}, format='multipart').status_code, status.HTTP_403_FORBIDDEN)

    def test_vendor_cannot_link_reupload_to_another_vendors_document(self):
        other_document = Document.objects.create(vendor=self.other_vendor, document_type=Document.TYPE_BUSINESS_PERMIT, title='Other permit')
        response = self._upload('phase3b_cross_vendor.pdf', replaces=other_document.pk)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Document.objects.count(), 1)

    def test_setup_required_vendor_cannot_access_document_api_or_refresh_session(self):
        self.vendor_user.must_change_password = True
        self.vendor_user.save(update_fields=['must_change_password'])
        login = self.client.post('/api/v1/auth/login/', {
            'username': self.vendor_user.username, 'password': 'Vendor-pass-123!',
        }, format='json')
        self.assertEqual(login.status_code, status.HTTP_200_OK)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        self.assertEqual(self.client.get(self.url).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.post('/api/v1/auth/refresh/', {'refresh': login.data['refresh']}, format='json').status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_rolls_back_document_and_files_on_page_failure(self):
        self.client.force_authenticate(self.vendor_user)
        with patch('apps.documents.views.DocumentPage.objects.create', side_effect=RuntimeError('forced page failure')):
            with self.assertRaises(RuntimeError):
                self.client.post(self.url, {
                    'document_type': Document.TYPE_BUSINESS_PERMIT,
                    'title': 'Rollback permit',
                    'file': self._pdf('phase3b_rollback.pdf'),
                }, format='multipart')
        self.assertEqual(Document.objects.count(), 0)
        directories, names = private_document_storage.listdir('documents')
        self.assertFalse(any(name.startswith('phase3b_rollback') for name in names))


@override_settings(
    DOCUMENT_STORAGE_BACKEND='cloudinary',
    CLOUDINARY_STORAGE={
        'CLOUD_NAME': 'pilot-test-cloud',
        'API_KEY': 'test-api-key-only',
        'API_SECRET': 'test-api-secret-only',
    },
)
class CloudinaryDocumentStorageTests(TestCase):
    url = '/api/v1/documents/'

    def setUp(self):
        self.client = APIClient()
        self.vendor_user = User.objects.create_user(username='cloud_vendor', password='Vendor-pass-123!', role='vendor')
        self.other_user = User.objects.create_user(username='cloud_other', password='Other-pass-123!', role='vendor')
        self.admin = User.objects.create_user(username='cloud_admin', password='Admin-pass-123!', role='admin')
        self.vendor = Vendor.objects.create(user=self.vendor_user, first_name='Cloud', last_name='Vendor')
        self.other_vendor = Vendor.objects.create(user=self.other_user, first_name='Other', last_name='Vendor')
        self.client.force_authenticate(self.vendor_user)

    def tearDown(self):
        for document in Document.objects.all():
            fields = [document.file, *(page.file for page in document.pages.all())]
            for field in fields:
                if field and field.name and not field.name.startswith('cloudinary/'):
                    private_document_storage.delete(field.name)

    @staticmethod
    def _pdf(name='phase3c_document.pdf'):
        return SimpleUploadedFile(name, b'%PDF-1.4\ncloud storage test\n%%EOF', content_type='application/pdf')

    @staticmethod
    def _image(name, content_type):
        image_bytes = {
            'jpg': b'\xff\xd8\xff\xe0' + b'phase3c-image-test' + b'\xff\xd9',
            'png': b'\x89PNG\r\n\x1a\n' + b'phase3c-image-test',
        }[name.rsplit('.', 1)[-1].lower()]
        return SimpleUploadedFile(name, image_bytes, content_type=content_type)

    @staticmethod
    def _successful_upload(file_obj, **options):
        return {
            'public_id': options['public_id'],
            'type': options['type'],
            'resource_type': options['resource_type'],
            'format': Path(file_obj.name).suffix.lstrip('.'),
        }

    def _post_document(self, file_obj):
        return self.client.post(self.url, {
            'document_type': Document.TYPE_BUSINESS_PERMIT,
            'title': 'Cloud-backed permit',
            'file': file_obj,
        }, format='multipart')

    @patch('apps.documents.storage.cloudinary_uploader.upload')
    def test_private_cloudinary_upload_uses_authenticated_delivery_for_supported_formats(self, upload):
        upload.side_effect = self._successful_upload
        for file_obj in [
            self._pdf('phase3c_permit.pdf'),
            self._image('phase3c_permit.jpg', 'image/jpeg'),
            self._image('phase3c_permit.png', 'image/png'),
        ]:
            response = self._post_document(file_obj)
            self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)
            document = Document.objects.get(pk=response.data['id'])
            self.assertTrue(document.file.name.startswith('cloudinary/epalengke_documents/'))
            self.assertTrue(document.file.name.endswith(Path(file_obj.name).suffix.lower()))
            self.assertEqual(response.data['status'], Document.STATUS_PENDING)
            self.assertIn('/api/v1/documents/', response.data['file_url'])
            self.assertNotIn('cloudinary', response.data['file_url'])
            self.assertNotIn('secure_url', response.data)
            self.assertNotIn('test-api-secret-only', response.content.decode())
            self.assertNotIn('test-api-key-only', response.content.decode())
        self.assertEqual(upload.call_count, 3)
        for call in upload.call_args_list:
            self.assertEqual(call.kwargs['resource_type'], 'image')
            self.assertEqual(call.kwargs['type'], 'authenticated')
            self.assertFalse(call.kwargs['overwrite'])
            self.assertTrue(call.kwargs['api_secret'])
        self.assertEqual(len({call.kwargs['public_id'] for call in upload.call_args_list}), 3)

    @patch('apps.documents.storage.cloudinary_uploader.upload')
    def test_local_and_cloudinary_documents_coexist(self, upload):
        upload.side_effect = self._successful_upload
        with self.settings(DOCUMENT_STORAGE_BACKEND='local'):
            local_response = self._post_document(self._pdf('phase3c_local.pdf'))
        cloud_response = self._post_document(self._pdf('phase3c_cloud.pdf'))
        local_document = Document.objects.get(pk=local_response.data['id'])
        cloud_document = Document.objects.get(pk=cloud_response.data['id'])
        self.assertFalse(local_document.file.name.startswith('cloudinary/'))
        self.assertTrue(local_document.file.storage.path(local_document.file.name).startswith(str(local_document.file.storage.location)))
        self.assertTrue(cloud_document.file.name.startswith('cloudinary/'))
        self.assertEqual(upload.call_count, 1)

    @patch('apps.documents.storage.cloudinary_uploader.upload')
    def test_contract_pages_upload_as_private_assets_and_submit(self, upload):
        upload.side_effect = self._successful_upload
        draft = self.client.post(self.url, {'document_type': Document.TYPE_CONTRACT, 'title': 'Pilot contract'}, format='multipart')
        self.assertEqual(draft.status_code, status.HTTP_201_CREATED, draft.content)
        document_id = draft.data['id']
        for index in range(1, 4):
            page_response = self.client.post(f'{self.url}{document_id}/add-page/', {
                'page': self._pdf(f'phase3c_contract_{index}.pdf'),
            }, format='multipart')
            self.assertEqual(page_response.status_code, status.HTTP_200_OK, page_response.content)
        document = Document.objects.get(pk=document_id)
        self.assertEqual(document.pages.count(), 3)
        self.assertTrue(all(page.file.name.startswith('cloudinary/') for page in document.pages.all()))
        submitted = self.client.post(f'{self.url}{document_id}/submit-contract/', {}, format='json')
        self.assertEqual(submitted.data['status'], Document.STATUS_PENDING)
        self.assertEqual(upload.call_count, 3)

    @patch('apps.documents.storage.cloudinary_uploader.upload')
    def test_missing_credentials_fail_closed_without_local_fallback(self, upload):
        with self.settings(CLOUDINARY_STORAGE={'CLOUD_NAME': '', 'API_KEY': '', 'API_SECRET': ''}):
            response = self._post_document(self._pdf('phase3c_no_credentials.pdf'))
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(Document.objects.count(), 0)
        upload.assert_not_called()

    @patch('apps.documents.storage.cloudinary_uploader.destroy')
    @patch('apps.documents.storage.cloudinary_uploader.upload', side_effect=TimeoutError('simulated network timeout'))
    def test_cloudinary_upload_failure_fails_closed_and_attempts_orphan_cleanup(self, upload, destroy):
        response = self._post_document(self._pdf('phase3c_upload_failure.pdf'))
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(Document.objects.count(), 0)
        upload.assert_called_once()
        destroy.assert_called_once()
        self.assertEqual(destroy.call_args.kwargs['type'], 'authenticated')
        self.assertFalse(list(Path(private_document_storage.location).rglob('phase3c_upload_failure.pdf')))

    @patch('apps.documents.storage.requests.get')
    @patch('apps.documents.storage.cloudinary_utils.private_download_url')
    @patch('apps.documents.storage.cloudinary_uploader.upload')
    def test_private_delivery_is_signed_only_after_authorization(self, upload, signed_url, remote_get):
        upload.side_effect = self._successful_upload
        signed_url.return_value = 'https://api.cloudinary.test/short-lived-signed-download'
        remote = Mock()
        remote.status_code = 200
        remote.content = b'%PDF-1.4\nprivate cloud document\n%%EOF'
        remote.headers = {'content-type': 'application/pdf'}
        remote.raise_for_status.return_value = None
        remote_get.return_value = remote

        created = self._post_document(self._pdf('phase3c_private.pdf'))
        private_document = Document.objects.get(pk=created.data['id'])
        file_url = created.data['file_url']

        owner_response = self.client.get(file_url)
        self.assertEqual(owner_response.status_code, status.HTTP_200_OK)
        self.assertIn(b'private cloud document', b''.join(owner_response.streaming_content))
        self.assertEqual(signed_url.call_count, 1)

        self.client.force_authenticate(self.other_user)
        self.assertEqual(self.client.get(file_url).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(signed_url.call_count, 1)

        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(file_url).status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(signed_url.call_count, 1)

        self.client.force_authenticate(self.admin)
        admin_response = self.client.get(file_url)
        self.assertEqual(admin_response.status_code, status.HTTP_200_OK)
        self.assertIn(b'private cloud document', b''.join(admin_response.streaming_content))
        self.assertEqual(admin_response['Cache-Control'], 'private, no-store')
        self.assertEqual(signed_url.call_count, 2)
        self.assertEqual(signed_url.call_args.args[0], private_document.file.name[len('cloudinary/'):].rsplit('.', 1)[0])
        self.assertEqual(signed_url.call_args.kwargs['type'], 'authenticated')
        self.assertLessEqual(signed_url.call_args.kwargs['expires_at'], int(time.time()) + 60)
        self.assertEqual(remote_get.call_args.args[0], signed_url.return_value)
        self.assertEqual(remote_get.call_count, 2)

    @patch('apps.documents.storage.cloudinary_uploader.destroy')
    @patch('apps.documents.storage.cloudinary_uploader.upload')
    def test_database_rollback_compensates_cloudinary_upload(self, upload, destroy):
        upload.side_effect = self._successful_upload
        with patch('apps.documents.views.DocumentPage.objects.create', side_effect=RuntimeError('simulated database insert failure')):
            with self.assertRaises(RuntimeError):
                self._post_document(self._pdf('phase3c_rollback.pdf'))
        self.assertEqual(Document.objects.count(), 0)
        destroy.assert_called_once()
        self.assertEqual(destroy.call_args.kwargs['type'], 'authenticated')

    @patch('apps.documents.storage.requests.get')
    @patch('apps.documents.storage.cloudinary_utils.private_download_url', return_value='https://api.cloudinary.test/missing')
    def test_missing_cloudinary_asset_returns_not_found(self, signed_url, remote_get):
        document = Document.objects.create(vendor=self.vendor, document_type=Document.TYPE_BUSINESS_PERMIT,
                                           title='Missing cloud asset', file='cloudinary/epalengke_documents/missing.pdf')
        remote = Mock()
        remote.status_code = 404
        remote_get.return_value = remote
        response = self.client.get(f'{self.url}{document.pk}/file/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        signed_url.assert_called_once()

    @patch('apps.documents.storage.requests.get', side_effect=requests.Timeout('simulated timeout'))
    @patch('apps.documents.storage.cloudinary_utils.private_download_url', return_value='https://api.cloudinary.test/timeout')
    def test_cloudinary_delivery_network_failure_returns_service_unavailable(self, signed_url, remote_get):
        document = Document.objects.create(vendor=self.vendor, document_type=Document.TYPE_BUSINESS_PERMIT,
                                           title='Slow cloud asset', file='cloudinary/epalengke_documents/slow.pdf')
        response = self.client.get(f'{self.url}{document.pk}/file/')
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
