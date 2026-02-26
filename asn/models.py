from django.db import models
from django.contrib.gis.db import models as gis_models
from django.utils.text import slugify


class NetworkType(models.Model):
    """
    Network type classification (ISP, Backbone, IX, Enterprise, Hosting, etc.)
    Normalized to avoid string repetition and enable filtering
    """

    name = models.CharField(max_length=100, unique=True, verbose_name="Network Type")
    slug = models.SlugField(max_length=100, unique=True, db_index=True)

    class Meta:
        verbose_name = "Network Type"
        verbose_name_plural = "Network Types"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class NetworkStatus(models.Model):
    """
    Network status classification (Active, Allocated, Reserved, etc.)
    Normalized to track ASN lifecycle states
    """

    name = models.CharField(max_length=100, unique=True, verbose_name="Status")
    slug = models.SlugField(max_length=100, unique=True, db_index=True)

    class Meta:
        verbose_name = "Network Status"
        verbose_name_plural = "Network Statuses"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class ASN(models.Model):
    """
    Core ASN model for BGP analysis and network infrastructure mapping.
    Supports self-referencing relationships for BGP peering topology.
    """

    asn_number = models.PositiveIntegerField(
        unique=True,
        db_index=True,
        verbose_name="ASN Number",
        help_text="Autonomous System Number (e.g., 64512)",
    )
    name = models.CharField(max_length=255, verbose_name="Organization Name")
    slug = models.SlugField(max_length=255, unique=True, db_index=True)
    description = models.TextField(blank=True, null=True, verbose_name="Description")

    # Normalized foreign keys
    network_type = models.ForeignKey(
        NetworkType,
        on_delete=models.PROTECT,
        related_name="asns",
        verbose_name="Network Type",
    )
    network_status = models.ForeignKey(
        NetworkStatus,
        on_delete=models.PROTECT,
        related_name="asns",
        verbose_name="Network Status",
    )

    # Registration information
    registered_on = models.DateField(
        null=True, blank=True, verbose_name="Registration Date"
    )
    registered_to = models.CharField(
        max_length=255, blank=True, verbose_name="Registered To"
    )
    registrar = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Registrar",
        help_text="e.g., RIPE NCC, ARIN, APNIC",
    )

    # Optional tags for categorization (PostgreSQL ArrayField compatible, falls back to CharField)
    tags = models.CharField(
        max_length=500,
        blank=True,
        verbose_name="Tags",
        help_text="Comma-separated tags",
    )

    # BGP relationships - self-referencing for network topology
    # Upstreams: ASNs that provide transit to this ASN (editable)
    upstreams = models.ManyToManyField(
        "self",
        symmetrical=False,
        related_name="downstreams",
        blank=True,
        verbose_name="Upstream Providers",
    )

    @property
    def peers(self):
        """Returns all ASNs that are either upstream or downstream"""
        upstream_ids = self.upstreams.values_list("id", flat=True)
        downstream_ids = self.downstreams.values_list("id", flat=True)
        peer_ids = set(upstream_ids) | set(downstream_ids)
        return ASN.objects.filter(id__in=peer_ids)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created At")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated At")

    class Meta:
        verbose_name = "ASN"
        verbose_name_plural = "ASNs"
        ordering = ["asn_number"]
        indexes = [
            models.Index(fields=["asn_number"]),
            models.Index(fields=["slug"]),
            models.Index(fields=["network_type", "network_status"]),
        ]

    def __str__(self):
        return f"AS{self.asn_number} - {self.name}"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(f"{self.asn_number}-{self.name}")
        super().save(*args, **kwargs)


class Prefix(models.Model):
    """
    IP prefix model for IP → ASN lookup and BGP route analysis.
    Supports both IPv4 and IPv6 with CIDR notation.
    Designed for fast containment checks and range queries.
    """

    IP_VERSION_CHOICES = [
        (4, "IPv4"),
        (6, "IPv6"),
    ]

    # Network address (base IP of the prefix)
    network = models.GenericIPAddressField(
        verbose_name="Network Address",
        db_index=True,
        help_text="Base IP address of the prefix (e.g., 46.167.128.0)",
    )

    # CIDR prefix length
    prefix_length = models.PositiveSmallIntegerField(
        verbose_name="Prefix Length", help_text="CIDR prefix length (e.g., 19 for /19)"
    )

    # IP version for filtering and validation
    ip_version = models.PositiveSmallIntegerField(
        choices=IP_VERSION_CHOICES, default=4, db_index=True, verbose_name="IP Version"
    )

    description = models.TextField(
        blank=True,
        verbose_name="Description",
        help_text="Purpose or description of this prefix",
    )

    # Foreign key to ASN - critical for IP lookup
    asn = models.ForeignKey(
        ASN, on_delete=models.CASCADE, related_name="prefixes", verbose_name="ASN"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created At")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated At")

    class Meta:
        verbose_name = "IP Prefix"
        verbose_name_plural = "IP Prefixes"
        ordering = ["ip_version", "network", "prefix_length"]
        indexes = [
            models.Index(fields=["network", "prefix_length"]),
            models.Index(fields=["ip_version", "network"]),
            models.Index(fields=["asn", "ip_version"]),
        ]
        # Ensure unique prefix per ASN
        unique_together = [["network", "prefix_length", "asn"]]

    def __str__(self):
        return f"{self.network}/{self.prefix_length} → AS{self.asn.asn_number}"

    @property
    def cidr(self):
        """Returns CIDR notation string"""
        return f"{self.network}/{self.prefix_length}"


class Location(models.Model):
    """
    Geographical location (e.g., a specific city, data center, or building).
    One location can host multiple network nodes.
    """

    name = models.CharField(max_length=255, verbose_name="Location Name")
    point = gis_models.PointField(
        verbose_name="Coordinates",
        help_text="Click on the map to set the exact coordinates",
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created At")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated At")

    class Meta:
        verbose_name = "Location"
        verbose_name_plural = "Locations"
        ordering = ["name"]

    def __str__(self):
        return self.name


class NodeType(models.Model):
    """
    Classification for network nodes (e.g., IXP, Data Center, CDN Node, Router).
    """

    name = models.CharField(max_length=100, unique=True, verbose_name="Node Type")
    slug = models.SlugField(max_length=100, unique=True, db_index=True)
    color = models.CharField(
        max_length=7,
        default="#0ea5e9",
        verbose_name="Badge Color",
        help_text="Hex color code (e.g., #0ea5e9)",
    )

    class Meta:
        verbose_name = "Node Type"
        verbose_name_plural = "Node Types"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class NetworkNode(models.Model):
    """
    Represents a physical or logical network node (e.g., PoP, Data Center, Router)
    which may be present at multiple geographical Locations.
    """

    name = models.CharField(max_length=255, verbose_name="Node Name")
    asn = models.ForeignKey(
        ASN, on_delete=models.CASCADE, related_name="nodes", verbose_name="ASN"
    )
    locations = models.ManyToManyField(
        Location, related_name="nodes", verbose_name="Locations", blank=True
    )
    node_types = models.ManyToManyField(
        NodeType, related_name="nodes", verbose_name="Node Types", blank=True
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created At")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated At")

    class Meta:
        verbose_name = "Network Node"
        verbose_name_plural = "Network Nodes"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} (AS{self.asn.asn_number})"
