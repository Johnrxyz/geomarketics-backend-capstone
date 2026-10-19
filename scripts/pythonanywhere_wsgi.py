# This file contains the WSGI configuration required to serve your
# Django application on PythonAnywhere.
# 
# Instructions:
# 1. Open your PythonAnywhere Dashboard -> Web tab.
# 2. Click on the WSGI configuration file link (usually /var/www/<username>_pythonanywhere_com_wsgi.py).
# 3. Replace the entire contents of that file with the code below.
# 4. Make sure to replace 'yourusername' with your actual PythonAnywhere username!

import os
import sys
from dotenv import load_dotenv

# 1. REPLACE 'yourusername' with your actual PythonAnywhere username below:
USERNAME = 'yourusername'
PROJECT_FOLDER = 'backend' # The folder containing your manage.py

# 2. Path to your project directory
path = f'/home/{USERNAME}/{PROJECT_FOLDER}'
if path not in sys.path:
    sys.path.append(path)

# 3. Load environment variables from .env file
# PythonAnywhere doesn't load .env automatically, so we use python-dotenv
env_path = os.path.join(path, '.env')
if os.path.exists(env_path):
    load_dotenv(env_path)

# 4. Use the production-safe pilot settings.
# The required values are loaded from the private backend .env above or from
# the PythonAnywhere process environment. Pilot settings fail closed when
# SECRET_KEY, ALLOWED_HOSTS, or CORS_ALLOWED_ORIGINS are missing or invalid.
os.environ['DJANGO_SETTINGS_MODULE'] = 'core.settings.pilot'

# 5. Initialize the WSGI application
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
