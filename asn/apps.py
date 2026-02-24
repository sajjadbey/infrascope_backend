from django.apps import AppConfig


class AsnConfig(AppConfig):
    name = 'asn'
    
    def ready(self):
        import asn.signals
