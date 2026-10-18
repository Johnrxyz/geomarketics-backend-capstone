"""Validation helpers for the deliberately strict PythonAnywhere pilot settings."""

import ipaddress
import re
from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured


_PLACEHOLDER_SECRET_MARKERS = (
    "django-insecure-",
    "generate-",
    "replace-",
    "your-",
    "change-me",
    "placeholder",
    "example",
)


def required_env(name, environ):
    """Return a required, trimmed environment value without a fallback."""
    value = environ.get(name, "")
    if not isinstance(value, str) or not value.strip():
        raise ImproperlyConfigured(f"{name} must be set to a non-empty value.")
    return value.strip()


def validate_secret_key(value):
    """Reject development keys and obvious sample values before Django starts."""
    if not isinstance(value, str) or not value:
        raise ImproperlyConfigured("SECRET_KEY must be set to a unique production value.")
    lowered = value.lower()
    if (
        len(value) < 50
        or len(set(value)) < 16
        or any(marker in lowered for marker in _PLACEHOLDER_SECRET_MARKERS)
    ):
        raise ImproperlyConfigured(
            "SECRET_KEY must be a unique, randomly generated value of at least 50 characters."
        )
    return value


def _csv_values(name, value):
    if not isinstance(value, str) or not value.strip():
        raise ImproperlyConfigured(f"{name} must contain one or more explicit values.")
    values = [part.strip() for part in value.split(",")]
    if any(not part for part in values):
        raise ImproperlyConfigured(f"{name} must not contain empty entries.")
    return values


def _is_exact_host(value):
    if value == "*" or value.startswith(".") or any(c in value for c in "/\\@?#"):
        return False
    if value.lower() == "localhost":
        return False
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        pass
    if len(value) > 253 or value.endswith("."):
        return False
    labels = value.split(".")
    return all(
        label
        and len(label) <= 63
        and re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?", label)
        for label in labels
    )


def parse_allowed_hosts(value):
    """Parse exact hostnames/IPs; reject Django's wildcard host forms."""
    hosts = _csv_values("ALLOWED_HOSTS", value)
    if any(not _is_exact_host(host) for host in hosts):
        raise ImproperlyConfigured(
            "ALLOWED_HOSTS must list exact hostnames or IP addresses without schemes, ports, paths, or wildcards."
        )
    return list(dict.fromkeys(host.lower() for host in hosts))


def parse_cors_origins(value):
    """Accept exact HTTPS origins only, with no wildcard or path component."""
    origins = _csv_values("CORS_ALLOWED_ORIGINS", value)
    normalized = []
    for origin in origins:
        try:
            parsed = urlsplit(origin)
            hostname = parsed.hostname
            port = parsed.port
        except ValueError as exc:
            raise ImproperlyConfigured(
                "CORS_ALLOWED_ORIGINS must contain valid exact HTTPS origins."
            ) from exc
        if (
            parsed.scheme.lower() != "https"
            or not hostname
            or parsed.username is not None
            or parsed.password is not None
            or port is not None
            or parsed.path
            or parsed.query
            or parsed.fragment
            or parsed.netloc.lower() != hostname.lower()
            or not _is_exact_host(hostname)
        ):
            raise ImproperlyConfigured(
                "CORS_ALLOWED_ORIGINS must contain exact HTTPS origins without ports, paths, credentials, or wildcards."
            )
        normalized.append(f"https://{hostname.lower()}")
    return list(dict.fromkeys(normalized))
