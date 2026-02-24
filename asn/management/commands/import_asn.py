import json
from datetime import datetime
from django.core.management.base import BaseCommand
from django.db import transaction
from asn.models import ASN, NetworkType, NetworkStatus, Prefix


class Command(BaseCommand):
    help = 'Import ASNs from JSON file (fills empty fields only, always adds prefixes, upstreams, downstreams)'

    def add_arguments(self, parser):
        parser.add_argument('json_file', type=str, help='Path to JSON file')
        parser.add_argument('--registrar', type=str, default='RIPE NCC', help='Default registrar')
        parser.add_argument('--status', type=str, default='Active', help='Default network status')

    def _get_or_create_stub_asn(self, asn_number, description, default_status):
        """Get an existing ASN or create a stub entry for relationship linking."""
        try:
            return ASN.objects.get(asn_number=asn_number), False
        except ASN.DoesNotExist:
            unknown_type, _ = NetworkType.objects.get_or_create(name='Unknown')
            asn_obj = ASN.objects.create(
                asn_number=asn_number,
                name=description or f'AS{asn_number}',
                network_type=unknown_type,
                network_status=default_status,
            )
            return asn_obj, True

    def handle(self, *args, **options):
        with open(options['json_file'], 'r') as f:
            data = json.load(f)

        default_status, _ = NetworkStatus.objects.get_or_create(name=options['status'])
        
        created_count = 0
        updated_count = 0
        prefix_count = 0
        upstream_count = 0
        downstream_count = 0
        stub_count = 0

        for item in data:
            with transaction.atomic():
                asn_number = int(item['asn'])
                
                try:
                    asn_obj = ASN.objects.get(asn_number=asn_number)
                    # ASN exists - only fill empty fields
                    updated = False
                    
                    if not asn_obj.name:
                        asn_obj.name = item['name']
                        updated = True
                    
                    if not asn_obj.registered_to and item.get('registered_to'):
                        asn_obj.registered_to = item['registered_to']
                        updated = True
                    
                    if not asn_obj.registrar:
                        asn_obj.registrar = options['registrar']
                        updated = True
                    
                    if not asn_obj.registered_on and item.get('registered_on'):
                        try:
                            date_str = item['registered_on'].split('(')[0].strip()
                            asn_obj.registered_on = datetime.strptime(date_str, '%d %b %Y').date()
                            updated = True
                        except:
                            pass
                    
                    if not asn_obj.tags and item.get('tags'):
                        asn_obj.tags = ','.join(item['tags'])
                        updated = True
                    
                    if updated:
                        asn_obj.save()
                        updated_count += 1
                    
                except ASN.DoesNotExist:
                    # Create new ASN
                    network_type, _ = NetworkType.objects.get_or_create(name=item['network_type'])
                    
                    registered_on = None
                    if item.get('registered_on'):
                        try:
                            date_str = item['registered_on'].split('(')[0].strip()
                            registered_on = datetime.strptime(date_str, '%d %b %Y').date()
                        except:
                            pass
                    
                    asn_obj = ASN.objects.create(
                        asn_number=asn_number,
                        name=item['name'],
                        network_type=network_type,
                        network_status=default_status,
                        registered_on=registered_on,
                        registered_to=item.get('registered_to', ''),
                        registrar=options['registrar'],
                        tags=','.join(item.get('tags', [])),
                    )
                    created_count += 1
                
                # Always add prefixes
                for prefix_data in item.get('prefixes', []):
                    ip = prefix_data['ip'].strip()
                    mask = int(prefix_data['mask'])
                    
                    # Normalize IPv6 - remove trailing ::
                    if ':' in ip:
                        ip_version = 6
                        # Ensure proper IPv6 format (remove trailing :: if present)
                        if ip.endswith('::'):
                            ip = ip.rstrip(':')
                            if not ip:
                                ip = '::'
                    else:
                        ip_version = 4
                    
                    Prefix.objects.get_or_create(
                        network=ip,
                        prefix_length=mask,
                        asn=asn_obj,
                        defaults={
                            'ip_version': ip_version,
                            'description': prefix_data.get('description', '')
                        }
                    )
                    prefix_count += 1

                # Import upstreams
                for upstream_data in item.get('upstreams', []):
                    upstream_asn_number = int(upstream_data['asn'])
                    upstream_obj, was_created = self._get_or_create_stub_asn(
                        upstream_asn_number,
                        upstream_data.get('description', ''),
                        default_status,
                    )
                    if was_created:
                        stub_count += 1
                    asn_obj.upstreams.add(upstream_obj)
                    upstream_count += 1

                # Import downstreams
                for downstream_data in item.get('downstreams', []):
                    downstream_asn_number = int(downstream_data['asn'])
                    downstream_obj, was_created = self._get_or_create_stub_asn(
                        downstream_asn_number,
                        downstream_data.get('description', ''),
                        default_status,
                    )
                    if was_created:
                        stub_count += 1
                    # downstream's upstream is this ASN
                    downstream_obj.upstreams.add(asn_obj)
                    downstream_count += 1

        self.stdout.write(self.style.SUCCESS(
            f'✓ Created: {created_count} ASNs\n'
            f'✓ Updated: {updated_count} ASNs\n'
            f'✓ Stubs created: {stub_count} ASNs\n'
            f'✓ Prefixes: {prefix_count}\n'
            f'✓ Upstreams linked: {upstream_count}\n'
            f'✓ Downstreams linked: {downstream_count}'
        ))
