"""Focused validation tests for the production-safe pilot settings."""

from importlib import import_module
from io import BytesIO
import os
from types import SimpleNamespace
from unittest.mock import patch

from urllib3 import ProxyManager

from django.core.exceptions import ImproperlyConfigured
from django.conf import settings
from django.test import SimpleTestCase

from ._pilot_validation import (
    parse_allowed_hosts,
    parse_cors_origins,
    required_env,
    validate_secret_key,
)


class PilotSettingsValidationTests(SimpleTestCase):
    def test_required_environment_value_has_no_fallback(self):
        with self.assertRaisesMessage(ImproperlyConfigured, "SECRET_KEY must be set"):
            required_env("SECRET_KEY", {})

    def test_secret_requires_long_random_non_placeholder_value(self):
        key = "fS7mQ2vN9xR4kT8pL3zB6cH1wY5dG0jAqE2uM8iP4oV9nC6xZ7"
        self.assertEqual(validate_secret_key(key), key)

        for invalid in (
            "django-insecure-this-is-a-development-secret-key",
            "generate-a-strong-random-secret-key-here-for-production",
            "x" * 64,
            "short",
        ):
            with self.subTest(invalid=invalid[:18]), self.assertRaises(ImproperlyConfigured):
                validate_secret_key(invalid)

    def test_allowed_hosts_requires_explicit_exact_hosts(self):
        self.assertEqual(
            parse_allowed_hosts("api.example.test, api.example.test, 192.0.2.10"),
            ["api.example.test", "192.0.2.10"],
        )
        for invalid in (None, "", "*", ".example.test", "https://api.example.test", "api.example.test:443", "localhost"):
            with self.subTest(invalid=invalid), self.assertRaises(ImproperlyConfigured):
                parse_allowed_hosts(invalid)

    def test_cors_requires_exact_https_origins(self):
        self.assertEqual(
            parse_cors_origins("https://app.example.test,https://admin.example.test"),
            ["https://app.example.test", "https://admin.example.test"],
        )
        for invalid in (
            None,
            "",
            "*",
            "http://app.example.test",
            "https://*.example.test",
            "https://app.example.test/path",
            "https://user@app.example.test",
            "https://app.example.test:443",
            "https://app.example.test:invalid",
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ImproperlyConfigured):
                parse_cors_origins(invalid)

    def test_pilot_keeps_development_sqlite_path_and_isolates_test_database(self):
        from . import dev, pilot

        self.assertEqual(pilot.DATABASES["default"]["ENGINE"], dev.DATABASES["default"]["ENGINE"])
        # Django's test runner rewrites dev.DATABASES['default']['NAME'] to an
        # in-memory URI, so compare with the configured project path instead.
        self.assertEqual(pilot.PILOT_DATABASE_PATH, dev.BASE_DIR / "db.sqlite3")
        self.assertEqual(pilot.PILOT_TEST_DATABASE_NAME, ":memory:")
        self.assertFalse(pilot.DEBUG)

    def test_pilot_enables_secure_cookies_without_proxy_header_assumptions(self):
        from . import pilot

        self.assertTrue(pilot.SESSION_COOKIE_SECURE)
        self.assertTrue(pilot.CSRF_COOKIE_SECURE)
        self.assertIsNone(pilot.SECURE_PROXY_SSL_HEADER)
        self.assertFalse(pilot.SECURE_SSL_REDIRECT)
        self.assertFalse(pilot.CORS_ALLOW_ALL_ORIGINS)


class TestStorageIsolationTests(SimpleTestCase):
    def test_default_test_run_uses_temporary_local_storage_without_cloudinary_credentials(self):
        self.assertEqual(settings.DOCUMENT_STORAGE_BACKEND, 'local')
        self.assertEqual(settings.CLOUDINARY_STORAGE, {
            'CLOUD_NAME': '',
            'API_KEY': '',
            'API_SECRET': '',
        })
        self.assertEqual(
            settings.STORAGES['default']['BACKEND'],
            'django.core.files.storage.FileSystemStorage',
        )
        self.assertIn('epalengke-tests-', str(settings.PRIVATE_DOCUMENT_ROOT))
        self.assertEqual(os.environ.get('CLOUDINARY_URL'), '')
        self.assertEqual(os.environ.get('CLOUDINARY_CLOUD_NAME'), '')
        self.assertEqual(os.environ.get('CLOUDINARY_API_KEY'), '')
        self.assertEqual(os.environ.get('CLOUDINARY_API_SECRET'), '')


class CloudinaryProxyBootstrapTests(SimpleTestCase):
    def test_already_imported_upload_and_admin_clients_use_configured_proxy(self):
        import cloudinary

        # Import both SDK modules before proxy setup to reproduce the stale
        # module-level PoolManager that caused direct connections in WSGI.
        uploader = import_module('cloudinary.uploader')
        admin_api = import_module('cloudinary.api_client.call_api')
        original_proxy = cloudinary.config().api_proxy
        original_upload_http = uploader._http
        original_admin_http = admin_api._http
        proxy_url = 'http://proxy.synthetic.test:3128'

        try:
            from core.cloudinary_bootstrap import initialize_cloudinary_proxy

            with patch.dict(os.environ, {'CLOUDINARY_API_PROXY': proxy_url}):
                self.assertTrue(initialize_cloudinary_proxy())

            # These are the exact connectors used by uploader.upload/destroy
            # and cloudinary.api.resource, not a config-only assertion.
            for sdk_client in (uploader, admin_api):
                self.assertIsInstance(sdk_client._http, ProxyManager)
                self.assertEqual(str(sdk_client._http.proxy), proxy_url)

            # Exercise the SDK's upload/destroy request path while trapping
            # the connector request. The project test runner intentionally
            # disables the convenience upload/destroy methods globally.
            response = SimpleNamespace(data=b'{}', headers={}, status=200)
            with patch.object(uploader._http, 'request', return_value=response) as request:
                uploader.call_api(
                    'upload',
                    {'public_id': 'proxy-bootstrap-test'},
                    file=BytesIO(b'synthetic test payload'),
                    resource_type='image',
                    type='authenticated',
                    cloud_name='synthetic-cloud',
                    api_key='synthetic-key',
                    api_secret='synthetic-secret',
                )
                uploader.call_api(
                    'destroy',
                    {'public_id': 'proxy-bootstrap-test'},
                    resource_type='image',
                    type='authenticated',
                    cloud_name='synthetic-cloud',
                    api_key='synthetic-key',
                    api_secret='synthetic-secret',
                )
            self.assertEqual(request.call_count, 2)
            self.assertTrue(all(call.kwargs['url'].startswith('https://api.cloudinary.com/')
                                for call in request.call_args_list))
        finally:
            cloudinary.config(api_proxy=original_proxy)
            uploader._http = original_upload_http
            admin_api._http = original_admin_http
