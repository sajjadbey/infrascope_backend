from django.urls import path
from . import views
from .seo import robots_txt

urlpatterns = [
    path("", views.home, name="home"),
    path("lookup/", views.lookup_ip, name="lookup_ip"),
    path("<int:asn_number>/", views.asn_detail, name="asn_detail"),
    path("<int:asn_number>/summary/", views.asn_summary, name="asn_summary"),
    path("<int:asn_number>/graph/", views.asn_graph, name="asn_graph"),
    path("topology/", views.asn_full_topology, name="asn_full_topology"),
    path("topology/data/", views.asn_topology_data, name="asn_topology_data"),
    # SEO
    path("robots.txt", robots_txt, name="robots_txt"),
]
