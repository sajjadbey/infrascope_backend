from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views, api_views
from .seo import robots_txt

router = DefaultRouter()
router.register(r"asns", api_views.ASNViewSet, basename="asn")

urlpatterns = [
    # API Endpoints
    path("api/", include(router.urls)),
    path("api/stats/", api_views.DashboardStatsView.as_view(), name="api_stats"),
    path("api/lookup/", api_views.api_lookup_ip, name="api_lookup"),
    path("api/topology/", api_views.api_topology_data, name="api_topology"),
    path("api/map/", api_views.api_network_nodes, name="api_map"),
    # SEO
    path("robots.txt", robots_txt, name="robots_txt"),
]
