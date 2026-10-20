"""PythonAnywhere WSGI entry point for the GeoMarketics pilot."""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Use the production checkout by default.
# Allows isolated startup validation with a different project directory.
PROJECT_ROOT = Path(
    os.environ.get(
        "GEOMARKETICS_PROJECT_ROOT",
        "/home/geomarketics/geomarketics-backend-capstone",
    )
).resolve()

if not (PROJECT_ROOT / "manage.py").is_file():
    raise RuntimeError("GeoMarketics project directory not found.")

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Load environment BEFORE importing Django or Cloudinary.
load_dotenv(PROJECT_ROOT / ".env")

os.environ["DJANGO_SETTINGS_MODULE"] = "core.settings.pilot"

# PythonAnywhere requires the outbound proxy for Cloudinary.
if os.environ.get("DOCUMENT_STORAGE_BACKEND", "").lower() == "cloudinary":
    if not (os.environ.get("https_proxy") or os.environ.get("HTTPS_PROXY")):
        raise RuntimeError("Cloudinary requires an HTTPS proxy on this host.")

# Initialize Cloudinary's HTTP clients BEFORE Django loads models.
from core.cloudinary_bootstrap import initialize_cloudinary_proxy

initialize_cloudinary_proxy()

# Start Django only after storage initialization is complete.
from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()
