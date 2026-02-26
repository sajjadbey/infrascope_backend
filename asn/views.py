from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.db.models import Prefetch, Q
from ipaddress import ip_address, ip_network
import socket
from .models import ASN, Prefix, NetworkNode, Location
from .seo import asn_jsonld
from django.shortcuts import render, get_object_or_404


def get_client_ip(request):
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0]
    else:
        ip = request.META.get("REMOTE_ADDR")
    return ip


def _is_browser(request):
    """Return True if the request comes from a web browser."""
    accept = request.META.get("HTTP_ACCEPT", "")
    return "text/html" in accept


def _resolve_to_ip(value):
    """Try to interpret value as an IP address; if that fails, resolve it as a domain name.
    Returns (ip_string, resolved_domain_or_None).
    Raises ValueError when resolution fails."""
    # First, try parsing directly as an IP
    try:
        ip_address(value)
        return value, None
    except ValueError:
        pass

    # Not a valid IP — try DNS resolution (treat as domain)
    try:
        resolved = socket.gethostbyname(value)
        return resolved, value
    except (socket.gaierror, socket.herror, UnicodeError):
        raise ValueError(f"Could not resolve '{value}' as an IP address or domain name")


@require_GET
def lookup_ip(request):
    is_html = _is_browser(request)
    query_ip = request.GET.get("ip", "").strip()
    client_ip = get_client_ip(request)
    raw_input = query_ip or client_ip

    # Browser hit with no explicit IP query → show empty search page
    if is_html and not query_ip:
        return render(request, "asn/lookup.html", {"client_ip": client_ip})

    if not raw_input:
        if is_html:
            return render(
                request,
                "asn/lookup.html",
                {
                    "error": "Could not determine IP address",
                    "client_ip": client_ip,
                },
            )
        return JsonResponse({"error": "Could not determine IP address"}, status=400)

    # Resolve input — could be an IP or a domain name
    resolved_domain = None
    try:
        ip, resolved_domain = _resolve_to_ip(raw_input)
        ip_obj = ip_address(ip)
    except ValueError as e:
        if is_html:
            return render(
                request,
                "asn/lookup.html",
                {
                    "error": str(e),
                    "query_ip": raw_input,
                    "client_ip": client_ip,
                },
            )
        return JsonResponse({"error": str(e)}, status=400)

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
            if is_html:
                return render(
                    request,
                    "asn/lookup.html",
                    {
                        "result": result,
                        "query_ip": raw_input,
                        "client_ip": client_ip,
                        "resolved_domain": resolved_domain,
                        "resolved_ip": ip,
                    },
                )
            return JsonResponse(result)

    if is_html:
        return render(
            request,
            "asn/lookup.html",
            {
                "error": "No matching prefix found",
                "query_ip": raw_input,
                "client_ip": client_ip,
            },
        )
    return JsonResponse({"error": "No matching prefix found", "ip": ip}, status=404)


def home(request):
    """Render the home page."""
    return render(request, "asn/home.html")


def asn_detail(request, asn_number):
    asn = get_object_or_404(
        ASN.objects.select_related(
            "network_type",
            "network_status",
        ).prefetch_related(
            "upstreams",
            "downstreams",
            "prefixes",
        ),
        asn_number=asn_number,
    )

    prefixes_v4 = asn.prefixes.filter(ip_version=4).order_by("network", "prefix_length")
    prefixes_v6 = asn.prefixes.filter(ip_version=6).order_by("network", "prefix_length")

    context = {
        "asn": asn,
        "prefixes_v4": prefixes_v4,
        "prefixes_v6": prefixes_v6,
        "upstreams": asn.upstreams.all(),
        "downstreams": asn.downstreams.all(),
        "peers": asn.peers,
        "jsonld": asn_jsonld(asn),
    }

    return render(request, "asn/detail.html", context)


