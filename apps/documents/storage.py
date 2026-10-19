import logging
from pathlib import Path
import time
from uuid import uuid4

import requests
from cloudinary import api as cloudinary_api
from cloudinary import uploader as cloudinary_uploader
from cloudinary import utils as cloudinary_utils
from django.conf import settings
from django.core.exceptions import SuspiciousFileOperation
from django.core.files.storage import FileSystemStorage
from django.core.files.base import ContentFile
from django.utils._os import safe_join
from django.utils.deconstruct import deconstructible

logger = logging.getLogger(__name__)
CLOUDINARY_PREFIX = 'cloudinary/'
CLOUDINARY_FOLDER = 'epalengke_documents'
CLOUDINARY_COMPLAINT_FOLDER = 'epalengke_complaints'
CLOUDINARY_RESOURCE_TYPE = 'image'


class DocumentStorageUnavailable(Exception):
    """The configured private document backend is unavailable."""


class CloudinaryDocumentStorage:
    """Private Cloudinary adapter for PDF, JPG, and PNG document assets."""

    @staticmethod
    def credentials():
        credentials = {
            'cloud_name': getattr(settings, 'CLOUDINARY_STORAGE', {}).get('CLOUD_NAME'),
            'api_key': getattr(settings, 'CLOUDINARY_STORAGE', {}).get('API_KEY'),
            'api_secret': getattr(settings, 'CLOUDINARY_STORAGE', {}).get('API_SECRET'),
        }
        if not all(credentials.values()):
            raise DocumentStorageUnavailable('Cloudinary document storage is not configured.')
        return credentials

    @staticmethod
    def public_id(storage_name):
        if not storage_name.startswith(CLOUDINARY_PREFIX):
            raise ValueError('Not a Cloudinary document key.')
        relative = storage_name[len(CLOUDINARY_PREFIX):]
        return str(Path(relative).with_suffix(''))

    @staticmethod
    def file_format(storage_name):
        return Path(storage_name).suffix.lstrip('.').lower()

    def upload(self, storage_name, content):
        credentials = self.credentials()
        public_id = self.public_id(storage_name)
        if hasattr(content, 'seek'):
            content.seek(0)
        try:
            result = cloudinary_uploader.upload(
                content,
                public_id=public_id,
                resource_type=CLOUDINARY_RESOURCE_TYPE,
                type='authenticated',
                overwrite=False,
                unique_filename=False,
                use_filename=False,
                timeout=20,
                **credentials,
            )
            if (result.get('public_id') != public_id
                    or result.get('type') != 'authenticated'
                    or result.get('resource_type') != CLOUDINARY_RESOURCE_TYPE):
                self._destroy(public_id, credentials, suppress=True)
                raise DocumentStorageUnavailable('Cloudinary did not confirm a private document upload.')
            return storage_name
        except DocumentStorageUnavailable:
            raise
        except Exception as exc:
            # A timeout can happen after Cloudinary accepted the file. Attempt a
            # compensating delete using the pre-generated, unique asset ID.
            self._destroy(public_id, credentials, suppress=True)
            raise DocumentStorageUnavailable('Cloudinary document upload failed.') from exc

    def open(self, storage_name):
        credentials = self.credentials()
        public_id = self.public_id(storage_name)
        file_format = self.file_format(storage_name)
        try:
            signed_url = cloudinary_utils.private_download_url(
                public_id,
                file_format,
                resource_type=CLOUDINARY_RESOURCE_TYPE,
                type='authenticated',
                expires_at=int(time.time()) + 60,
                secure=True,
                **credentials,
            )
            response = requests.get(signed_url, timeout=(5, 20), allow_redirects=True)
            if response.status_code == 404:
                raise FileNotFoundError(storage_name)
            response.raise_for_status()
            return ContentFile(response.content, name=Path(storage_name).name)
        except FileNotFoundError:
            raise
        except Exception as exc:
            raise DocumentStorageUnavailable('Cloudinary document delivery failed.') from exc

    def exists(self, storage_name):
        credentials = self.credentials()
        try:
            cloudinary_api.resource(
                self.public_id(storage_name),
                resource_type=CLOUDINARY_RESOURCE_TYPE,
                type='authenticated',
                **credentials,
            )
            return True
        except Exception as exc:
            if getattr(exc, 'http_code', None) == 404 or 'not found' in str(exc).lower():
                return False
            raise DocumentStorageUnavailable('Cloudinary document lookup failed.') from exc

    def delete(self, storage_name):
        credentials = self.credentials()
        self._destroy(self.public_id(storage_name), credentials, suppress=False)

    @staticmethod
    def _destroy(public_id, credentials, suppress):
        try:
            cloudinary_uploader.destroy(
                public_id,
                resource_type=CLOUDINARY_RESOURCE_TYPE,
                type='authenticated',
                invalidate=True,
                timeout=20,
                **credentials,
            )
        except Exception:
            # Do not log SDK exception strings: they may contain request details.
            logger.error('Cloudinary cleanup failed for asset %s.', public_id)
            if not suppress:
                raise DocumentStorageUnavailable('Cloudinary document cleanup failed.')

