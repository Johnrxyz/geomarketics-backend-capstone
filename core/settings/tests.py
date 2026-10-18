"""Focused validation tests for the production-safe pilot settings."""

from django.core.exceptions import ImproperlyConfigured
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
        self.assertEqual(pilot.PILOT_DATABASE_PATH, dev.DATABASES["default"]["NAME"])
        self.assertEqual(pilot.PILOT_TEST_DATABASE_NAME, ":memory:")
        self.assertFalse(pilot.DEBUG)

    def test_pilot_enables_secure_cookies_without_proxy_header_assumptions(self):
        from . import pilot

        self.assertTrue(pilot.SESSION_COOKIE_SECURE)
        self.assertTrue(pilot.CSRF_COOKIE_SECURE)
        self.assertIsNone(pilot.SECURE_PROXY_SSL_HEADER)
        self.assertFalse(pilot.SECURE_SSL_REDIRECT)
        self.assertFalse(pilot.CORS_ALLOW_ALL_ORIGINS)
