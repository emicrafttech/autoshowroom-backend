import json
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import StaffUser
from apps.billing.models import BillingPlan, EarlyPlanTermination, Invoice, PaymentEvent, Subscription
from apps.dealers.models import Dealer, DealerLocation


@override_settings(
    PAYSTACK_SECRET_KEY="sk_test_example",
    PAYSTACK_PUBLIC_KEY="pk_test_example",
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=False,
)
class PaystackCheckoutTests(TestCase):
    def setUp(self):
        self.notify_patcher = patch("apps.notifications.services.notify_payment_received")
        self.notify_patcher.start()
        self.addCleanup(self.notify_patcher.stop)
        self.client = APIClient()
        self.dealer = Dealer.objects.create(
            slug="paystack-dealer",
            name="Paystack Dealer",
            legal_name="Paystack Dealer Ltd",
            area="Wuse",
            phone="+2348000000000",
            plan_id="starter",
        )
        self.location = DealerLocation.objects.create(
            dealer=self.dealer,
            name="Main stand",
            area="Wuse",
            is_primary=True,
        )
        self.staff = StaffUser.objects.create_user(
            email="billing@dealer.test",
            password="password123",
            name="Billing Staff",
            dealer=self.dealer,
            role=StaffUser.Role.OWNER,
        )
        self.platform_user = StaffUser.objects.create_user(
            email="platform-billing@test.local",
            password="password123",
            name="Platform Billing",
            is_staff=True,
            is_superuser=True,
        )
        self.free_plan, _ = BillingPlan.objects.update_or_create(
            id="free",
            defaults={
                "name": "Free",
                "price_ngn": 0,
                "listing_limit": 1,
                "is_active": True,
            },
        )
        self.paid_plan, _ = BillingPlan.objects.update_or_create(
            id="growth",
            defaults={
                "name": "Growth",
                "price_ngn": 75000,
                "price_yearly_ngn": 675000,
                "listing_limit": 25,
                "stand_limit": None,
                "staff_limit": 5,
                "is_active": True,
            },
        )
        self.starter_plan, _ = BillingPlan.objects.update_or_create(
            id="starter",
            defaults={
                "name": "Starter",
                "price_ngn": 9999,
                "price_yearly_ngn": 89991,
                "listing_limit": 5,
                "stand_limit": None,
                "staff_limit": 1,
                "is_active": True,
            },
        )
        # Prior paid invoice so founding-trial eligibility does not short-circuit checkout tests.
        Invoice.objects.create(
            dealer=self.dealer,
            amount_ngn=9999,
            amount_ex_vat_ngn=9302,
            vat_ngn=697,
            status=Invoice.Status.PAID,
        )
        self.dealer.plan_id = "free"
        self.dealer.save(update_fields=["plan_id", "updated_at"])
        self.client.force_authenticate(self.staff)

    def test_platform_plan_count_includes_dealer_plan_id_without_subscription(self):
        self.client.force_authenticate(self.platform_user)

        response = self.client.get("/v1/platform/billing/plans")

        self.assertEqual(response.status_code, 200)
        payload = response.json()["data"]
        plans = payload["results"] if isinstance(payload, dict) else payload
        free_plan = next(plan for plan in plans if plan["id"] == self.free_plan.id)
        self.assertEqual(free_plan["activeDealerCount"], 1)

    def test_platform_plan_creation_does_not_auto_enroll_dealer(self):
        self.client.force_authenticate(self.platform_user)
        original_plan_id = self.dealer.plan_id

        response = self.client.post(
            "/v1/platform/billing/plans",
            {
                "id": "launch",
                "name": "Launch",
                "priceNgn": 25000,
                "listingLimit": 10,
                "standLimit": 1,
                "features": [],
                "isActive": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.dealer.refresh_from_db()
        self.assertEqual(self.dealer.plan_id, original_plan_id)
        self.assertFalse(Subscription.objects.filter(dealer=self.dealer, plan_id="launch").exists())

    def test_invoice_pdf_endpoint_streams_downloadable_pdf(self):
        subscription = Subscription.objects.create(
            dealer=self.dealer,
            plan=self.free_plan,
            current_period_end=timezone.now() + timedelta(days=30),
        )
        invoice = Invoice.objects.create(
            dealer=self.dealer,
            subscription=subscription,
            amount_ngn=15000,
            status=Invoice.Status.PAID,
        )

        response = self.client.get(f"/v1/billing/invoices/{invoice.id}/pdf")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertTrue(b"".join(response.streaming_content).startswith(b"%PDF"))

    def test_platform_can_list_early_plan_terminations(self):
        self.client.force_authenticate(self.platform_user)
        subscription = Subscription.objects.create(dealer=self.dealer, plan=self.free_plan)
        EarlyPlanTermination.objects.create(
            dealer=self.dealer,
            subscription=subscription,
            plan=self.free_plan,
            reason="Dealer is closing a branch early.",
        )

        response = self.client.get("/v1/platform/billing/terminations")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["results"][0]["reason"], "Dealer is closing a branch early.")

    def test_free_plan_checkout_completes_without_paystack(self):
        self.dealer.plan_id = "legacy"
        self.dealer.save(update_fields=["plan_id"])

        start = self.client.post(
            "/v1/billing/checkout",
            {"planId": self.free_plan.id},
            format="json",
        )
        self.assertEqual(start.status_code, 201)
        reference = start.json()["data"]["reference"]
        self.assertTrue(start.json()["data"]["fullyCovered"])

        complete = self.client.post(
            "/v1/billing/checkout/complete",
            {"planId": self.free_plan.id, "reference": reference},
            format="json",
        )
        self.assertEqual(complete.status_code, 201)
        self.dealer.refresh_from_db()
        self.assertEqual(self.dealer.plan_id, self.free_plan.id)
        self.assertEqual(
            Subscription.objects.filter(dealer=self.dealer, status=Subscription.Status.ACTIVE).count(),
            1,
        )

    @patch("apps.billing.checkout.verify_transaction")
    def test_paid_plan_checkout_returns_paystack_session(self, mock_verify):
        mock_verify.return_value = {
            "status": "success",
            "amount": self.paid_plan.price_ngn * 100,
            "metadata": {
                "dealer_id": str(self.dealer.id),
                "plan_id": self.paid_plan.id,
            },
            "authorization": {
                "authorization_code": "AUTH_test_code",
                "brand": "visa",
                "last4": "4081",
                "exp_month": "12",
                "exp_year": "2030",
                "reusable": True,
            },
        }

        start = self.client.post(
            "/v1/billing/checkout",
            {"planId": self.paid_plan.id},
            format="json",
        )
        self.assertEqual(start.status_code, 201)
        payload = start.json()["data"]
        self.assertFalse(payload["fullyCovered"])
        self.assertEqual(payload["publicKey"], "pk_test_example")
        self.assertEqual(payload["email"], "billing@dealer.test")
        self.assertEqual(payload["amountKobo"], self.paid_plan.price_ngn * 100)
        self.assertEqual(payload["reference"], payload["reference"].upper())
        self.assertTrue(payload["reference"].startswith("ASR"))

        complete = self.client.post(
            "/v1/billing/checkout/complete",
            {"planId": self.paid_plan.id, "reference": payload["reference"]},
            format="json",
        )
        self.assertEqual(complete.status_code, 201)
        mock_verify.assert_called_once()
        self.dealer.refresh_from_db()
        self.assertEqual(self.dealer.plan_id, self.paid_plan.id)
        paid_invoices = Invoice.objects.filter(dealer=self.dealer, status=Invoice.Status.PAID)
        self.assertEqual(paid_invoices.count(), 2)
        self.assertTrue(paid_invoices.filter(amount_ngn=self.paid_plan.price_ngn).exists())
        subscription = Subscription.objects.filter(
            dealer=self.dealer,
            status=Subscription.Status.ACTIVE,
        ).latest("created_at")
        self.assertEqual(subscription.payment_card_last4, "4081")
        self.assertEqual(subscription.payment_card_brand, "visa")

        summary = self.client.get("/v1/billing/summary")
        self.assertEqual(summary.status_code, 200)
        self.assertEqual(summary.json()["data"]["paymentMethod"]["last4"], "4081")

    @patch("apps.billing.checkout.verify_transaction")
    def test_paid_plan_complete_rejects_unverified_payment(self, mock_verify):
        mock_verify.return_value = {"status": "failed", "amount": 0, "metadata": {}}

        response = self.client.post(
            "/v1/billing/checkout/complete",
            {"planId": self.paid_plan.id, "reference": "asr_failed_ref"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    @patch("apps.billing.views.verify_webhook_signature", return_value=True)
    @patch("apps.billing.checkout.verify_transaction")
    def test_paystack_webhook_activates_subscription(self, mock_verify, _mock_signature):
        mock_verify.return_value = {
            "status": "success",
            "amount": self.paid_plan.price_ngn * 100,
            "metadata": {
                "dealer_id": str(self.dealer.id),
                "plan_id": self.paid_plan.id,
            },
        }
        reference = "asr_webhook_ref"
        payload = {
            "event": "charge.success",
            "data": {
                "reference": reference,
                "metadata": {
                    "dealer_id": str(self.dealer.id),
                    "plan_id": self.paid_plan.id,
                },
            },
        }

        response = self.client.post(
            "/v1/billing/webhooks/paystack",
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_PAYSTACK_SIGNATURE="test-signature",
        )
        self.assertEqual(response.status_code, 202)
        self.dealer.refresh_from_db()
        self.assertEqual(self.dealer.plan_id, self.paid_plan.id)
        self.assertTrue(
            PaymentEvent.objects.filter(reference=reference, event_type="checkout.completed").exists()
        )

    @patch("apps.billing.checkout.verify_transaction")
    def test_upgrade_prorates_current_plan_price(self, mock_verify):
        period_end = timezone.now() + timedelta(days=18)
        Subscription.objects.create(
            dealer=self.dealer,
            plan=self.starter_plan,
            status=Subscription.Status.ACTIVE,
            current_period_end=period_end,
        )
        self.dealer.plan_id = self.starter_plan.id
        self.dealer.save(update_fields=["plan_id"])

        expected_amount_kobo = (self.paid_plan.price_ngn - self.starter_plan.price_ngn) * 100
        mock_verify.return_value = {
            "status": "success",
            "amount": expected_amount_kobo,
            "metadata": {
                "dealer_id": str(self.dealer.id),
                "plan_id": self.paid_plan.id,
                "expected_amount_kobo": expected_amount_kobo,
            },
        }

        start = self.client.post(
            "/v1/billing/checkout",
            {"planId": self.paid_plan.id},
            format="json",
        )
        self.assertEqual(start.status_code, 201)
        payload = start.json()["data"]
        self.assertEqual(payload["amountKobo"], expected_amount_kobo)
        self.assertEqual(payload["creditAppliedNgn"], self.starter_plan.price_ngn)
        self.assertEqual(payload["checkoutKind"], "upgrade_prorated")

        complete = self.client.post(
            "/v1/billing/checkout/complete",
            {"planId": self.paid_plan.id, "reference": payload["reference"]},
            format="json",
        )
        self.assertEqual(complete.status_code, 201)
        subscription = Subscription.objects.filter(
            dealer=self.dealer,
            status=Subscription.Status.ACTIVE,
        ).latest("created_at")
        self.assertEqual(subscription.plan_id, self.paid_plan.id)
        self.assertEqual(subscription.current_period_end, period_end)
        invoice = Invoice.objects.filter(dealer=self.dealer).latest("issued_at")
        self.assertEqual(invoice.amount_ngn, self.paid_plan.price_ngn - self.starter_plan.price_ngn)

    def test_downgrade_schedules_for_next_cycle(self):
        period_end = timezone.now() + timedelta(days=12)
        Subscription.objects.create(
            dealer=self.dealer,
            plan=self.paid_plan,
            status=Subscription.Status.ACTIVE,
            current_period_end=period_end,
        )
        self.dealer.plan_id = self.paid_plan.id
        self.dealer.save(update_fields=["plan_id"])

        response = self.client.post(
            "/v1/billing/downgrade-request",
            {"targetPlanId": self.starter_plan.id},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        payload = response.json()["data"]
        self.assertEqual(payload["planId"], self.starter_plan.id)
        self.assertEqual(payload["status"], "scheduled")

        self.dealer.refresh_from_db()
        self.assertEqual(self.dealer.plan_id, self.paid_plan.id)
        subscription = Subscription.objects.get(dealer=self.dealer, status=Subscription.Status.ACTIVE)
        self.assertEqual(subscription.pending_plan_id, self.starter_plan.id)
        self.assertEqual(subscription.pending_plan_effective_at, period_end)

        summary = self.client.get("/v1/billing/summary")
        self.assertEqual(summary.status_code, 200)
        self.assertEqual(
            summary.json()["data"]["pendingDowngrade"]["planId"],
            self.starter_plan.id,
        )

    def test_checkout_rejects_downgrade_target(self):
        Subscription.objects.create(
            dealer=self.dealer,
            plan=self.paid_plan,
            status=Subscription.Status.ACTIVE,
            current_period_end=timezone.now() + timedelta(days=10),
        )
        self.dealer.plan_id = self.paid_plan.id
        self.dealer.save(update_fields=["plan_id"])

        response = self.client.post(
            "/v1/billing/checkout",
            {"planId": self.starter_plan.id},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    @patch("apps.billing.payment_method.verify_transaction")
    def test_payment_method_update_saves_card(self, mock_verify):
        Subscription.objects.create(
            dealer=self.dealer,
            plan=self.paid_plan,
            status=Subscription.Status.ACTIVE,
            current_period_end=timezone.now() + timedelta(days=20),
        )
        self.dealer.plan_id = self.paid_plan.id
        self.dealer.save(update_fields=["plan_id"])

        start = self.client.post("/v1/billing/payment-method/update", format="json")
        self.assertEqual(start.status_code, 201)
        payload = start.json()["data"]
        self.assertTrue(payload["reference"].startswith("ASRPMC"))
        self.assertEqual(payload["amountKobo"], 10000)
        self.assertEqual(payload["publicKey"], "pk_test_example")
        self.assertEqual(payload["metadata"]["purpose"], "payment_method_update")

        mock_verify.return_value = {
            "status": "success",
            "amount": payload["amountKobo"],
            "metadata": payload["metadata"],
            "authorization": {
                "authorization_code": "AUTH_card_update",
                "brand": "mastercard",
                "last4": "9012",
                "exp_month": "08",
                "exp_year": "2028",
                "reusable": True,
            },
        }

        complete = self.client.post(
            "/v1/billing/payment-method/complete",
            {"reference": payload["reference"]},
            format="json",
        )
        self.assertEqual(complete.status_code, 201)
        self.assertEqual(complete.json()["data"]["paymentMethod"]["last4"], "9012")
        self.assertEqual(complete.json()["data"]["paymentMethod"]["brand"], "mastercard")

        subscription = Subscription.objects.get(dealer=self.dealer, status=Subscription.Status.ACTIVE)
        self.assertEqual(subscription.payment_card_last4, "9012")
        self.assertEqual(subscription.payment_card_brand, "mastercard")
        self.assertTrue(
            PaymentEvent.objects.filter(
                reference=payload["reference"],
                event_type="payment_method.updated",
            ).exists()
        )

        summary = self.client.get("/v1/billing/summary")
        self.assertEqual(summary.json()["data"]["paymentMethod"]["last4"], "9012")

    def test_payment_method_update_requires_active_subscription(self):
        response = self.client.post("/v1/billing/payment-method/update", format="json")
        self.assertEqual(response.status_code, 400)
