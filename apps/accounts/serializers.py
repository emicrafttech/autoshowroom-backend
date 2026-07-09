import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import authenticate, password_validation
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify
from rest_framework import serializers

from apps.dealers.models import Dealer, DealerLocation
from apps.dealers.serializers import DealerContextLocationSerializer

from .models import DealerSignupOtp, StaffUser
from .tokens import hash_invite_token


class AuthUserSerializer(serializers.ModelSerializer):
    dealerId = serializers.UUIDField(source="dealer_id")
    mustChangePassword = serializers.BooleanField(source="must_change_password")
    emailVerified = serializers.SerializerMethodField()
    emailVerifiedAt = serializers.DateTimeField(source="email_verified_at", read_only=True)
    emailVerificationSentAt = serializers.DateTimeField(source="email_verification_sent_at", read_only=True)
    emailVerificationRequiredAt = serializers.DateTimeField(source="email_verification_required_at", read_only=True)
    locationId = serializers.SerializerMethodField()

    class Meta:
        model = StaffUser
        fields = [
            "id",
            "dealerId",
            "email",
            "name",
            "role",
            "mustChangePassword",
            "emailVerified",
            "emailVerifiedAt",
            "emailVerificationSentAt",
            "emailVerificationRequiredAt",
            "locationId",
        ]

    def get_emailVerified(self, obj):
        return obj.email_verified_at is not None

    def get_locationId(self, obj):
        location = self.context.get("active_location") or obj.preferred_location
        return str(location.id) if location else None


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(min_length=8, write_only=True)

    def validate(self, attrs):
        email = attrs["email"].lower()
        user = authenticate(
            request=self.context.get("request"),
            username=email,
            password=attrs["password"],
        )
        if not user:
            raise serializers.ValidationError("Invalid credentials")
        if not user.dealer:
            raise serializers.ValidationError("Dealer staff account is not configured")
        if user.dealer.operational_status == "banned":
            raise serializers.ValidationError(
                user.dealer.suspended_reason
                or "This dealer account has been permanently banned."
            )
        attrs["user"] = user
        return attrs


class DealerSignupStartSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=32)

    def validate_phone(self, value):
        if Dealer.objects.filter(phone=value).exists():
            raise serializers.ValidationError("A dealership already exists for this phone.")
        return value

    def create(self, validated_data):
        code = "123456" if settings.DEBUG else f"{secrets.randbelow(1_000_000):06d}"
        return DealerSignupOtp.objects.create(
            phone=validated_data["phone"],
            code=code,
            expires_at=timezone.now() + timedelta(minutes=settings.OTP_CODE_TTL_MINUTES),
        )


class DealerSignupVerifySerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=32)
    code = serializers.CharField(max_length=8)

    def validate(self, attrs):
        otp = DealerSignupOtp.objects.filter(
            phone=attrs["phone"],
            code=attrs["code"],
        ).first()
        if not otp or not otp.is_valid:
            raise serializers.ValidationError({"code": "Invalid or expired verification code."})
        attrs["otp"] = otp
        return attrs

    def make_slug(self, name: str) -> str:
        base = slugify(name)[:48] or "dealer"
        slug = base
        index = 2
        while Dealer.objects.filter(slug=slug).exists():
            suffix = f"-{index}"
            slug = f"{base[: 64 - len(suffix)]}{suffix}"
            index += 1
        return slug

    @transaction.atomic
    def create(self, validated_data):
        otp = validated_data.pop("otp")
        dealer_name = "New Dealer"
        area = "abuja"
        dealer = Dealer.objects.create(
            slug=self.make_slug(f"{dealer_name}-{otp.id.hex[:8]}"),
            name=dealer_name,
            legal_name=dealer_name,
            area=area,
            phone=validated_data["phone"],
            whatsapp=validated_data["phone"],
        )
        location = DealerLocation.objects.create(
            dealer=dealer,
            name="Main Stand",
            area=area,
            is_primary=True,
        )
        user = StaffUser.objects.create_user(
            email=f"dealer-{otp.id.hex}@pending.autoshowroom.local",
            password=None,
            name="Dealer Owner",
            role=StaffUser.Role.OWNER,
            dealer=dealer,
            preferred_location=location,
            must_change_password=True,
        )
        otp.consumed_at = timezone.now()
        otp.save(update_fields=["consumed_at"])
        return user


