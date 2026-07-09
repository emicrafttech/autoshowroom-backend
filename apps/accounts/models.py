import uuid

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone


class StaffUserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email: str, password: str | None, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email).lower()
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email: str, password: str | None = None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email: str, password: str | None = None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", StaffUser.Role.OWNER)
        extra_fields.setdefault("name", "Admin")

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True")

        return self._create_user(email, password, **extra_fields)


class StaffUser(AbstractBaseUser, PermissionsMixin):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        MANAGER = "manager", "Manager"
        SALES = "sales", "Sales"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dealer = models.ForeignKey(
        "dealers.Dealer",
        on_delete=models.CASCADE,
        related_name="staff_users",
        null=True,
        blank=True,
    )
    platform_role = models.ForeignKey(
        "platform.PlatformRole",
        on_delete=models.SET_NULL,
        related_name="staff_users",
        null=True,
        blank=True,
    )
    preferred_location = models.ForeignKey(
        "dealers.DealerLocation",
        on_delete=models.SET_NULL,
        related_name="preferred_by_staff",
        null=True,
        blank=True,
    )
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=160)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.SALES)
    must_change_password = models.BooleanField(default=False)
    invite_token_hash = models.CharField(max_length=64, null=True, blank=True)
    invite_expires_at = models.DateTimeField(null=True, blank=True)
    password_reset_token_hash = models.CharField(max_length=64, null=True, blank=True)
    password_reset_expires_at = models.DateTimeField(null=True, blank=True)
    password_changed_at = models.DateTimeField(null=True, blank=True)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    email_verification_token_hash = models.CharField(max_length=64, null=True, blank=True)
    email_verification_sent_at = models.DateTimeField(null=True, blank=True)
    email_verification_required_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = StaffUserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        ordering = ["name", "email"]

    def __str__(self) -> str:
        return self.email

    @property
    def invite_pending(self) -> bool:
        return bool(
            self.invite_token_hash
            and self.invite_expires_at
            and self.invite_expires_at > timezone.now()
        )


class DealerSignupOtp(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    phone = models.CharField(max_length=32)
    code = models.CharField(max_length=8)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["phone", "code"])]

    @property
    def is_valid(self) -> bool:
        return self.consumed_at is None and self.expires_at > timezone.now()


class DealerPushDevice(models.Model):
    class Platform(models.TextChoices):
        ANDROID = "android", "Android"
        IOS = "ios", "iOS"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    staff_user = models.ForeignKey(
        StaffUser,
        on_delete=models.CASCADE,
        related_name="push_devices",
    )
    fcm_token = models.CharField(max_length=512)
    platform = models.CharField(max_length=20, choices=Platform.choices, default=Platform.ANDROID)
    last_seen_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["staff_user", "fcm_token"],
                name="unique_dealer_push_token",
            )
        ]
        ordering = ["-last_seen_at"]
