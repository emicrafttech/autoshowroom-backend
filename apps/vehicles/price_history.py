from apps.vehicles.models import Vehicle, VehiclePriceHistory


def record_vehicle_price(vehicle: Vehicle, price_ngn: int) -> None:
    latest = vehicle.price_history.order_by("-recorded_at").first()
    if latest and latest.price_ngn == price_ngn:
        return
    previous_price = latest.price_ngn if latest else None
    VehiclePriceHistory.objects.create(vehicle=vehicle, price_ngn=price_ngn)
    if previous_price is not None and price_ngn < previous_price:
        from apps.notifications.tasks import dispatch_price_alert_pushes_for_vehicle

        dispatch_price_alert_pushes_for_vehicle.delay(
            str(vehicle.id),
            previous_price_ngn=previous_price,
            match_kind="price_drop",
        )
