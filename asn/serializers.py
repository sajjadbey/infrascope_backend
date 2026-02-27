from rest_framework import serializers
from .models import (
    NetworkType,
    NetworkStatus,
    ASN,
    Prefix,
    Location,
    NodeType,
    NetworkNode,
)


class NetworkTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = NetworkType
        fields = ["id", "name", "slug"]


class NetworkStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = NetworkStatus
        fields = ["id", "name", "slug"]


class NodeTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = NodeType
        fields = ["id", "name", "name_fa", "slug", "color"]


class PrefixSerializer(serializers.ModelSerializer):
    class Meta:
        model = Prefix
        fields = ["id", "network", "prefix_length", "ip_version", "cidr", "description"]


class ASNSerializer(serializers.ModelSerializer):
    network_type = NetworkTypeSerializer(read_only=True)
    network_status = NetworkStatusSerializer(read_only=True)

    class Meta:
        model = ASN
        fields = [
            "id",
            "asn_number",
            "name",
            "name_fa",
            "slug",
            "description",
            "description_fa",
            "network_type",
            "network_status",
            "registered_on",
            "registered_to",
            "registrar",
            "tags",
        ]


class ASNRecursiveSerializer(serializers.ModelSerializer):
    """Used for nested upstreams/downstreams to avoid infinite recursion while providing basic info"""

    class Meta:
        model = ASN
        fields = ["id", "asn_number", "name", "name_fa", "slug"]


class ASNDetailSerializer(ASNSerializer):
    prefixes = PrefixSerializer(many=True, read_only=True)
    upstreams = ASNRecursiveSerializer(many=True, read_only=True)
    downstreams = ASNRecursiveSerializer(many=True, read_only=True)

    class Meta(ASNSerializer.Meta):
        fields = ASNSerializer.Meta.fields + ["prefixes", "upstreams", "downstreams"]


class LocationSerializer(serializers.ModelSerializer):
    longitude = serializers.FloatField(source="point.x", read_only=True)
    latitude = serializers.FloatField(source="point.y", read_only=True)

    class Meta:
        model = Location
        fields = ["id", "name", "name_fa", "latitude", "longitude"]


class NetworkNodeSerializer(serializers.ModelSerializer):
    asns = ASNRecursiveSerializer(many=True, read_only=True)
    node_types = NodeTypeSerializer(many=True, read_only=True)

    class Meta:
        model = NetworkNode
        fields = ["id", "name", "name_fa", "asns", "node_types"]