def asn_graph(request, asn_number):
    """Return the upstream topology rooted at a specific ASN.

    Walks upstreams until real tier-1 nodes (no upstreams) are reached,
    and includes direct downstreams of the root ASN for context.
    Uses the same role logic as the full topology view.
    """
    root = get_object_or_404(
        ASN.objects.prefetch_related("upstreams", "downstreams"),
        asn_number=asn_number,
    )

    nodes = {}
    edges = []
    visited = set()

    def get_role(asn):
        has_upstreams = asn.upstreams.exists()
        has_downstreams = asn.downstreams.exists()
        if has_upstreams and has_downstreams:
            return "transit"
        if not has_upstreams and has_downstreams:
            return "tier1"
        if has_upstreams and not has_downstreams:
            return "origin"
        return "standalone"

    def add_node(asn):
        if asn.id not in nodes:
            nodes[asn.id] = {
                "id": asn.id,
                "asn_number": asn.asn_number,
                "name": asn.name,
                "label": f"AS{asn.asn_number}\n{asn.name}",
                "role": get_role(asn),
            }

    def walk_upstreams(asn, max_depth=15):
        """Walk upstreams until tier-1 (no upstreams) is reached."""
        if asn.id in visited:
            return
        visited.add(asn.id)
        add_node(asn)

        if max_depth <= 0:
            return

        for up in asn.upstreams.all():
            add_node(up)
            edges.append({"from": asn.id, "to": up.id})
            walk_upstreams(up, max_depth - 1)

    # Walk upstreams from root
    walk_upstreams(root)

    return JsonResponse(
        {
            "nodes": list(nodes.values()),
            "edges": edges,
        }
    )


def asn_full_topology(request):
    """Render the full topology visualization page"""
    return render(request, "asn/full_topology.html")


@require_GET
def asn_summary(request, asn_number):
    """Return a short JSON summary of an ASN for the topology popup."""
    asn = get_object_or_404(
        ASN.objects.select_related("network_type", "network_status").prefetch_related(
            "upstreams", "downstreams", "prefixes"
        ),
        asn_number=asn_number,
    )
    return JsonResponse(
        {
            "asn_number": asn.asn_number,
            "name": asn.name,
            "network_type": asn.network_type.name,
            "network_status": asn.network_status.name,
            "registrar": asn.registrar or "—",
            "registered_to": asn.registered_to or "—",
            "upstreams_count": asn.upstreams.count(),
            "downstreams_count": asn.downstreams.count(),
            "prefixes_v4": asn.prefixes.filter(ip_version=4).count(),
            "prefixes_v6": asn.prefixes.filter(ip_version=6).count(),
            "detail_url": f"/{asn.asn_number}/",
        }
    )


def asn_topology_data(request):
    """Return ALL ASNs as nodes and all upstream relationships as edges."""
    nodes = {}
    edges = []

    all_asns = ASN.objects.prefetch_related("upstreams").all()

    for asn in all_asns:
        has_upstreams = asn.upstreams.exists()
        has_downstreams = asn.downstreams.exists()

        if has_upstreams and has_downstreams:
            role = "transit"
        elif not has_upstreams and has_downstreams:
            role = "tier1"
        elif has_upstreams and not has_downstreams:
            role = "origin"
        else:
            role = "standalone"

        nodes[asn.id] = {
            "id": asn.id,
            "asn_number": asn.asn_number,
            "name": asn.name,
            "label": f"AS{asn.asn_number}\n{asn.name}",
            "role": role,
        }

        for up in asn.upstreams.all():
            edges.append({"from": asn.id, "to": up.id})

    return JsonResponse(
        {
            "nodes": list(nodes.values()),
            "edges": edges,
        }
    )


def network_map(request):
    """Render the network topology map page using Leaflet."""
    return render(request, "asn/network_map.html")


@require_GET
def network_nodes_geojson(request):
    """Serialize Locations and their NetworkNodes into a GeoJSON FeatureCollection."""
    locations = Location.objects.prefetch_related("nodes__asn").all()

    features = []
    for loc in locations:
        nodes_data = []
        for node in loc.nodes.all():
            nodes_data.append(
                {
                    "id": node.id,
                    "name": node.name,
                    "asn_number": node.asn.asn_number,
                    "asn_name": node.asn.name,
                }
            )

        if not nodes_data:
            continue

        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [loc.point.x, loc.point.y],
                },
                "properties": {
                    "id": loc.id,
                    "name": loc.name,
                    "nodes": nodes_data,
                },
            }
        )

    return JsonResponse({"type": "FeatureCollection", "features": features})
