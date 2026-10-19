from django.contrib import admin
from django.urls import path, include
from django.urls import re_path
from django.http import HttpResponseNotFound
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/', include('core.api_urls')),
    # Legacy document files may remain under MEDIA_ROOT. Never serve them as
    # static files; access is mediated by the authenticated document API.
    re_path(r'^media/documents(?:/.*)?$', lambda request, *args, **kwargs: HttpResponseNotFound()),
    # Complaint evidence follows the same rule, including legacy files kept in
    # MEDIA_ROOT while their database records remain unchanged.
    re_path(r'^media/complaints(?:/.*)?$', lambda request, *args, **kwargs: HttpResponseNotFound()),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
