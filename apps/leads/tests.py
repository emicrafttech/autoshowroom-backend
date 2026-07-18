from datetime import timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import StaffUser
from apps.bookings.models import Booking
from apps.buyers.models import Buyer, BuyerOtp
from apps.dealers.models import Dealer, DealerLocation
from apps.leads.models import Lead, LeadNote
from apps.vehicles.models import Vehicle


class LeadAutomationTests(TestCase):
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
            district_slug="wuse",
            is_primary=True,
        )
        self.staff = StaffUser.objects.create_user(
            email="owner@example.com",
            password="strong-pass-123",
            name="Owner User",
            role=StaffUser.Role.OWNER,
            dealer=self.dealer,
            preferred_location=self.location,
        )
        self.vehicle = Vehicle.objects.create(
            dealer=self.dealer,
            location=self.location,
            slug="toyota-camry-2020",
            make="Toyota",
            model="Camry",
            year=2020,
            price_ngn=15000000,
            mileage_km=45000,
            transmission=Vehicle.Transmission.AUTOMATIC,
            fuel=Vehicle.Fuel.PETROL,
            body_type=Vehicle.BodyType.SEDAN,
            drivetrain=Vehicle.Drivetrain.FWD,
            condition_grade=Vehicle.ConditionGrade.GOOD,
            status=Vehicle.Status.AVAILABLE,
            listing_verification_status=Vehicle.ListingVerificationStatus.APPROVED,
            feed_ready=True,
            published_at=timezone.now(),
        )
        self.buyer = Buyer.objects.create(phone="+2348090000000", name="Ada Buyer")

    def buyer_token(self):
        start = self.client.post(
            "/v1/buyers/sign-in/start",
            {"phone": self.buyer.phone},
            format="json",
        )
        code = BuyerOtp.objects.get(phone=self.buyer.phone).code
        verify = self.client.post(
            "/v1/buyers/sign-in/verify",
            {"phone": self.buyer.phone, "code": code},
            format="json",
        )
        return verify.json()["data"]["token"]

    def available_booking_time(self):
        scheduled_at = timezone.now() + timedelta(days=1)
        while scheduled_at.weekday() > 4:
            scheduled_at += timedelta(days=1)
        return scheduled_at.astimezone(ZoneInfo("Africa/Lagos")).replace(
            hour=10,
            minute=30,
            second=0,
            microsecond=0,
        )

    @patch("apps.notifications.services.send_new_lead_alert_email.delay")
    @patch("apps.notifications.services.send_dealer_push_task.delay")
    def test_vehicle_view_only_pushes_on_first_view(self, send_push, send_email):
        token = self.buyer_token()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        response = self.client.get(f"/v1/feed/vehicles/{self.vehicle.id}")
        self.assertEqual(response.status_code, 200)

        lead = Lead.objects.get()
        self.assertEqual(lead.stage, Lead.Stage.NEW)
        self.assertEqual(lead.phone, self.buyer.phone)
        self.assertEqual(lead.vehicle_id, self.vehicle.id)
        send_email.assert_not_called()
        send_push.assert_called_once_with(
            str(self.dealer.id),
            title="New lead",
            body="You received a new lead. Tap to review the details.",
            data={
                "kind": "new_lead",
                "leadId": str(lead.id),
            },
        )

        lead.stage = Lead.Stage.LOST
        lead.save(update_fields=["stage", "updated_at"])
        repeat_response = self.client.get(f"/v1/feed/vehicles/{self.vehicle.id}")

        self.assertEqual(repeat_response.status_code, 200)
        self.assertEqual(Lead.objects.count(), 1)
        send_email.assert_not_called()
        self.assertEqual(send_push.call_count, 1)

    @patch("apps.notifications.services.notify_new_lead")
    def test_chat_promotes_lead_to_contacted(self, notify_new_lead):
        token = self.buyer_token()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        Lead.objects.create(
            dealer=self.dealer,
            location=self.location,
            vehicle=self.vehicle,
            name=self.buyer.name,
            phone=self.buyer.phone,
            stage=Lead.Stage.NEW,
            source=Lead.Source.FEED,
        )

        response = self.client.post(
            f"/v1/buyers/chat/vehicles/{self.vehicle.id}",
            {"message": "Is this still available?"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)

        lead = Lead.objects.get()
        self.assertEqual(lead.stage, Lead.Stage.CONTACTED)
        notify_new_lead.assert_not_called()

    @patch("apps.notifications.services.notify_new_lead")
    def test_booking_promotes_lead_to_inspection(self, notify_new_lead):
        token = self.buyer_token()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        Lead.objects.create(
            dealer=self.dealer,
            location=self.location,
            vehicle=self.vehicle,
            name=self.buyer.name,
            phone=self.buyer.phone,
            stage=Lead.Stage.CONTACTED,
            source=Lead.Source.FEED,
        )

        response = self.client.post(
            "/v1/bookings",
            {
                "vehicleId": str(self.vehicle.id),
                "scheduledAt": self.available_booking_time().isoformat(),
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)

        lead = Lead.objects.get()
        self.assertEqual(lead.stage, Lead.Stage.INSPECTION)
        self.assertEqual(lead.source, Lead.Source.BOOKING)
        notify_new_lead.assert_not_called()

    @patch("apps.notifications.services.notify_new_lead")
    def test_booking_without_prior_lead_creates_inspection_lead(self, notify_new_lead):
        token = self.buyer_token()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        response = self.client.post(
            "/v1/bookings",
            {
                "vehicleId": str(self.vehicle.id),
                "scheduledAt": self.available_booking_time().isoformat(),
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)

        lead = Lead.objects.get()
        self.assertEqual(lead.stage, Lead.Stage.INSPECTION)
        self.assertEqual(lead.source, Lead.Source.BOOKING)
        notify_new_lead.assert_called_once()

    def test_dealer_can_update_follow_up_and_add_lead_notes(self):
        self.client.force_authenticate(self.staff)
        lead = Lead.objects.create(
            dealer=self.dealer,
            location=self.location,
            vehicle=self.vehicle,
            name="Walk-in Buyer",
            phone="+2348091111111",
            source=Lead.Source.WALK_IN,
        )
        follow_up_at = (timezone.now() + timedelta(days=1)).replace(microsecond=0)

        update_response = self.client.patch(
            f"/v1/leads/{lead.id}",
            {"followUpAt": follow_up_at.isoformat()},
            format="json",
        )
        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(update_response.json()["data"]["followUpAt"], follow_up_at.isoformat().replace("+00:00", "Z"))

        note_response = self.client.post(
            f"/v1/leads/{lead.id}/notes",
            {"body": "Buyer wants a follow-up tomorrow."},
            format="json",
        )
        self.assertEqual(note_response.status_code, 201)
        self.assertEqual(LeadNote.objects.get(lead=lead).author, self.staff)

        list_response = self.client.get(f"/v1/leads/{lead.id}/notes")
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.json()["data"][0]["body"], "Buyer wants a follow-up tomorrow.")
