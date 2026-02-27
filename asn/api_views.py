from rest_framework import viewsets, views, status, response
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.db.models import Count
from django.shortcuts import get_object_or_404
from .models import ASN, Prefix, NetworkNode, Location, NodeType
from .serializers import (
    ASNSerializer,
    ASNDetailSerializer,
    NetworkNodeSerializer,
    LocationSerializer,
)
from .views import _resolve_to_ip, get_client_ip
from ipaddress import ip_address, ip_network


class DashboardStatsView(views.APIView):
    def get(self, request):
        return Response(
            {
                "total_asns": ASN.objects.count(),
                "total_prefixes_v4": Prefix.objects.filter(ip_version=4).count(),
                "total_prefixes_v6": Prefix.objects.filter(ip_version=6).count(),
                "total_locations": Location.objects.count(),
                "total_nodes": NetworkNode.objects.count(),
            }
        )


class ASNViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ASN.objects.select_related("network_type", "network_status").all()
    lookup_field = "asn_number"

    def get_serializer_class(self):
        if self.action == "retrieve":
            return ASNDetailSerializer
        return ASNSerializer


@api_view(["GET"])
def api_lookup_ip(request):
    query_ip = request.GET.get("ip", "").strip()
    client_ip = get_client_ip(request)
    raw_input = query_ip or client_ip

    if not raw_input:
        return Response({"error": "No IP provided"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        ip, resolved_domain = _resolve_to_ip(raw_input)
        ip_obj = ip_address(ip)
    except ValueError as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    version = ip_obj.version
    prefixes = Prefix.objects.filter(ip_version=version).select_related(
        "asn", "asn__network_type", "asn__network_status"
    )

    for prefix in prefixes:
        net = ip_network(f"{prefix.network}/{prefix.prefix_length}", strict=False)
        if ip_obj in net:
            result = {
                "ip": ip,
                "prefix": prefix.cidr,
                "asn": prefix.asn.asn_number,
                "provider": prefix.asn.name,
                "network_type": prefix.asn.network_type.name,
                "status": prefix.asn.network_status.name,
            }
            if resolved_domain:
                result["resolved_domain"] = resolved_domain
            return Response(result)

    return Response(
        {"error": "No matching prefix found", "ip": ip},
        status=status.HTTP_404_NOT_FOUND,
    )


@api_view(["GET"])
def api_topology_data(request):
    """Mirror of the existing asn_topology_data but using DRF for consistency"""
    from .views import asn_topology_data

    return asn_topology_data(request)


@api_view(["GET"])
def api_network_nodes(request):
    """Mirror of the existing network_nodes_geojson but using DRF for consistency"""
    from .views import network_nodes_geojson

    return network_nodes_geojson(request)
