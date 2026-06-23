from django.contrib import admin

from .models import Dealer, DealerLocation, DealerVerificationDocument


class DealerLocationInline(admin.TabularInline):
    model = DealerLocation
    extra = 0


@admin.register(Dealer)
class DealerAdmin(admin.ModelAdmin):
    inlines = [DealerLocationInline]
    list_display = ["name", "slug", "operational_status", "verification_status"]
    list_filter = ["operational_status", "verification_status"]
    search_fields = ["name", "legal_name", "slug", "phone"]


@admin.register(DealerLocation)
class DealerLocationAdmin(admin.ModelAdmin):
    list_display = ["name", "dealer", "area", "is_primary", "premises_verification_status"]
    list_filter = ["is_primary", "premises_verification_status"]
    search_fields = ["name", "dealer__name", "area", "district_slug"]


@admin.register(DealerVerificationDocument)
class DealerVerificationDocumentAdmin(admin.ModelAdmin):
    list_display = ["dealer", "kind", "title", "created_at"]
    list_filter = ["kind", "created_at"]
    search_fields = ["dealer__name", "title"]
