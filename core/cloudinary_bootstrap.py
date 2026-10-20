"""Initialize Cloudinary before its HTTP clients are imported."""

import os
import sys
from urllib.parse import quote, urlencode


def initialize_cloudinary_proxy():
    if os.environ.get("DOCUMENT_STORAGE_BACKEND", "local").lower() != "cloudinary":
        return

    proxy = os.environ.get("https_proxy") or os.environ.get("HTTPS_PROXY")

    # Standard connections remain available outside proxied hosts.
    if not proxy:
        return

    required = (
        "CLOUDINARY_CLOUD_NAME",
        "CLOUDINARY_API_KEY",
        "CLOUDINARY_API_SECRET",
    )

    if not all(os.environ.get(key) for key in required):
        raise RuntimeError("Cloudinary credentials are missing.")

    early_modules = (
        "cloudinary.api_client.call_api",
        "cloudinary.api",
        "cloudinary.uploader",
    )

    if any(name in sys.modules for name in early_modules):
        raise RuntimeError(
            "Cloudinary was imported before proxy initialization."
        )

    credentials = {
        key: os.environ.pop(key)
        for key in required
    }

    try:
        os.environ["CLOUDINARY_URL"] = (
            "cloudinary://"
            + quote(credentials["CLOUDINARY_API_KEY"], safe="")
            + ":"
            + quote(credentials["CLOUDINARY_API_SECRET"], safe="")
            + "@"
            + quote(credentials["CLOUDINARY_CLOUD_NAME"], safe="")
            + "?"
            + urlencode({"api_proxy": proxy})
        )

        # Initialize both cached HTTP clients with the proxy available.
        import cloudinary.api
        import cloudinary.uploader

    finally:
        os.environ.update(credentials)
