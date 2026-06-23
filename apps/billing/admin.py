from django.contrib import admin

from .models import BillingDispute, BillingPlan, Invoice, PaymentEvent, Subscription


@admin.register(BillingPlan)
class BillingPlanAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "price_ngn", "listing_limit", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["id", "name"]


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ["dealer", "plan", "status", "current_period_end", "created_at"]
    list_filter = ["status", "plan"]
    search_fields = ["dealer__name"]


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ["dealer", "amount_ngn", "status", "issued_at"]
    list_filter = ["status", "issued_at"]
    search_fields = ["dealer__name"]


@admin.register(PaymentEvent)
class PaymentEventAdmin(admin.ModelAdmin):
    list_display = ["provider", "event_type", "reference", "received_at"]
    search_fields = ["event_type", "reference"]


@admin.register(BillingDispute)
class BillingDisputeAdmin(admin.ModelAdmin):
    list_display = ["dealer", "invoice", "status", "created_at"]
    list_filter = ["status"]
    search_fields = ["dealer__name", "reason", "note"]
