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
    password_changed_at = models.DateTimeField(null=True, blank=True)
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
