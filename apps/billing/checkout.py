from django.utils.dateparse import parse_datetime
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .models import BillingPlan, Invoice, PaymentEvent, Subscription
from .paystack import PaystackError, verify_transaction
from .plan_catalogue import vat_breakdown
from .serializers import InvoiceSerializer, SubscriptionSerializer
from .subscriptions import (
    apply_payment_method,
    copy_payment_method,
    default_period_end,
    founding_trial_period_end,
    get_active_subscription,
    payment_method_from_authorization,
)


def _checkout_init_event(reference: str):
    return PaymentEvent.objects.filter(
        reference=reference,
        event_type="checkout.initiated",
    ).first()


def _existing_checkout_result(reference: str):
    event = PaymentEvent.objects.filter(
        reference=reference,
        event_type="checkout.completed",
    ).first()
    if not event:
        return None
    payload = event.payload or {}
    subscription_id = payload.get("subscriptionId")
    invoice_id = payload.get("invoiceId")
    if not subscription_id:
        return None
    subscription = Subscription.objects.filter(id=subscription_id).select_related("plan").first()
    if not subscription:
        return None
    invoice = Invoice.objects.filter(id=invoice_id).first() if invoice_id else None
    return subscription, invoice


def _expected_amount_kobo(reference: str, plan: BillingPlan) -> int:
    init_event = _checkout_init_event(reference)
    if init_event and init_event.payload.get("amountKobo") is not None:
        return int(init_event.payload["amountKobo"])
    return int(plan.price_ngn) * 100


def _assert_verified_payment(dealer, plan: BillingPlan, reference: str) -> dict:
    try:
        verified = verify_transaction(reference)
    except PaystackError as exc:
        raise ValidationError(str(exc)) from exc

    if verified.get("status") != "success":
        raise ValidationError("Payment was not successful.")

    metadata = verified.get("metadata") or {}
    if str(metadata.get("dealer_id")) != str(dealer.id):
        raise ValidationError("Payment does not belong to this dealer.")
    if metadata.get("plan_id") != plan.id:
        raise ValidationError("Payment does not match the selected plan.")

    expected_kobo = int(metadata.get("expected_amount_kobo") or _expected_amount_kobo(reference, plan))
    paid_kobo = int(verified.get("amount") or 0)
    if paid_kobo < expected_kobo:
        raise ValidationError("Payment amount does not match the quoted plan price.")

    return verified


def activate_subscription(
    dealer,
    plan: BillingPlan,
    reference: str,
    *,
    amount_ngn: int | None = None,
    preserve_period_end=None,
    payment_method: dict | None = None,
):
    from .limits import soft_inactivate_excess_listings

    existing = _existing_checkout_result(reference)
    if existing:
        subscription, invoice = existing
        return subscription, invoice

    init_event = _checkout_init_event(reference)
    init_payload = init_event.payload if init_event else {}
    charged_amount_ngn = amount_ngn if amount_ngn is not None else init_payload.get("amountNgn", plan.price_ngn)
    billing_interval = init_payload.get("billingInterval") or Subscription.BillingInterval.MONTHLY
    checkout_kind = init_payload.get("checkoutKind")
    is_founding_trial = checkout_kind == "founding_trial"

    period_end = preserve_period_end
    if period_end is None and init_payload.get("preservePeriodEnd"):
        period_end = parse_datetime(init_payload["preservePeriodEnd"])
    if period_end is None and is_founding_trial:
        period_end = founding_trial_period_end()
    if period_end is None:
        period_end = default_period_end(billing_interval)

    active = get_active_subscription(dealer)
    if active and checkout_kind == "upgrade_prorated" and active.current_period_end:
        period_end = active.current_period_end

    previous_active = active
    if active:
        active.status = Subscription.Status.CANCELLED
        active.pending_plan_id = None
        active.pending_plan_effective_at = None
        active.updated_at = timezone.now()
        active.save(
            update_fields=[
                "status",
                "pending_plan_id",
                "pending_plan_effective_at",
                "updated_at",
            ]
        )

    subscription = Subscription.objects.create(
        dealer=dealer,
        plan=plan,
        status=Subscription.Status.TRIALING if is_founding_trial else Subscription.Status.ACTIVE,
        billing_interval=billing_interval,
        current_period_end=period_end,
    )
    if payment_method:
        apply_payment_method(subscription, payment_method)
    elif previous_active:
        copy_payment_method(previous_active, subscription)
    if subscription.payment_card_last4 or subscription.paystack_authorization_code:
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
    dealer.plan_id = plan.id
    dealer.save(update_fields=["plan_id", "updated_at"])
    soft_inactivate_excess_listings(dealer)

    tax = vat_breakdown(charged_amount_ngn)
    invoice = Invoice.objects.create(
        dealer=dealer,
        subscription=subscription,
        amount_ngn=charged_amount_ngn,
        amount_ex_vat_ngn=tax["amountExVatNgn"] if charged_amount_ngn else 0,
        vat_ngn=tax["vatNgn"] if charged_amount_ngn else 0,
        status=Invoice.Status.PAID,
    )
    PaymentEvent.objects.create(
        event_type="checkout.completed",
        reference=reference,
        payload={
            "dealerId": str(dealer.id),
            "planId": plan.id,
            "subscriptionId": str(subscription.id),
            "invoiceId": str(invoice.id),
            "amountNgn": charged_amount_ngn,
            "billingInterval": billing_interval,
            "checkoutKind": checkout_kind,
            "vatNgn": invoice.vat_ngn,
            "amountExVatNgn": invoice.amount_ex_vat_ngn,
        },
    )
    from apps.notifications.services import notify_payment_received

    if charged_amount_ngn > 0:
        notify_payment_received(invoice, reference)
    return subscription, invoice


def complete_checkout(dealer, plan: BillingPlan, reference: str):
    init_event = _checkout_init_event(reference)
    init_payload = init_event.payload if init_event else {}
    amount_ngn = init_payload.get("amountNgn", plan.price_ngn)
    payment_method = None

    if amount_ngn > 0:
        verified = _assert_verified_payment(dealer, plan, reference)
        payment_method = payment_method_from_authorization(verified.get("authorization"))

    subscription, invoice = activate_subscription(
        dealer,
        plan,
        reference,
        amount_ngn=amount_ngn,
        payment_method=payment_method,
    )
    return {
        "subscription": SubscriptionSerializer(subscription).data,
        "invoice": InvoiceSerializer(invoice).data,
    }


def handle_charge_success(reference: str, metadata: dict | None = None) -> bool:
    from apps.dealers.models import Dealer

    metadata = metadata or {}
    dealer_id = metadata.get("dealer_id")
    plan_id = metadata.get("plan_id")
    if not dealer_id or not plan_id or not reference:
        return False

    dealer = Dealer.objects.filter(id=dealer_id).first()
    plan = BillingPlan.objects.filter(id=plan_id, is_active=True).first()
    if not dealer or not plan:
        return False

    try:
        complete_checkout(dealer, plan, reference)
    except ValidationError:
        return False
    return True
