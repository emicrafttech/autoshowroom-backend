from rest_framework.permissions import BasePermission


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


def has_vehicle_review_permission(user) -> bool:
    return bool(
        user
        and user.is_authenticated
        and getattr(user, "is_active", False)
        and (getattr(user, "is_staff", False) or getattr(user, "is_superuser", False))
    )


class IsDealerStaffOrVehicleReviewer(BasePermission):
    message = "Dealer staff or listing reviewer credentials are required."

    def has_permission(self, request, view) -> bool:
        return IsDealerStaff().has_permission(
            request,
            view,
        ) or has_vehicle_review_permission(request.user)
