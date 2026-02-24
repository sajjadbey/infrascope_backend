from django.contrib import admin
from django import forms
from .models import NetworkType, NetworkStatus, ASN, Prefix


class ASNAdminForm(forms.ModelForm):
    downstreams = forms.ModelMultipleChoiceField(
        queryset=ASN.objects.all(),
        required=False,
        widget=admin.widgets.FilteredSelectMultiple('Downstream ASNs', is_stacked=False),
        help_text="ASNs that use this ASN as their upstream provider."
    )

    class Meta:
        model = ASN
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            # Downstreams = ASNs whose upstreams include this ASN
            self.fields['downstreams'].initial = self.instance.downstreams.all()

    def save(self, commit=True):
        instance = super().save(commit=commit)

        if commit:
            self._save_downstreams(instance)
        else:
            # Defer M2M save until after the instance is saved
            old_save_m2m = self.save_m2m
            def new_save_m2m():
                old_save_m2m()
                self._save_downstreams(instance)
            self.save_m2m = new_save_m2m

        return instance

    def _save_downstreams(self, instance):
        new_downstreams = set(self.cleaned_data['downstreams'])
        current_downstreams = set(instance.downstreams.all())

        # Add: for each new downstream ASN, add this instance to their upstreams
        for asn in new_downstreams - current_downstreams:
            asn.upstreams.add(instance)

        # Remove: for each removed downstream ASN, remove this instance from their upstreams
        for asn in current_downstreams - new_downstreams:
            asn.upstreams.remove(instance)


@admin.register(NetworkType)
class NetworkTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug']
    search_fields = ['name']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(NetworkStatus)
class NetworkStatusAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug']
    search_fields = ['name']
    prepopulated_fields = {'slug': ('name',)}


class PrefixInline(admin.TabularInline):
    """Inline display of prefixes within ASN admin"""
    model = Prefix
    extra = 1
    fields = ['network', 'prefix_length', 'ip_version', 'description']


@admin.register(ASN)
class ASNAdmin(admin.ModelAdmin):
    form = ASNAdminForm
    list_display = [
        'asn_number',
        'name',
        'network_type',
        'network_status',
        'registrar',
        'created_at'
    ]
    list_filter = [
        'network_type',
        'network_status',
        'registrar',
        'created_at'
    ]
    search_fields = [
        'asn_number',
        'name',
        'description',
        'registered_to'
    ]
    prepopulated_fields = {'slug': ('name',)}
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('asn_number', 'name', 'slug', 'description', 'tags')
        }),
        ('Classification', {
            'fields': ('network_type', 'network_status')
        }),
        ('Registration', {
            'fields': ('registered_on', 'registered_to', 'registrar')
        }),
        ('BGP Relationships', {
            'fields': ('upstreams', 'downstreams'),
            'classes': ('collapse',)
        }),
    )
    
    filter_horizontal = ['upstreams']
    inlines = [PrefixInline]
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Prefix)
class PrefixAdmin(admin.ModelAdmin):
    list_display = [
        'cidr',
        'asn',
        'ip_version',
        'description',
        'created_at'
    ]
    list_filter = [
        'ip_version',
        'asn__network_type',
        'created_at'
    ]
    search_fields = [
        'network',
        'description',
        'asn__asn_number',
        'asn__name'
    ]
    autocomplete_fields = ['asn']
    
    fieldsets = (
        ('Prefix Information', {
            'fields': ('network', 'prefix_length', 'ip_version')
        }),
        ('Association', {
            'fields': ('asn', 'description')
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at']
