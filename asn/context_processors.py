from django.conf import settings


def site_url(request):
    """Inject SITE_URL into all template contexts."""
    return {
        'SITE_URL': getattr(settings, 'SITE_URL', 'https://infrascope.ir').rstrip('/'),
    }
