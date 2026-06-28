from django.conf import settings
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .models import PaymentEvent, Subscription
from .paystack import PaystackError, verify_transaction
from .subscriptions import (
    apply_payment_method,
    get_active_subscription,
    payment_method_from_authorization,
    payment_method_payload,
)


PAYMENT_METHOD_PURPOSE = "payment_method_update"


def verification_amount_ngn() -> int:
    return max(1, int(getattr(settings, "PAYMENT_METHOD_VERIFICATION_NGN", 100)))


def _init_event(reference: str):
    return PaymentEvent.objects.filter(
        reference=reference,
        event_type="payment_method.initiated",
    ).first()


def _completed_event(reference: str):
    return PaymentEvent.objects.filter(
        reference=reference,
        event_type="payment_method.updated",
    ).first()


def start_payment_method_update(dealer, email: str) -> dict:
    subscription = get_active_subscription(dealer)
    if not subscription:
        raise ValidationError("Subscribe to a plan before saving a payment method.")

    amount_ngn = verification_amount_ngn()
    amount_kobo = amount_ngn * 100

    from .paystack import build_payment_method_reference

    reference = build_payment_method_reference()
    PaymentEvent.objects.create(
        event_type="payment_method.initiated",
        reference=reference,
        payload={
            "dealerId": str(dealer.id),
            "subscriptionId": str(subscription.id),
            "amountNgn": amount_ngn,
            "amountKobo": amount_kobo,
            "purpose": PAYMENT_METHOD_PURPOSE,
        },
    )
    return {
        "reference": reference,
        "email": email,
        "amountNgn": amount_ngn,
        "amountKobo": amount_kobo,
        "metadata": {
            "dealer_id": str(dealer.id),
            "subscription_id": str(subscription.id),
            "purpose": PAYMENT_METHOD_PURPOSE,
            "expected_amount_kobo": amount_kobo,
        },
    }


def _assert_verified_card_update(dealer, reference: str) -> tuple[Subscription, dict]:
    init_event = _init_event(reference)
    if not init_event:
        raise ValidationError("Unknown payment reference.")

    init_payload = init_event.payload or {}
    if init_payload.get("dealerId") != str(dealer.id):
        raise ValidationError("Payment does not belong to this dealer.")

    subscription = Subscription.objects.filter(
        id=init_payload.get("subscriptionId"),
        dealer=dealer,
        status__in=[Subscription.Status.TRIALING, Subscription.Status.ACTIVE],
    ).first()
    if not subscription:
        raise ValidationError("No active subscription found for this payment.")

    try:
        verified = verify_transaction(reference)
    except PaystackError as exc:
        raise ValidationError(str(exc)) from exc

    if verified.get("status") != "success":
        raise ValidationError("Payment was not successful.")

    metadata = verified.get("metadata") or {}
    if metadata.get("purpose") != PAYMENT_METHOD_PURPOSE:
        raise ValidationError("Payment was not for a card update.")
    if str(metadata.get("dealer_id")) != str(dealer.id):
        raise ValidationError("Payment does not belong to this dealer.")

    expected_kobo = int(
        metadata.get("expected_amount_kobo") or init_payload.get("amountKobo") or 0
    )
    paid_kobo = int(verified.get("amount") or 0)
    if paid_kobo < expected_kobo:
        raise ValidationError("Payment amount does not match the card verification charge.")

    return subscription, verified


def complete_payment_method_update(dealer, reference: str) -> dict:
    existing = _completed_event(reference)
    if existing:
        subscription = get_active_subscription(dealer)
        return {"paymentMethod": payment_method_payload(subscription)}

    subscription, verified = _assert_verified_card_update(dealer, reference)
    payment_method = payment_method_from_authorization(verified.get("authorization"))
    if not payment_method:
        raise ValidationError("No reusable card authorization was returned.")

    apply_payment_method(subscription, payment_method)
    subscription.updated_at = timezone.now()
    subscription.save(
        update_fields=[
            "paystack_authorization_code",
            "payment_card_brand",
            "payment_card_last4",
            "payment_card_exp_month",
            "payment_card_exp_year",
            "updated_at",
        ]
    )
    PaymentEvent.objects.create(
        event_type="payment_method.updated",
        reference=reference,
        payload={
            "dealerId": str(dealer.id),
            "subscriptionId": str(subscription.id),
            "last4": subscription.payment_card_last4,
            "brand": subscription.payment_card_brand,
        },
    )
    return {"paymentMethod": payment_method_payload(subscription)}


def handle_payment_method_success(reference: str, metadata: dict | None = None) -> bool:
    from apps.dealers.models import Dealer

    metadata = metadata or {}
    if metadata.get("purpose") != PAYMENT_METHOD_PURPOSE:
        return False

    dealer_id = metadata.get("dealer_id")
    if not dealer_id or not reference:
        return False

    dealer = Dealer.objects.filter(id=dealer_id).first()
    if not dealer:
        return False

    try:
        complete_payment_method_update(dealer, reference)
    except ValidationError:
        return False
    return True
