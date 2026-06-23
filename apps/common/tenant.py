from dataclasses import dataclass

from rest_framework.exceptions import NotAuthenticated


@dataclass(frozen=True)
class TenantContext:
    staff_id: str
    dealer_id: str
    location_id: str | None


def get_tenant_context(request) -> TenantContext:
    user = request.user
    if not user or not user.is_authenticated or not getattr(user, "dealer_id", None):
        raise NotAuthenticated("Authenticated dealer staff credentials are required.")

    return TenantContext(
        staff_id=str(user.id),
        dealer_id=str(user.dealer_id),
        location_id=str(user.preferred_location_id)
        if getattr(user, "preferred_location_id", None)
        else None,
    )
