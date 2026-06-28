from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import DealerSignupOtp, StaffUser


@admin.register(StaffUser)
class StaffUserAdmin(UserAdmin):
    model = StaffUser
    list_display = ["email", "name", "dealer", "role", "is_active", "is_staff"]
    list_filter = ["role", "is_active", "is_staff", "is_superuser"]
    search_fields = ["email", "name", "dealer__name"]
    ordering = ["email"]
    fieldsets = [
        (None, {"fields": ["email", "password"]}),
        ("Profile", {"fields": ["name", "dealer", "preferred_location", "role"]}),
        (
            "Invite",
            {"fields": ["invite_token_hash", "invite_expires_at", "must_change_password"]},
        ),
        ("Permissions", {"fields": ["is_active", "is_staff", "is_superuser", "groups", "user_permissions"]}),
        ("Important dates", {"fields": ["last_login", "password_changed_at"]}),
    ]


@admin.register(DealerSignupOtp)
class DealerSignupOtpAdmin(admin.ModelAdmin):
    list_display = ["phone", "code", "expires_at", "consumed_at", "created_at"]
    list_filter = ["consumed_at", "created_at"]
    search_fields = ["phone", "code"]
    add_fieldsets = [
        (
            None,
            {
                "classes": ["wide"],
                "fields": [
                    "email",
                    "name",
                    "dealer",
                    "role",
                    "password1",
                    "password2",
                    "is_staff",
                    "is_superuser",
                ],
            },
        ),
    ]