@deconstructible
class PrivateDocumentStorage(FileSystemStorage):
    """Store new documents outside MEDIA_ROOT and read legacy files in place."""

    def __init__(self, location=None, base_url=None, cloudinary_folder=CLOUDINARY_FOLDER):
        super().__init__(location=location or settings.PRIVATE_DOCUMENT_ROOT, base_url=base_url)
        self.cloudinary_folder = cloudinary_folder

    @staticmethod
    def _backend():
        backend = getattr(settings, 'DOCUMENT_STORAGE_BACKEND', 'local')
        if backend not in {'local', 'cloudinary'}:
            raise DocumentStorageUnavailable('Document storage backend configuration is invalid.')
        return backend

    def get_available_name(self, name, max_length=None):
        if self._backend() == 'cloudinary':
            suffix = Path(name).suffix.lower()
            return f'{CLOUDINARY_PREFIX}{self.cloudinary_folder}/{uuid4().hex}{suffix}'
        return super().get_available_name(name, max_length)

    def _save(self, name, content):
        if name.startswith(CLOUDINARY_PREFIX):
            return CloudinaryDocumentStorage().upload(name, content)
        return super()._save(name, content)

    def _open(self, name, mode="rb"):
        if name.startswith(CLOUDINARY_PREFIX):
            if mode != 'rb':
                raise ValueError('Cloudinary documents are read-only through storage.')
            return CloudinaryDocumentStorage().open(name)
        private_path = Path(self.path(name))
        if private_path.exists():
            return super()._open(name, mode)

        # Existing local documents remain where they are; they are never copied
        # as part of this migration. New writes always use PRIVATE_DOCUMENT_ROOT.
        legacy_path = self._legacy_path(name)
        if legacy_path and legacy_path.exists():
            return legacy_path.open(mode)
        raise FileNotFoundError(name)

    def exists(self, name):
        if name.startswith(CLOUDINARY_PREFIX):
            return CloudinaryDocumentStorage().exists(name)
        legacy_path = self._legacy_path(name)
        return super().exists(name) or bool(legacy_path and legacy_path.exists())

    def delete(self, name):
        if name.startswith(CLOUDINARY_PREFIX):
            return CloudinaryDocumentStorage().delete(name)
        return super().delete(name)

    def path(self, name):
        if name.startswith(CLOUDINARY_PREFIX):
            raise NotImplementedError('Cloudinary document assets do not have a local filesystem path.')
        return super().path(name)

    @staticmethod
    def _legacy_path(name):
        try:
            return Path(safe_join(settings.MEDIA_ROOT, name))
        except SuspiciousFileOperation:
            return None

    def url(self, name):
        raise ValueError("Private documents do not have public URLs.")


@deconstructible
class PrivateComplaintEvidenceStorage(PrivateDocumentStorage):
    """Use private Cloudinary storage for new evidence and keep legacy media readable."""

    def __init__(self, location=None, base_url=None):
        super().__init__(
            location=location,
            base_url=base_url,
            cloudinary_folder=CLOUDINARY_COMPLAINT_FOLDER,
        )

    def get_available_name(self, name, max_length=None):
        suffix = Path(name).suffix.lower()
        if self._backend() == 'cloudinary':
            return super().get_available_name(name, max_length=max_length)
        return f'complaints/{uuid4().hex}{suffix}'


private_document_storage = PrivateDocumentStorage()
private_complaint_evidence_storage = PrivateComplaintEvidenceStorage()
