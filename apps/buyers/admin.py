from django.contrib import admin

from .models import (
    Buyer,
    BuyerConversation,
    BuyerMessage,
    BuyerOtp,
    SavedVehicle,
    VehicleVisit,
)


@admin.register(Buyer)
class BuyerAdmin(admin.ModelAdmin):
    list_display = ["phone", "name", "email", "created_at"]
    search_fields = ["phone", "name", "email"]


@admin.register(BuyerOtp)
class BuyerOtpAdmin(admin.ModelAdmin):
    list_display = ["phone", "code", "expires_at", "consumed_at", "created_at"]
    search_fields = ["phone"]


@admin.register(SavedVehicle)
class SavedVehicleAdmin(admin.ModelAdmin):
    list_display = ["buyer", "vehicle", "created_at"]
    search_fields = ["buyer__phone", "vehicle__slug"]


@admin.register(VehicleVisit)
class VehicleVisitAdmin(admin.ModelAdmin):
    list_display = ["buyer", "vehicle", "created_at"]
    search_fields = ["buyer__phone", "vehicle__slug"]


@admin.register(BuyerConversation)
class BuyerConversationAdmin(admin.ModelAdmin):
    list_display = ["buyer", "dealer", "vehicle", "last_message_at", "created_at"]
    search_fields = ["buyer__phone", "dealer__name", "vehicle__slug"]


@admin.register(BuyerMessage)
class BuyerMessageAdmin(admin.ModelAdmin):
    list_display = ["conversation", "sender_type", "created_at"]
    list_filter = ["sender_type"]
