from django.contrib import admin

from .models import Appointment, Booking


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ["buyer_name", "buyer_phone", "vehicle", "dealer", "scheduled_at", "status"]
    list_filter = ["status", "scheduled_at"]
    search_fields = ["buyer_name", "buyer_phone", "vehicle__slug", "dealer__name"]


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ["title", "dealer", "location", "vehicle", "scheduled_at"]
    list_filter = ["scheduled_at"]
    search_fields = ["title", "dealer__name", "vehicle__slug"]
