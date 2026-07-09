from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import StaffUser
from apps.dealers.models import Dealer, DealerLocation
from apps.platform.models import DealerMessage, DealerMessageThread
from apps.vehicles.models import Vehicle
from apps.leads.models import Lead


class DealerLocationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.dealer = Dealer.objects.create(
            slug="dealer-location-tests",
            name="Dealer Location Tests",
            legal_name="Dealer Location Tests Ltd",
            area="Wuse",
            phone="+2348000000001",
        )
        self.location = DealerLocation.objects.create(
            dealer=self.dealer,
            name="Main Stand",
            area="Wuse",
            district_slug="wuse",
            address="Old address",
            is_primary=True,
        )
        self.staff = StaffUser.objects.create_user(
            email="dealer-locations@test.local",
            password="password123",
            name="Dealer Owner",
            dealer=self.dealer,
            role=StaffUser.Role.OWNER,
            preferred_location=self.location,
        )
        self.client.force_authenticate(self.staff)

    def test_location_detail_edits_are_submitted_as_pending_changes(self):
        response = self.client.patch(
            f"/v1/dealers/me/locations/{self.location.id}",
            {"name": "Updated Stand", "address": "New address", "districtSlug": "Wuse II"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.location.refresh_from_db()
        self.assertEqual(self.location.name, "Main Stand")
        self.assertEqual(self.location.address, "Old address")
        self.assertEqual(
            self.location.pending_changes,
            {
                "name": "Updated Stand",
                "area": "Wuse II",
                "district_slug": "wuse-ii",
                "address": "New address",
            },
        )
        self.assertIsNotNone(self.location.pending_changes_submitted_at)

    def test_dealer_context_location_listing_count_uses_real_vehicle_count(self):
        Vehicle.objects.create(
            dealer=self.dealer,
            location=self.location,
            slug="toyota-corolla-2021",
            make="Toyota",
            model="Corolla",
            year=2021,
            trim="LE",
            price_ngn=12000000,
            mileage_km=25000,
            transmission=Vehicle.Transmission.AUTOMATIC,
            fuel=Vehicle.Fuel.PETROL,
            colour="Silver",
            body_type=Vehicle.BodyType.SEDAN,
            drivetrain=Vehicle.Drivetrain.FWD,
            condition_grade=Vehicle.ConditionGrade.GOOD,
        )

        response = self.client.get("/v1/dealers/me/context")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["locations"][0]["listingCount"], 1)

    def test_dealer_insights_returns_sales_sources_and_inventory_groups(self):
        Vehicle.objects.create(
            dealer=self.dealer,
            location=self.location,
            slug="sold-corolla",
            make="Toyota",
            model="Corolla",
            year=2020,
            trim="LE",
            price_ngn=10000000,
            mileage_km=25000,
            transmission=Vehicle.Transmission.AUTOMATIC,
            fuel=Vehicle.Fuel.PETROL,
            colour="Silver",
            body_type=Vehicle.BodyType.SEDAN,
            drivetrain=Vehicle.Drivetrain.FWD,
            condition_grade=Vehicle.ConditionGrade.GOOD,
            status=Vehicle.Status.SOLD,
        )
        Vehicle.objects.create(
            dealer=self.dealer,
            location=self.location,
            slug="available-corolla",
            make="Toyota",
            model="Corolla",
            year=2021,
            trim="LE",
            price_ngn=12000000,
            mileage_km=22000,
            transmission=Vehicle.Transmission.AUTOMATIC,
            fuel=Vehicle.Fuel.PETROL,
            colour="Black",
            body_type=Vehicle.BodyType.SEDAN,
            drivetrain=Vehicle.Drivetrain.FWD,
            condition_grade=Vehicle.ConditionGrade.GOOD,
        )
        Lead.objects.create(dealer=self.dealer, location=self.location, name="Ada", phone="+234809", source=Lead.Source.WALK_IN)
        Lead.objects.create(dealer=self.dealer, location=self.location, name="Tola", phone="+234808", source=Lead.Source.NOTIFY_ME)

        response = self.client.get("/v1/dealers/me/insights")

        self.assertEqual(response.status_code, 200)
        payload = response.json()["data"]
        self.assertEqual(payload["soldValueNgn"], 10000000)
        self.assertEqual(payload["soldCount"], 1)
        self.assertEqual(payload["carsByMakeModel"][0]["count"], 1)
        self.assertEqual({item["source"] for item in payload["leadSources"]}, {"walk_in", "notify_me"})

    def test_dealer_can_list_and_reply_to_platform_message_threads(self):
        platform_user = StaffUser.objects.create_user(
            email="platform-message@test.local",
            password="password123",
            name="Platform Admin",
            is_staff=True,
        )
        thread = DealerMessageThread.objects.create(
            dealer=self.dealer,
            subject="Verification update",
            created_by=platform_user,
        )
        DealerMessage.objects.create(
            thread=thread,
            sender=platform_user,
            sender_type=DealerMessage.SenderType.PLATFORM,
            body="Please upload the missing premise image.",
        )

        list_response = self.client.get("/v1/dealers/me/messages")
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.json()["data"][0]["subject"], "Verification update")

        reply_response = self.client.post(
            "/v1/dealers/me/messages",
            {"threadId": str(thread.id), "body": "I have uploaded it now."},
            format="json",
        )

        self.assertEqual(reply_response.status_code, 201)
        self.assertEqual(reply_response.json()["data"]["messages"][-1]["senderType"], "dealer")
        self.assertEqual(thread.messages.count(), 2)