class DealerSignupSetupSerializer(serializers.Serializer):
    dealerName = serializers.CharField(max_length=160)
    email = serializers.EmailField()
    standName = serializers.CharField(max_length=80)
    districtSlug = serializers.CharField(max_length=120)
    address = serializers.CharField()

    def validate_email(self, value):
        email = value.lower()
        user = self.context["user"]
        if StaffUser.objects.exclude(id=user.id).filter(email=email).exists():
            raise serializers.ValidationError("An account already exists for this email.")
        return email

    def validate_districtSlug(self, value):
        district = value.strip()
        if not district:
            raise serializers.ValidationError("District is required.")
        district_slug = slugify(district)
        if not district_slug:
            raise serializers.ValidationError("Enter a valid district.")
        return district

    @transaction.atomic
    def save(self, **kwargs):
        user = self.context["user"]
        dealer = user.dealer
        dealer_name = self.validated_data["dealerName"]
        district_label = self.validated_data["districtSlug"]
        district_slug = slugify(district_label)
        dealer.name = dealer_name
        dealer.legal_name = dealer_name
        dealer.area = district_label
        dealer.district_slug = district_slug
        dealer.address = self.validated_data["address"]
        dealer.save(update_fields=["name", "legal_name", "area", "district_slug", "address", "updated_at"])

        location = user.preferred_location or dealer.locations.filter(is_primary=True).first()
        if location:
            location.name = self.validated_data["standName"]
            location.area = district_label
            location.district_slug = district_slug
            location.address = self.validated_data["address"]
            location.save(update_fields=["name", "area", "district_slug", "address", "updated_at"])
        else:
            location = DealerLocation.objects.create(
                dealer=dealer,
                name=self.validated_data["standName"],
                area=district_label,
                district_slug=district_slug,
                address=self.validated_data["address"],
                is_primary=True,
            )
            user.preferred_location = location

        user.email = self.validated_data["email"]
        user.email_verified_at = None
        user.email_verification_token_hash = None
        user.email_verification_sent_at = None
        user.email_verification_required_at = timezone.now()
        user.name = dealer_name
        user.save(
            update_fields=[
                "email",
                "email_verified_at",
                "email_verification_token_hash",
                "email_verification_sent_at",
                "email_verification_required_at",
                "name",
                "preferred_location",
                "updated_at",
            ]
        )
        return user


class DealerSignupPasswordSerializer(serializers.Serializer):
    password = serializers.CharField(min_length=8, max_length=128, write_only=True)
    confirmPassword = serializers.CharField(min_length=8, max_length=128, write_only=True)

    def validate(self, attrs):
        if attrs["password"] != attrs["confirmPassword"]:
            raise serializers.ValidationError({"confirmPassword": "Passwords do not match."})
        password_validation.validate_password(attrs["password"], self.context["user"])
        return attrs

    def save(self, **kwargs):
        user = self.context["user"]
        user.set_password(self.validated_data["password"])
        user.must_change_password = False
        user.save(update_fields=["password", "must_change_password", "updated_at"])
        return user


class RefreshSerializer(serializers.Serializer):
    refreshToken = serializers.CharField(min_length=1)


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        return value.lower()


class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.CharField(min_length=16)
    password = serializers.CharField(min_length=8, max_length=128, write_only=True)
    confirmPassword = serializers.CharField(min_length=8, max_length=128, write_only=True)

    def validate_token(self, value):
        token_hash = hash_invite_token(value)
        user = (
            StaffUser.objects.select_related("dealer")
            .filter(
                password_reset_token_hash=token_hash,
                password_reset_expires_at__gt=timezone.now(),
                dealer__isnull=False,
                is_active=True,
            )
            .first()
        )
        if not user:
            raise serializers.ValidationError("Password reset link is invalid or expired.")
        self.context["reset_user"] = user
        return value

    def validate(self, attrs):
        if attrs["password"] != attrs["confirmPassword"]:
            raise serializers.ValidationError({"confirmPassword": "Passwords do not match."})
        password_validation.validate_password(attrs["password"], self.context.get("reset_user"))
        return attrs


class EmailVerificationSendSerializer(serializers.Serializer):
    pass


class EmailVerificationVerifySerializer(serializers.Serializer):
    token = serializers.CharField(min_length=16)

    def validate_token(self, value):
        token_hash = hash_invite_token(value)
        user = StaffUser.objects.filter(email_verification_token_hash=token_hash).first()
        if not user:
            raise serializers.ValidationError("Email verification link is invalid or expired.")
        self.context["verification_user"] = user
        return value


class StaffInvitationPreviewSerializer(serializers.Serializer):
    token = serializers.CharField(min_length=16)

    def validate_token(self, value):
        token_hash = hash_invite_token(value)
        user = (
            StaffUser.objects.select_related("dealer")
            .filter(
                invite_token_hash=token_hash,
                invite_expires_at__gt=timezone.now(),
            )
            .first()
        )
        if not user:
            raise serializers.ValidationError("Invite link is invalid or expired")
        self.context["invite_user"] = user
        return value


class AcceptStaffInvitationSerializer(StaffInvitationPreviewSerializer):
    password = serializers.CharField(min_length=8, max_length=128, write_only=True)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        password_validation.validate_password(attrs["password"])
        return attrs


class ChangePasswordSerializer(serializers.Serializer):
    currentPassword = serializers.CharField(min_length=8, write_only=True)
    newPassword = serializers.CharField(min_length=8, max_length=128, write_only=True)

    def validate(self, attrs):
        password_validation.validate_password(attrs["newPassword"], self.context["user"])
        return attrs


class SessionLocationSerializer(serializers.Serializer):
    locationId = serializers.UUIDField()

    def validate_locationId(self, value):
        user = self.context["user"]
        location = DealerLocation.objects.filter(id=value, dealer_id=user.dealer_id).first()
        if not location:
            raise serializers.ValidationError("Location not found for this dealer")
        self.context["location"] = location
        return value


class DealerConsoleContextSerializer(serializers.Serializer):
    dealerName = serializers.CharField()
    activeLocationId = serializers.UUIDField(allow_null=True)
    locations = DealerContextLocationSerializer(many=True)
