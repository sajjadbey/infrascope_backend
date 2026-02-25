"""
SEO utilities: sitemap, robots.txt, and JSON-LD helpers.
"""

import json

from django.conf import settings
from django.contrib.sitemaps import Sitemap
from django.http import HttpResponse
from django.urls import reverse
from django.views.decorators.cache import cache_control
from django.views.decorators.http import require_GET

from .models import ASN


# ─── Helpers ──────────────────────────────────────────────────


def get_site_url():
    return getattr(settings, "SITE_URL", "https://infrascope.ir").rstrip("/")


def absolute_url(path):
    return f"{get_site_url()}{path}"


# ─── JSON-LD Structured Data ─────────────────────────────────


def asn_jsonld(asn):
    """Generate JSON-LD structured data for an ASN detail page."""
    return json.dumps(
        {
            "@context": "https://schema.org",
            "@type": "Dataset",
            "name": f"AS{asn.asn_number} — {asn.name}",
            "description": (
                f"Network infrastructure data for AS{asn.asn_number} ({asn.name}). "
                f"Type: {asn.network_type.name}. Status: {asn.network_status.name}. "
                f"Registrar: {asn.registrar or 'N/A'}."
            ),
            "url": absolute_url(reverse("asn_detail", args=[asn.asn_number])),
            "keywords": [
                "ASN",
                f"AS{asn.asn_number}",
                asn.name,
                "BGP",
                "Iran",
                "network infrastructure",
            ],
            "creator": {
                "@type": "Organization",
                "name": "InfraScope",
                "url": get_site_url(),
            },
            "distribution": {
                "@type": "DataDownload",
                "encodingFormat": "text/html",
                "contentUrl": absolute_url(
                    reverse("asn_detail", args=[asn.asn_number])
                ),
            },
        },
        ensure_ascii=False,
    )


# ─── Robots.txt ───────────────────────────────────────────────


@require_GET
@cache_control(max_age=86400, public=True)
def robots_txt(request):
    site_url = get_site_url()
    content = f"""User-agent: *
Allow: /
Allow: /topology/
Allow: /lookup/

Disallow: /admin/

Sitemap: {site_url}/sitemap.xml
"""
    return HttpResponse(content.strip(), content_type="text/plain")


# ─── Sitemaps ─────────────────────────────────────────────────


class StaticViewSitemap(Sitemap):
    priority = 1.0
    changefreq = "weekly"
    protocol = "https"

    def items(self):
        return ["home", "asn_full_topology", "lookup_ip"]

    def location(self, item):
        return reverse(item)


class ASNSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.8
    protocol = "https"
    limit = 5000  # split into index if needed

    def items(self):
        return ASN.objects.order_by("asn_number").values_list("asn_number", flat=True)

    def location(self, asn_number):
        return reverse("asn_detail", args=[asn_number])


sitemaps = {
    "static": StaticViewSitemap,
    "asn": ASNSitemap,
}
