"""Safe defaults for the maintained Django test suite.

Tests must never inherit the developer's live document-storage credentials or
write test uploads into the working tree's private storage directory.
Cloudinary-specific tests can opt in to dummy settings and mock the SDK calls.
"""

import os
import secrets
from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.test.runner import DiscoverRunner
from django.test.utils import override_settings


class IsolatedStorageDiscoverRunner(DiscoverRunner):
    def run_tests(self, test_labels, **kwargs):
        from apps.documents.storage import (
            private_complaint_evidence_storage,
            private_document_storage,
        )

        storage_instances = (private_document_storage, private_complaint_evidence_storage)
        previous_locations = [
            (storage, storage._location, storage.__dict__.get('location'))
            for storage in storage_instances
        ]
        test_env = {
            'SECRET_KEY': secrets.token_urlsafe(48),
            'ALLOWED_HOSTS': 'api.synthetic.test',
            'CORS_ALLOWED_ORIGINS': 'https://web.synthetic.test',
            'CLOUDINARY_URL': '',
            'CLOUDINARY_CLOUD_NAME': '',
            'CLOUDINARY_API_KEY': '',
            'CLOUDINARY_API_SECRET': '',
            'SEMAPHORE_API_KEY': '',
        }

        with TemporaryDirectory(prefix='epalengke-tests-') as temp_root:
            root = Path(temp_root)
            private_root = root / 'private_documents'
            private_root.mkdir()
            for storage in storage_instances:
                storage._location = private_root
                storage.__dict__.pop('location', None)

            isolated_settings = {
                'DOCUMENT_STORAGE_BACKEND': 'local',
                'SEMAPHORE_API_KEY': '',
                'CLOUDINARY_STORAGE': {
                    'CLOUD_NAME': '',
                    'API_KEY': '',
                    'API_SECRET': '',
                },
                'STORAGES': {
                    'default': {
                        'BACKEND': 'django.core.files.storage.FileSystemStorage',
                        'OPTIONS': {'location': str(root / 'media')},
                    },
                    'staticfiles': {
                        'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
                    },
                },
                'MEDIA_ROOT': root / 'media',
                'PRIVATE_DOCUMENT_ROOT': private_root,
            }
            try:
                with ExitStack() as stack:
                    for target in (
                        'apps.documents.storage.cloudinary_uploader.upload',
                        'apps.documents.storage.cloudinary_uploader.destroy',
                        'apps.documents.storage.cloudinary_api.resource',
                        'apps.documents.storage.requests.get',
                    ):
                        stack.enter_context(
                            patch(target, side_effect=AssertionError('Cloudinary network operations are disabled in the test suite.'))
                        )
                    stack.enter_context(patch.dict(os.environ, test_env))
                    stack.enter_context(override_settings(**isolated_settings))
                    if not test_labels:
                        # Django's default root discovery also imports standalone
                        # test_*.py experiments, some of which perform HTTP calls
                        # at import time. The maintained suite is the tests.py
                        # module in each Django app/settings package.
                        project_root = Path(__file__).resolve().parent.parent
                        test_labels = sorted(
                            path.relative_to(project_root).with_suffix('').as_posix().replace('/', '.')
                            for package in (project_root / 'apps', project_root / 'core')
                            for path in package.rglob('tests.py')
                        )
                    return super().run_tests(test_labels, **kwargs)
            finally:
                for storage, old_location, cached_location in previous_locations:
                    storage._location = old_location
                    if cached_location is None:
                        storage.__dict__.pop('location', None)
                    else:
                        storage.__dict__['location'] = cached_location
