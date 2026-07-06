from __future__ import annotations

from apps.leads.models import Lead

STAGE_RANK = {
    Lead.Stage.NEW: 0,
    Lead.Stage.CONTACTED: 1,
    Lead.Stage.INSPECTION: 2,
    Lead.Stage.RESERVED: 3,
    Lead.Stage.SOLD: 4,
}

TERMINAL_STAGES = {Lead.Stage.LOST, Lead.Stage.SOLD}


def _should_promote(current_stage: str, target_stage: str) -> bool:
    if current_stage in TERMINAL_STAGES:
        return False
    return STAGE_RANK.get(target_stage, 0) > STAGE_RANK.get(current_stage, 0)


def _find_existing_lead(*, dealer_id, vehicle_id, phone: str) -> Lead | None:
    return (
        Lead.objects.filter(
            dealer_id=dealer_id,
            vehicle_id=vehicle_id,
            phone=phone,
        )
        .exclude(stage=Lead.Stage.LOST)
        .order_by("-updated_at")
        .first()
    )


def upsert_lead_for_buyer(
    *,
    buyer,
    vehicle,
    stage: str,
    source: str,
    message: str = "",
) -> tuple[Lead, bool]:
    name = (buyer.name or "").strip() or buyer.phone
    phone = buyer.phone
    email = buyer.email or None
    normalized_message = message.strip() or None

    existing = _find_existing_lead(
        dealer_id=vehicle.dealer_id,
        vehicle_id=vehicle.id,
        phone=phone,
    )
    if existing:
        updates: list[str] = []
        if _should_promote(existing.stage, stage):
            existing.stage = stage
            updates.append("stage")
        if source == Lead.Source.BOOKING and existing.source != Lead.Source.BOOKING:
            existing.source = source
            updates.append("source")
        if not existing.name and name:
            existing.name = name
            updates.append("name")
        if not existing.email and email:
            existing.email = email
            updates.append("email")
        if normalized_message and not existing.message:
            existing.message = normalized_message
            updates.append("message")
        if updates:
            existing.save(update_fields=[*updates, "updated_at"])
        return existing, False

    lead = Lead.objects.create(
        dealer=vehicle.dealer,
        location=vehicle.location,
        vehicle=vehicle,
        name=name,
        phone=phone,
        email=email,
        message=normalized_message,
        source=source,
        stage=stage,
    )
    return lead, True


def sync_lead_from_vehicle_view(*, buyer, vehicle) -> Lead | None:
    lead, created = upsert_lead_for_buyer(
        buyer=buyer,
        vehicle=vehicle,
        stage=Lead.Stage.NEW,
        source=Lead.Source.FEED,
    )
    if created:
        from apps.notifications.services import notify_new_lead

        notify_new_lead(lead)
    return lead


def sync_lead_from_buyer_chat(*, buyer, vehicle, message: str = "") -> Lead | None:
    lead, created = upsert_lead_for_buyer(
        buyer=buyer,
        vehicle=vehicle,
        stage=Lead.Stage.CONTACTED,
        source=Lead.Source.FEED,
        message=message,
    )
    if created:
        from apps.notifications.services import notify_new_lead

        notify_new_lead(lead)
    return lead


def sync_lead_from_booking(*, buyer, vehicle, message: str = "") -> Lead | None:
    lead, created = upsert_lead_for_buyer(
        buyer=buyer,
        vehicle=vehicle,
        stage=Lead.Stage.INSPECTION,
        source=Lead.Source.BOOKING,
        message=message,
    )
    if created:
        from apps.notifications.services import notify_new_lead

        notify_new_lead(lead)
    return lead
