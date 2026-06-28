from rest_framework.permissions import BasePermission

from apps.dealers.models import Dealer


class IsDealerStaff(BasePermission):
    message = "Authenticated dealer staff credentials are required."

    def has_permission(self, request, view) -> bool:
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and getattr(user, "dealer_id", None)
            and getattr(user, "is_active", False)
        )


class IsActiveDealerStaff(IsDealerStaff):
    message = "Your dealer account is suspended. Verify your email from Account settings to continue."

    def has_permission(self, request, view) -> bool:
        if not super().has_permission(request, view):
            return False
        dealer = getattr(request.user, "dealer", None)
        return bool(dealer and dealer.operational_status == Dealer.OperationalStatus.ACTIVE)


def has_platform_capability(user, capability: str) -> bool:
    if getattr(user, "is_superuser", False):
        return True
    role = getattr(user, "platform_role", None)
    return capability in set(getattr(role, "capabilities", None) or [])


def has_vehicle_review_permission(user, capability: str = "listing_review.read") -> bool:
    return bool(
        user
        and user.is_authenticated
        and getattr(user, "is_active", False)
        and (
            getattr(user, "is_superuser", False)
            or (getattr(user, "is_staff", False) and has_platform_capability(user, capability))
        )
    )


class IsDealerStaffOrVehicleReviewer(BasePermission):
    message = "Dealer staff or listing reviewer credentials are required."

    def has_permission(self, request, view) -> bool:
        return IsActiveDealerStaff().has_permission(
            request,
            view,
        ) or has_vehicle_review_permission(request.user)
