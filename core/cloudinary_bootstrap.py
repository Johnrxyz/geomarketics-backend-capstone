"""Configure Cloudinary's HTTP clients for PythonAnywhere's outbound proxy.

The Cloudinary SDK creates module-level urllib3 managers when its upload and
Admin API modules are imported. Updating ``cloudinary.config().api_proxy``
after those imports does not change the managers, so refresh both clients after
setting the proxy. This also covers imports that happened before WSGI startup.
"""

import importlib
import os


def initialize_cloudinary_proxy():
    """Apply the configured outbound proxy to Cloudinary upload/API clients.

    PythonAnywhere exposes the proxy as ``https_proxy``. Other common casing
    variants are accepted for local development. No proxy details are logged.

    Returns ``False`` when no proxy is configured and ``True`` when both SDK
    clients have been initialized with the proxy.
    """
    proxy = next(
        (
            os.environ.get(name, "").strip()
            for name in (
                "CLOUDINARY_API_PROXY",
                "https_proxy",
                "HTTPS_PROXY",
                "http_proxy",
                "HTTP_PROXY",
            )
            if os.environ.get(name, "").strip()
        ),
        "",
    )
    if not proxy:
        return False

    import cloudinary
    from cloudinary.utils import get_http_connector

    cloudinary.config(api_proxy=proxy)
    config = cloudinary.config()

    # Cloudinary 1.44.x keeps one module-level connector in each of these
    # modules. Import after setting api_proxy for normal startup, then replace
    # the connector as well in case either module was imported earlier.
    for module_name in (
        "cloudinary.uploader",
        "cloudinary.api_client.call_api",
    ):
        client_module = importlib.import_module(module_name)
        if not hasattr(client_module, "_http"):
            raise RuntimeError("Unsupported Cloudinary SDK HTTP client layout.")
        client_module._http = get_http_connector(config, cloudinary.CERT_KWARGS)

    return True
