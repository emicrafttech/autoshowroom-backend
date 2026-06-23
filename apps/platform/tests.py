from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import StaffUser
from apps.billing.models import BillingDispute, BillingPlan, Invoice, Subscription
from apps.buyers.models import BuyerConversation, BuyerMessage, BuyerOtp
from apps.dealers.models import Dealer, DealerLocation, DealerVerificationDocument
from apps.leads.models import AnalyticsEvent, GenericUploadRequest, Lead
from apps.platform.models import (
    ContentReport,
    DataSubjectRequest,
    DealerSanction,
    PlatformSetting,
    SanctionAppeal,
)
from apps.vehicles.models import Vehicle


class CsvCoverageCompletionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.dealer = Dealer.objects.create(
            slug="prime-motors",
            name="Prime Motors",
            legal_name="Prime Motors Limited",
            area="Wuse",
            phone="+2348011111111",
        )
        self.location = DealerLocation.objects.create(
            dealer=self.dealer,
            name="Main Stand",
            area="Wuse",
            is_primary=True,
        )
        self.staff = StaffUser.objects.create_user(
            email="owner@example.com",
            password="strong-pass-123",
            name="Owner",
            dealer=self.dealer,
            preferred_location=self.location,
        )
        self.platform_user = StaffUser.objects.create_user(
            email="platform@example.com",
            password="strong-pass-123",
            name="Platform",
            is_staff=True,
        )
        self.vehicle = Vehicle.objects.create(
            dealer=self.dealer,
            location=self.location,
            slug="toyota-camry-2020",
            make="Toyota",
            model="Camry",
            year=2020,
            trim="XLE",
            price_ngn=15000000,
            mileage_km=45000,
            transmission=Vehicle.Transmission.AUTOMATIC,
            fuel=Vehicle.Fuel.PETROL,
            colour="Black",
            body_type=Vehicle.BodyType.SEDAN,
            drivetrain=Vehicle.Drivetrain.FWD,
            condition_grade=Vehicle.ConditionGrade.GOOD,
            status=Vehicle.Status.AVAILABLE,
            listing_verification_status=Vehicle.ListingVerificationStatus.APPROVED,
            feed_ready=True,
            published_at=timezone.now(),
        )

    def buyer_token(self):
        response = self.client.post(
            "/v1/buyers/sign-in/start",
            {"phone": "+2348090000000"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        code = BuyerOtp.objects.get(phone="+2348090000000").code
        response = self.client.post(
            "/v1/buyers/sign-in/verify",
            {"phone": "+2348090000000", "code": code},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        return response.json()["data"]["token"]

    def test_dealer_staff_verification_sanction_and_privacy_flows(self):
        self.client.force_authenticate(self.staff)
        staff_response = self.client.post(
            "/v1/dealers/me/staff",
            {
                "email": "sales@example.com",
                "name": "Sales User",
                "role": StaffUser.Role.SALES,
            },
            format="json",
        )
        self.assertEqual(staff_response.status_code, 201)
        self.assertIn("inviteToken", staff_response.json()["data"])

        document_response = self.client.post(
            "/v1/dealers/me/verification/documents",
            {
                "kind": "cac",
                "title": "CAC Certificate",
                "fileUrl": "https://example.com/cac.pdf",
            },
            format="json",
        )
        self.assertEqual(document_response.status_code, 201)
        self.assertEqual(DealerVerificationDocument.objects.count(), 1)

        submit_response = self.client.post("/v1/dealers/me/verification/submit")
        self.assertEqual(submit_response.status_code, 200)
        self.dealer.refresh_from_db()
        self.assertEqual(self.dealer.verification_status, Dealer.VerificationStatus.PENDING)

        premises_response = self.client.post(
            f"/v1/dealers/me/locations/{self.location.id}/request-verification",
        )
        self.assertEqual(premises_response.status_code, 200)
        self.location.refresh_from_db()
        self.assertEqual(
            self.location.premises_verification_status,
            DealerLocation.PremisesVerificationStatus.PENDING,
        )

        DealerSanction.objects.create(dealer=self.dealer, reason="Policy issue")
        status_response = self.client.get("/v1/dealers/me/sanction-status")
        self.assertEqual(status_response.status_code, 200)
        self.assertTrue(status_response.json()["data"]["hasActiveSanction"])

        appeal_response = self.client.post(
            "/v1/dealers/me/sanction-appeal",
            {"reason": "We fixed this."},
            format="json",
        )
        self.assertEqual(appeal_response.status_code, 201)
        self.assertEqual(SanctionAppeal.objects.count(), 1)

        privacy_response = self.client.post(
            "/v1/dealers/me/privacy-request",
            {"reason": "Export my dealer records."},
            format="json",
        )
        self.assertEqual(privacy_response.status_code, 201)
        self.assertEqual(DataSubjectRequest.objects.count(), 1)

    def test_lead_management_reports_events_and_uploads(self):
        lead_response = self.client.post(
            "/v1/leads",
            {
                "vehicleId": str(self.vehicle.id),
                "name": "Ada Buyer",
                "phone": "+2348080000000",
                "source": "feed",
            },
            format="json",
        )
        self.assertEqual(lead_response.status_code, 201)
        lead = Lead.objects.get()

        self.client.force_authenticate(self.staff)
        list_response = self.client.get("/v1/leads")
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.json()["data"]["count"], 1)

        update_response = self.client.patch(
            f"/v1/leads/{lead.id}",
            {"stage": Lead.Stage.CONTACTED},
            format="json",
        )
        self.assertEqual(update_response.status_code, 200)

        self.client.force_authenticate(None)
        report_response = self.client.post(
            "/v1/reports",
            {"vehicleId": str(self.vehicle.id), "reason": "Suspicious details"},
            format="json",
        )
        self.assertEqual(report_response.status_code, 201)
        self.assertEqual(ContentReport.objects.count(), 1)

        event_response = self.client.post(
            "/v1/events",
            {"name": "vehicle_view", "vehicleId": str(self.vehicle.id), "payload": {"source": "test"}},
            format="json",
        )
        self.assertEqual(event_response.status_code, 201)
        self.assertEqual(AnalyticsEvent.objects.count(), 1)

        with patch(
            "apps.leads.views.create_presigned_upload",
            return_value=SimpleNamespace(
                key="uploads/test.pdf",
                upload_url="https://upload.example.com",
                public_url="https://cdn.example.com/test.pdf",
            ),
        ):
            upload_response = self.client.post(
                "/v1/uploads",
                {
                    "purpose": "verification",
                    "fileName": "test.pdf",
                    "contentType": "application/pdf",
                },
                format="json",
            )
        self.assertEqual(upload_response.status_code, 201)
        self.assertEqual(GenericUploadRequest.objects.count(), 1)

    def test_buyer_vehicle_chat_and_dealer_response(self):
        token = self.buyer_token()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        open_response = self.client.post(
            f"/v1/vehicles/{self.vehicle.id}/chats",
            {"message": "Is this still available?"},
            format="json",
        )
        self.assertEqual(open_response.status_code, 201)
        conversation = BuyerConversation.objects.get()
        self.assertEqual(BuyerMessage.objects.count(), 1)

        list_response = self.client.get(f"/v1/vehicles/{self.vehicle.id}/chats")
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(len(list_response.json()["data"]), 1)

        detail_response = self.client.get(f"/v1/vehicles/{self.vehicle.id}/chats/{conversation.id}")
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(detail_response.json()["data"]["vehicle"]["id"], str(self.vehicle.id))

        self.client.credentials()
        self.client.force_authenticate(self.staff)
        dealer_response = self.client.post(
            f"/v1/vehicles/{self.vehicle.id}/chats/{conversation.id}/messages",
            {"message": "Yes, it is available."},
            format="json",
        )
        self.assertEqual(dealer_response.status_code, 201)
        self.assertEqual(BuyerMessage.objects.count(), 2)

        other_dealer = Dealer.objects.create(slug="other-motors", name="Other Motors")
        other_staff = StaffUser.objects.create_user(
            email="other@example.com",
            password="strong-pass-123",
            name="Other Owner",
            dealer=other_dealer,
        )
        self.client.force_authenticate(other_staff)
        blocked_response = self.client.get(f"/v1/vehicles/{self.vehicle.id}/chats/{conversation.id}")
        self.assertEqual(blocked_response.status_code, 404)

    def test_platform_console_and_billing_operations(self):
        self.client.force_authenticate(self.platform_user)
        settings_response = self.client.patch(
            "/v1/platform/settings",
            {"marketplace": {"maintenanceMode": False}},
            format="json",
        )
        self.assertEqual(settings_response.status_code, 200)
        self.assertEqual(PlatformSetting.objects.count(), 1)

        overview_response = self.client.get("/v1/platform/overview")
        self.assertEqual(overview_response.status_code, 200)

        missing_reason_response = self.client.patch(
            f"/v1/dealers/{self.dealer.id}/verification/reject",
            {},
            format="json",
        )
        self.assertEqual(missing_reason_response.status_code, 400)

        reject_response = self.client.patch(
            f"/v1/dealers/{self.dealer.id}/verification/reject",
            {"reason": "Business documents could not be verified."},
            format="json",
        )
        self.assertEqual(reject_response.status_code, 200)

        incident_response = self.client.post(
            "/v1/platform/security-incidents",
            {"title": "Suspicious login", "severity": "high"},
            format="json",
        )
        self.assertEqual(incident_response.status_code, 201)

        watchlist_response = self.client.post(
            "/v1/platform/watchlists",
            {"dealerId": str(self.dealer.id), "reason": "Monitor activity"},
            format="json",
        )
        self.assertEqual(watchlist_response.status_code, 201)

        plan_response = self.client.post(
            "/v1/platform/billing/plans",
            {
                "id": "growth",
                "name": "Growth",
                "priceNgn": 50000,
                "listingLimit": 50,
                "features": [],
                "is_active": True,
            },
            format="json",
        )
        self.assertEqual(plan_response.status_code, 201)
        plan = BillingPlan.objects.get(id="growth")
        subscription = Subscription.objects.create(
            dealer=self.dealer,
            plan=plan,
            current_period_end=timezone.now() + timedelta(days=30),
        )
        invoice = Invoice.objects.create(
            dealer=self.dealer,
            subscription=subscription,
            amount_ngn=50000,
        )
        dispute_response = self.client.post(
            "/v1/platform/billing/disputes",
            {
                "dealerId": str(self.dealer.id),
                "invoiceId": str(invoice.id),
                "reason": "Wrong amount",
            },
            format="json",
        )
        self.assertEqual(dispute_response.status_code, 201)
        dispute = BillingDispute.objects.get()

        accept_response = self.client.post(
            f"/v1/platform/billing/disputes/{dispute.id}/accept",
        )
        self.assertEqual(accept_response.status_code, 200)

        refund_response = self.client.post(
            f"/v1/platform/billing/subscriptions/{subscription.id}/refund",
            {"amountNgn": 1000, "reason": "Goodwill"},
            format="json",
        )
        self.assertEqual(refund_response.status_code, 202)
