from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import StaffUser
from apps.billing.models import BillingPlan
from apps.bookings.models import Appointment, Booking
from apps.buyers.models import BuyerOtp, SavedVehicle, VehicleVisit
from apps.dealers.models import Dealer, DealerLocation
from apps.leads.models import Lead, NotifyMeRequest
from apps.platform.models import AuditLog, ContentReport, DealerSanction
from apps.vehicles.models import Vehicle


class RemainingRoadmapTests(TestCase):
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
        self.platform_user = StaffUser.objects.create_user(
            email="admin@example.com",
            password="strong-pass-123",
            name="Platform Admin",
            role=StaffUser.Role.OWNER,
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
        start = self.client.post(
            "/v1/buyers/sign-in/start",
            {"phone": "+2348090000000"},
            format="json",
        )
        self.assertEqual(start.status_code, 201)
        code = BuyerOtp.objects.get(phone="+2348090000000").code
        verify = self.client.post(
            "/v1/buyers/sign-in/verify",
            {"phone": "+2348090000000", "code": code},
            format="json",
        )
        self.assertEqual(verify.status_code, 200)
        return verify.json()["data"]["token"]

    def test_public_feed_leads_and_notify_me(self):
        feed_response = self.client.get("/v1/feed")
        self.assertEqual(feed_response.status_code, 200)
        self.assertEqual(feed_response.json()["data"]["count"], 1)

        detail_response = self.client.get(f"/v1/feed/vehicles/{self.vehicle.id}")
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(detail_response.json()["data"]["dealer"]["slug"], self.dealer.slug)

        dealer_response = self.client.get(f"/v1/feed/dealers/{self.dealer.slug}")
        self.assertEqual(dealer_response.status_code, 200)
        self.assertEqual(dealer_response.json()["data"]["name"], self.dealer.name)

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
        self.assertEqual(Lead.objects.count(), 1)

        notify_response = self.client.post(
            "/v1/notify-me",
            {"phone": "+2348070000000", "make": "Toyota", "model": "Camry"},
            format="json",
        )
        self.assertEqual(notify_response.status_code, 201)
        self.assertEqual(NotifyMeRequest.objects.count(), 1)

    def test_buyer_saved_vehicle_and_visit_tracking(self):
        token = self.buyer_token()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        save_response = self.client.post(f"/v1/buyers/saved/{self.vehicle.id}")
        self.assertEqual(save_response.status_code, 201)
        self.assertEqual(SavedVehicle.objects.count(), 1)

        detail_response = self.client.get(f"/v1/feed/vehicles/{self.vehicle.id}")
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(VehicleVisit.objects.count(), 1)

        saved_response = self.client.get("/v1/buyers/saved")
        self.assertEqual(saved_response.status_code, 200)
        self.assertEqual(saved_response.json()["data"]["count"], 1)

    def test_booking_summary_verify_and_dealer_appointment(self):
        summary_response = self.client.post(
            "/v1/bookings/summaries",
            {"vehicleId": str(self.vehicle.id)},
            format="json",
        )
        self.assertEqual(summary_response.status_code, 200)
        self.assertEqual(summary_response.json()["data"]["vehicleId"], str(self.vehicle.id))

        unauthenticated_response = self.client.post(
            "/v1/bookings",
            {
                "vehicleId": str(self.vehicle.id),
                "scheduledAt": (timezone.now() + timedelta(days=2)).isoformat(),
            },
            format="json",
        )
        self.assertEqual(unauthenticated_response.status_code, 401)

        token = self.buyer_token()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        booking_response = self.client.post(
            "/v1/bookings",
            {
                "vehicleId": str(self.vehicle.id),
                "scheduledAt": (timezone.now() + timedelta(days=2)).isoformat(),
            },
            format="json",
        )
        self.assertEqual(booking_response.status_code, 201)
        booking = Booking.objects.get()
        self.assertEqual(booking.status, Booking.Status.CONFIRMED)
        self.assertEqual(booking.buyer.phone, "+2348090000000")
        self.assertEqual(Appointment.objects.count(), 1)

        self.client.credentials()
        self.client.force_authenticate(self.staff)
        appointment_response = self.client.get("/v1/appointments")
        self.assertEqual(appointment_response.status_code, 200)
        self.assertEqual(appointment_response.json()["data"]["count"], 1)

    def test_billing_and_listing_limits(self):
        plan = BillingPlan.objects.create(
            id="free",
            name="Free",
            price_ngn=0,
            listing_limit=1,
        )
        self.dealer.plan_id = plan.id
        self.dealer.save(update_fields=["plan_id"])

        plans_response = self.client.get("/v1/billing/plans")
        self.assertEqual(plans_response.status_code, 200)
        self.assertEqual(plans_response.json()["data"]["count"], 1)

        self.client.force_authenticate(self.staff)
        summary_response = self.client.get("/v1/billing/summary")
        self.assertEqual(summary_response.status_code, 200)
        self.assertEqual(summary_response.json()["data"]["listingLimit"], 1)

        checkout_response = self.client.post(
            "/v1/billing/checkout",
            {"planId": plan.id},
            format="json",
        )
        self.assertEqual(checkout_response.status_code, 201)

        blocked_response = self.client.post(
            "/v1/vehicles",
            {
                "slug": "honda-accord-2021",
                "make": "Honda",
                "model": "Accord",
                "year": 2021,
                "trim": "EX",
                "priceNgn": 17000000,
                "mileageKm": 30000,
                "transmission": "automatic",
                "fuel": "petrol",
                "colour": "Blue",
                "bodyType": "sedan",
                "drivetrain": "fwd",
                "conditionGrade": "good",
                "locationId": str(self.location.id),
            },
            format="json",
        )
        self.assertEqual(blocked_response.status_code, 403)

    def test_platform_trust_resources_and_dealer_verification(self):
        self.client.force_authenticate(self.platform_user)
        report_response = self.client.post(
            "/v1/platform/reports",
            {"vehicleId": str(self.vehicle.id), "reason": "Bad listing"},
            format="json",
        )
        self.assertEqual(report_response.status_code, 201)
        report = ContentReport.objects.get()

        resolve_response = self.client.patch(f"/v1/platform/reports/{report.id}/resolve")
        self.assertEqual(resolve_response.status_code, 200)

        sanction_response = self.client.post(
            "/v1/platform/sanctions",
            {"dealerId": str(self.dealer.id), "reason": "Policy violation"},
            format="json",
        )
        self.assertEqual(sanction_response.status_code, 201)
        self.assertEqual(DealerSanction.objects.count(), 1)

        verify_response = self.client.patch(
            f"/v1/dealers/{self.dealer.id}/verification/approve",
        )
        self.assertEqual(verify_response.status_code, 200)
        self.dealer.refresh_from_db()
        self.assertTrue(self.dealer.verified_badge)
        self.assertGreaterEqual(AuditLog.objects.count(), 3)
