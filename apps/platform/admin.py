from django.contrib import admin

from .models import (
    AuditLog,
    ContentReport,
    ContentReportNote,
    DataSubjectRequest,
    DealerSanction,
    PlatformRole,
    PlatformSetting,
    SanctionAppeal,
    SecurityIncident,
    WatchlistEntry,
)


@admin.register(PlatformRole)
class PlatformRoleAdmin(admin.ModelAdmin):
    list_display = ["name", "created_at"]
    search_fields = ["name"]


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ["action", "target_type", "target_id", "actor", "created_at"]
    list_filter = ["action", "target_type"]
    search_fields = ["action", "target_id", "actor__email"]


@admin.register(ContentReport)
class ContentReportAdmin(admin.ModelAdmin):
    list_display = ["vehicle", "status", "reporter_contact", "created_at"]
    list_filter = ["status", "created_at"]
    search_fields = ["reporter_name", "reporter_contact", "reason"]


@admin.register(DataSubjectRequest)
class DataSubjectRequestAdmin(admin.ModelAdmin):
    list_display = ["requester_name", "requester_contact", "request_type", "status", "created_at"]
    list_filter = ["status", "request_type"]
    search_fields = ["requester_name", "requester_contact"]


@admin.register(DealerSanction)
class DealerSanctionAdmin(admin.ModelAdmin):
    list_display = ["dealer", "status", "created_at", "lifted_at"]
    list_filter = ["status"]
    search_fields = ["dealer__name", "reason"]


@admin.register(ContentReportNote)
class ContentReportNoteAdmin(admin.ModelAdmin):
    list_display = ["report", "author", "created_at"]
    search_fields = ["body", "author__email"]


@admin.register(SanctionAppeal)
class SanctionAppealAdmin(admin.ModelAdmin):
    list_display = ["dealer", "status", "created_at", "decided_at"]
    list_filter = ["status"]
    search_fields = ["dealer__name", "reason"]


@admin.register(PlatformSetting)
class PlatformSettingAdmin(admin.ModelAdmin):
    list_display = ["key", "updated_at"]
    search_fields = ["key"]


@admin.register(SecurityIncident)
class SecurityIncidentAdmin(admin.ModelAdmin):
    list_display = ["title", "severity", "status", "created_at"]
    list_filter = ["severity", "status"]
    search_fields = ["title", "description"]


@admin.register(WatchlistEntry)
class WatchlistEntryAdmin(admin.ModelAdmin):
    list_display = ["dealer", "vehicle", "status", "created_at"]
    list_filter = ["status"]
    search_fields = ["dealer__name", "vehicle__slug", "reason"]
