from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import path, include
from infrascope_backend.settings import SECRET_ADMIN_URL

from asn.seo import sitemaps

urlpatterns = [
    path(SECRET_ADMIN_URL, admin.site.urls),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
    path('', include('asn.urls')),
]
