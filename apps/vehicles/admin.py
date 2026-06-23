from django.contrib import admin

from .models import Vehicle, VehicleMake, VehicleMedia, VehicleModel


class VehicleModelInline(admin.TabularInline):
    model = VehicleModel
    extra = 0


@admin.register(VehicleMake)
class VehicleMakeAdmin(admin.ModelAdmin):
    inlines = [VehicleModelInline]
    list_display = ["name", "display_order", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["name", "models__name"]


@admin.register(VehicleModel)
class VehicleModelAdmin(admin.ModelAdmin):
    list_display = ["name", "make", "display_order", "is_active"]
    list_filter = ["make", "is_active"]
    search_fields = ["name", "make__name"]


class VehicleMediaInline(admin.TabularInline):
    model = VehicleMedia
    extra = 0
    readonly_fields = ["created_at", "updated_at"]


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    inlines = [VehicleMediaInline]
    list_display = [
        "make",
        "model",
        "year",
        "dealer",
        "location",
        "status",
        "listing_verification_status",
        "price_ngn",
    ]
    list_filter = [
        "status",
        "listing_verification_status",
        "dealer",
        "location",
        "make",
        "model",
    ]
    search_fields = ["make", "model", "slug", "vin", "chassis_number", "dealer__name"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(VehicleMedia)
class VehicleMediaAdmin(admin.ModelAdmin):
    list_display = ["vehicle", "kind", "status", "sort_order", "content_type"]
    list_filter = ["kind", "status", "content_type"]
    search_fields = ["vehicle__make", "vehicle__model", "file_name", "s3_key", "url"]
    readonly_fields = ["created_at", "updated_at"]
