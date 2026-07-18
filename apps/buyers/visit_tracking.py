from django.utils import timezone

from apps.buyers.models import VehicleVisit


def record_vehicle_visit(*, buyer, vehicle) -> tuple[VehicleVisit, bool]:
    visit, created = VehicleVisit.objects.get_or_create(buyer=buyer, vehicle=vehicle)
    if not created:
        VehicleVisit.objects.filter(pk=visit.pk).update(created_at=timezone.now())
        visit.refresh_from_db(fields=["created_at"])
    return visit, created
