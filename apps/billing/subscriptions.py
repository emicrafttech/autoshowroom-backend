from datetime import timedelta

from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .models import BillingPlan, PaymentEvent, Subscription


def get_active_subscription(dealer):
    return (
        Subscription.objects.filter(
            dealer=dealer,
            status__in=[Subscription.Status.TRIALING, Subscription.Status.ACTIVE],
        )
        .select_related("plan", "pending_plan")
        .order_by("-created_at")
        .first()
    )


def subscription_period_is_active(subscription: Subscription | None) -> bool:
    if not subscription or not subscription.current_period_end:
        return False
    return subscription.current_period_end > timezone.now()


def compute_checkout_quote(dealer, target_plan: BillingPlan) -> dict:
    active = get_active_subscription(dealer)
    current_plan = active.plan if active else BillingPlan.objects.filter(id=dealer.plan_id, is_active=True).first()
    current_price_ngn = int(current_plan.price_ngn) if current_plan else 0
    target_price_ngn = int(target_plan.price_ngn)

    if target_price_ngn < current_price_ngn:
        raise ValidationError("Choose downgrade to switch to a lower plan at your next billing cycle.")

    if (
        target_price_ngn > current_price_ngn
        and subscription_period_is_active(active)
        and current_price_ngn > 0
    ):
        amount_ngn = max(0, target_price_ngn - current_price_ngn)
        return {
            "amount_ngn": amount_ngn,
            "amount_kobo": amount_ngn * 100,
            "list_price_ngn": target_price_ngn,
            "credit_applied_ngn": current_price_ngn,
            "checkout_kind": "upgrade_prorated",
            "preserve_period_end": active.current_period_end,
        }

    return {
        "amount_ngn": target_price_ngn,
        "amount_kobo": target_price_ngn * 100,
        "list_price_ngn": target_price_ngn,
        "credit_applied_ngn": 0,
        "checkout_kind": "new",
        "preserve_period_end": None,
    }


def apply_due_plan_changes(dealer) -> bool:
    subscription = get_active_subscription(dealer)
    if not subscription or not subscription.pending_plan_id or not subscription.pending_plan_effective_at:
        return False
    if timezone.now() < subscription.pending_plan_effective_at:
        return False

    subscription.plan_id = subscription.pending_plan_id
    subscription.pending_plan_id = None
    subscription.pending_plan_effective_at = None
    subscription.save(
        update_fields=[
            "plan_id",
            "pending_plan_id",
            "pending_plan_effective_at",
            "updated_at",
        ]
    )
    dealer.plan_id = subscription.plan_id
    dealer.save(update_fields=["plan_id", "updated_at"])
    return True


def schedule_downgrade(dealer, target_plan: BillingPlan, reason: str = "") -> dict:
    apply_due_plan_changes(dealer)

    active = get_active_subscription(dealer)
    if not active:
        raise ValidationError("No active subscription found.")

    current_plan = active.plan
    if current_plan.id == target_plan.id:
        raise ValidationError("You are already on this plan.")

    if int(target_plan.price_ngn) >= int(current_plan.price_ngn):
        raise ValidationError("Choose a lower plan to downgrade.")

    if not active.current_period_end:
        raise ValidationError("Renewal date is unknown. Contact support to change your plan.")

    if active.pending_plan_id == target_plan.id:
        effective_at = active.pending_plan_effective_at
    else:
        active.pending_plan_id = target_plan.id
        active.pending_plan_effective_at = active.current_period_end
        active.save(
            update_fields=[
                "pending_plan_id",
                "pending_plan_effective_at",
                "updated_at",
            ]
        )
        effective_at = active.pending_plan_effective_at
        PaymentEvent.objects.create(
            event_type="downgrade.scheduled",
            reference=str(dealer.id),
            payload={
                "targetPlanId": target_plan.id,
                "currentPlanId": current_plan.id,
                "effectiveAt": effective_at.isoformat() if effective_at else None,
                "reason": reason,
            },
        )

    return {
        "planId": target_plan.id,
        "planName": target_plan.name,
        "currentPlanId": current_plan.id,
        "currentPlanName": current_plan.name,
        "effectiveAt": effective_at,
        "status": "scheduled",
    }


def pending_downgrade_payload(subscription: Subscription | None) -> dict | None:
    if not subscription or not subscription.pending_plan_id or not subscription.pending_plan_effective_at:
        return None
    pending_plan = subscription.pending_plan or BillingPlan.objects.filter(id=subscription.pending_plan_id).first()
    if not pending_plan:
        return None
    return {
        "planId": pending_plan.id,
        "planName": pending_plan.name,
        "effectiveAt": subscription.pending_plan_effective_at,
    }


def payment_method_from_authorization(authorization: dict | None) -> dict | None:
    if not authorization:
        return None
    authorization_code = authorization.get("authorization_code") or authorization.get("authorizationCode")
    last4 = authorization.get("last4")
    if not authorization_code and not last4:
        return None
    brand = (authorization.get("brand") or authorization.get("card_type") or "card").strip()
    return {
        "authorizationCode": authorization_code,
        "brand": brand,
        "last4": last4 or "",
        "expMonth": str(authorization.get("exp_month") or authorization.get("expMonth") or ""),
        "expYear": str(authorization.get("exp_year") or authorization.get("expYear") or ""),
        "reusable": bool(authorization.get("reusable", True)),
    }


def payment_method_payload(subscription: Subscription | None) -> dict | None:
    if not subscription or not subscription.payment_card_last4:
        return None
    return {
        "brand": subscription.payment_card_brand or "card",
        "last4": subscription.payment_card_last4,
        "expMonth": subscription.payment_card_exp_month,
        "expYear": subscription.payment_card_exp_year,
    }


def apply_payment_method(subscription: Subscription, payment_method: dict | None) -> None:
    if not payment_method:
        return
    subscription.paystack_authorization_code = payment_method.get("authorizationCode") or ""
    subscription.payment_card_brand = payment_method.get("brand") or ""
    subscription.payment_card_last4 = payment_method.get("last4") or ""
    subscription.payment_card_exp_month = payment_method.get("expMonth") or ""
    subscription.payment_card_exp_year = payment_method.get("expYear") or ""


def copy_payment_method(source: Subscription | None, target: Subscription) -> None:
    if not source or not source.payment_card_last4:
        return
    apply_payment_method(
        target,
        {
            "authorizationCode": source.paystack_authorization_code,
            "brand": source.payment_card_brand,
            "last4": source.payment_card_last4,
            "expMonth": source.payment_card_exp_month,
            "expYear": source.payment_card_exp_year,
        },
    )


def default_period_end():
    return timezone.now() + timedelta(days=30)
