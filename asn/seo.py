"""
SEO utilities: dynamic OG image generation, sitemap, robots.txt, and JSON-LD helpers.
"""
import io
import json

from django.conf import settings
from django.contrib.sitemaps import Sitemap
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.decorators.cache import cache_control
from django.views.decorators.http import require_GET
from PIL import Image, ImageDraw, ImageFont

from .models import ASN


# ─── Helpers ──────────────────────────────────────────────────

def get_site_url():
    return getattr(settings, 'SITE_URL', 'https://infrascope.ir').rstrip('/')


def absolute_url(path):
    return f"{get_site_url()}{path}"


# ─── JSON-LD Structured Data ─────────────────────────────────

def asn_jsonld(asn):
    """Generate JSON-LD structured data for an ASN detail page."""
    return json.dumps({
        "@context": "https://schema.org",
        "@type": "Dataset",
        "name": f"AS{asn.asn_number} — {asn.name}",
        "description": (
            f"Network infrastructure data for AS{asn.asn_number} ({asn.name}). "
            f"Type: {asn.network_type.name}. Status: {asn.network_status.name}. "
            f"Registrar: {asn.registrar or 'N/A'}."
        ),
        "url": absolute_url(reverse('asn_detail', args=[asn.asn_number])),
        "keywords": [
            "ASN", f"AS{asn.asn_number}", asn.name,
            "BGP", "Iran", "network infrastructure",
        ],
        "creator": {
            "@type": "Organization",
            "name": "InfraScope",
            "url": get_site_url(),
        },
        "distribution": {
            "@type": "DataDownload",
            "encodingFormat": "text/html",
            "contentUrl": absolute_url(reverse('asn_detail', args=[asn.asn_number])),
        },
    }, ensure_ascii=False)


# ─── Dynamic OG Image Generation ─────────────────────────────

# Brand colors matching the app theme
BG_COLOR = (15, 23, 42)       # --bg-header: #0f172a
BRAND_COLOR = (14, 165, 233)   # --color-brand: #0ea5e9
TEXT_WHITE = (248, 250, 252)   # --text-on-dark: #f8fafc
TEXT_MUTED = (148, 163, 184)   # --text-on-dark-muted: #94a3b8
CARD_BG = (30, 41, 59)        # --bg-footer: #1e293b
BORDER_COLOR = (51, 65, 85)   # slate-700


@require_GET
@cache_control(max_age=86400, public=True)
def og_image_asn(request, asn_number):
    """Generate a dynamic OG image card for a specific ASN."""
    asn = get_object_or_404(
        ASN.objects.select_related('network_type', 'network_status'),
        asn_number=asn_number,
    )

    width, height = 1200, 630
    img = Image.new('RGB', (width, height), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # Load fonts (use default if system fonts unavailable)
    try:
        font_xl = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 56)
        font_lg = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 32)
        font_md = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 26)
        font_sm = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 22)
        font_brand = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28)
    except (OSError, IOError):
        font_xl = ImageFont.load_default()
        font_lg = font_md = font_sm = font_brand = font_xl

    # ── Brand accent bar at top ──
    draw.rectangle([(0, 0), (width, 6)], fill=BRAND_COLOR)

    # ── Card background ──
    card_margin = 60
    card_top = 80
    card_bottom = height - 80
    draw.rounded_rectangle(
        [(card_margin, card_top), (width - card_margin, card_bottom)],
        radius=16,
        fill=CARD_BG,
        outline=BORDER_COLOR,
        width=2,
    )

    # ── ASN Number ──
    asn_text = f"AS{asn.asn_number}"
    draw.text((card_margin + 50, card_top + 45), asn_text, fill=BRAND_COLOR, font=font_xl)

    # ── Organization Name (truncate if too long) ──
    name = asn.name
    if len(name) > 45:
        name = name[:42] + "…"
    draw.text((card_margin + 50, card_top + 120), name, fill=TEXT_WHITE, font=font_lg)

    # ── Divider line ──
    divider_y = card_top + 185
    draw.line(
        [(card_margin + 50, divider_y), (width - card_margin - 50, divider_y)],
        fill=BORDER_COLOR, width=2,
    )

    # ── Info rows ──
    info_y = divider_y + 25
    row_height = 45

    info_items = [
        ("Type", asn.network_type.name),
        ("Status", asn.network_status.name),
        ("Registrar", asn.registrar or "N/A"),
    ]

    for label, value in info_items:
        draw.text((card_margin + 50, info_y), f"{label}:", fill=TEXT_MUTED, font=font_sm)
        draw.text((card_margin + 220, info_y), value, fill=TEXT_WHITE, font=font_sm)
        info_y += row_height

    # ── Brand footer ──
    brand_y = card_bottom - 60
    draw.text((card_margin + 50, brand_y), "🌐 InfraScope", fill=TEXT_MUTED, font=font_brand)
    draw.text(
        (width - card_margin - 360, brand_y + 4),
        "Iran Network Infrastructure",
        fill=TEXT_MUTED, font=font_sm,
    )

    # ── Output ──
    buffer = io.BytesIO()
    img.save(buffer, format='PNG', optimize=True)
    buffer.seek(0)
    return HttpResponse(buffer.read(), content_type='image/png')


@require_GET
@cache_control(max_age=86400, public=True)
def og_image_default(request):
    """Generate a default OG image for the site."""
    width, height = 1200, 630
    img = Image.new('RGB', (width, height), BG_COLOR)
    draw = ImageDraw.Draw(img)

    try:
        font_xl = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 64)
        font_lg = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 30)
    except (OSError, IOError):
        font_xl = ImageFont.load_default()
        font_lg = font_xl

    # Accent bar
    draw.rectangle([(0, 0), (width, 6)], fill=BRAND_COLOR)

    # Centered title
    draw.text((width // 2, 220), "🌐 InfraScope", fill=TEXT_WHITE, font=font_xl, anchor="mm")
    draw.text(
        (width // 2, 310),
        "Iran's Network Infrastructure Analysis",
        fill=TEXT_MUTED, font=font_lg, anchor="mm",
    )
    draw.text(
        (width // 2, 380),
        "ASN Topology  •  IP Lookup  •  BGP Routing",
        fill=BRAND_COLOR, font=font_lg, anchor="mm",
    )

    buffer = io.BytesIO()
    img.save(buffer, format='PNG', optimize=True)
    buffer.seek(0)
    return HttpResponse(buffer.read(), content_type='image/png')


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
    return HttpResponse(content.strip(), content_type='text/plain')


# ─── Sitemaps ─────────────────────────────────────────────────

class StaticViewSitemap(Sitemap):
    priority = 1.0
    changefreq = 'weekly'
    protocol = 'https'

    def items(self):
        return ['home', 'asn_full_topology', 'lookup_ip']

    def location(self, item):
        return reverse(item)


class ASNSitemap(Sitemap):
    changefreq = 'weekly'
    priority = 0.8
    protocol = 'https'
    limit = 5000  # split into index if needed

    def items(self):
        return ASN.objects.order_by('asn_number').values_list('asn_number', flat=True)

    def location(self, asn_number):
        return reverse('asn_detail', args=[asn_number])


sitemaps = {
    'static': StaticViewSitemap,
    'asn': ASNSitemap,
}
