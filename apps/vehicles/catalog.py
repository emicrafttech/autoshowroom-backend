CATALOG_SOURCE = "local"


def normalize_make(value: str) -> str:
    collapsed = " ".join(value.strip().split())
    from .models import VehicleMake

    make = VehicleMake.objects.filter(name__iexact=collapsed, is_active=True).first()
    if make:
        return make.name
    return collapsed.title()


def get_makes() -> list[dict[str, int | str]]:
    from .models import VehicleMake

    return [
        {"id": make.id, "name": make.name}
        for make in VehicleMake.objects.filter(is_active=True).order_by(
            "display_order",
            "name",
        )
    ]


def get_models(make: str) -> list[dict[str, str]]:
    from .models import VehicleMake

    normalized_make = normalize_make(make)
    vehicle_make = VehicleMake.objects.filter(
        name__iexact=normalized_make,
        is_active=True,
    ).first()
    if not vehicle_make:
        return []
    return [
        {"name": model.name}
        for model in vehicle_make.models.filter(is_active=True).order_by(
            "display_order",
            "name",
        )
    ]
