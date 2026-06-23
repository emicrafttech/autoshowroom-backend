from django.contrib import admin

from .models import AnalyticsEvent, GenericUploadRequest, Lead, NotifyMeRequest


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ["name", "phone", "dealer", "vehicle", "stage", "source", "created_at"]
    list_filter = ["stage", "source", "created_at"]
    search_fields = ["name", "phone", "email", "dealer__name", "vehicle__slug"]


@admin.register(NotifyMeRequest)
class NotifyMeRequestAdmin(admin.ModelAdmin):
    list_display = ["phone", "make", "model", "area", "created_at"]
    search_fields = ["phone", "email", "make", "model", "area"]


@admin.register(AnalyticsEvent)
class AnalyticsEventAdmin(admin.ModelAdmin):
    list_display = ["name", "buyer", "vehicle", "created_at"]
    list_filter = ["name", "created_at"]
    search_fields = ["name", "anonymous_id"]


@admin.register(GenericUploadRequest)
class GenericUploadRequestAdmin(admin.ModelAdmin):
    list_display = ["purpose", "file_name", "content_type", "created_at"]
    search_fields = ["purpose", "file_name", "s3_key"]
