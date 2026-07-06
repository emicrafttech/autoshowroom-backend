from django.utils import timezone

from rest_framework.test import APIClient

from apps.buyers.auth import create_buyer_token
from apps.buyers.models import BlockedDealer, Buyer, PriceAlert
from apps.buyers.tests import BuyerChatTests
from apps.vehicles.models import Vehicle
from apps.vehicles.price_history import record_vehicle_price


class PriceAlertTests(BuyerChatTests):
    def test_price_alerts_list_create_and_toggle(self):
        list_response = self.client.get("/v1/buyers/price-alerts")
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.json()["data"]["activeCount"], 0)

        create_response = self.client.post(
            "/v1/buyers/price-alerts",
            {
                "bodyType": "suv",
                "maxPriceNgn": 40000000,
                "area": "Abuja",
            },
            format="json",
        )
        self.assertEqual(create_response.status_code, 201)
        data = create_response.json()["data"]
        self.assertEqual(data["activeCount"], 1)
        self.assertEqual(len(data["alerts"]), 1)
        alert_id = data["alerts"][0]["id"]
        self.assertIn("cars match now", data["alerts"][0]["subtitle"])

        toggle_response = self.client.patch(
            f"/v1/buyers/price-alerts/{alert_id}",
            {"active": False},
            format="json",
        )
        self.assertEqual(toggle_response.status_code, 200)
        self.assertEqual(toggle_response.json()["data"]["activeCount"], 0)

        delete_response = self.client.delete(f"/v1/buyers/price-alerts/{alert_id}")
        self.assertEqual(delete_response.status_code, 200)
        self.assertEqual(delete_response.json()["data"]["activeCount"], 0)
        self.assertEqual(len(delete_response.json()["data"]["alerts"]), 0)
        self.assertEqual(PriceAlert.objects.count(), 0)

    def test_new_match_uses_price_history(self):
        alert = PriceAlert.objects.create(
            buyer=self.buyer,
            title="Toyota deals",
            make="Toyota",
            active=True,
        )
        record_vehicle_price(self.vehicle, 17000000)
        self.vehicle.price_ngn = 15000000
        self.vehicle.save(update_fields=["price_ngn", "updated_at"])
        record_vehicle_price(self.vehicle, 15000000)

        response = self.client.get("/v1/buyers/price-alerts")
        self.assertEqual(response.status_code, 200)
        matches = response.json()["data"]["newMatches"]
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["matchedAlertName"], alert.title)
        self.assertEqual(matches[0]["previousPriceNgn"], 17000000)
        self.assertEqual(matches[0]["currentPriceNgn"], 15000000)
        self.assertEqual(matches[0]["matchKind"], "price_drop")

    def test_create_alert_with_title_price_range_and_push_notify(self):
        create_response = self.client.post(
            "/v1/buyers/price-alerts",
            {
                "title": "SUV under ₦40M",
                "bodyType": "suv",
                "minPriceNgn": 10000000,
                "maxPriceNgn": 40000000,
                "area": "Abuja",
                "pushNotify": True,
            },
            format="json",
        )
        self.assertEqual(create_response.status_code, 201)
        data = create_response.json()["data"]
        self.assertEqual(data["alerts"][0]["title"], "SUV under ₦40M")
        alert = PriceAlert.objects.get()
        self.assertEqual(alert.body_type, "suv")
        self.assertEqual(alert.min_price_ngn, 10000000)
        self.assertEqual(alert.max_price_ngn, 40000000)
        self.assertTrue(alert.push_notify)

    def test_blocked_dealers_crud(self):
        create_response = self.client.post(
            "/v1/buyers/blocked-dealers",
            {"dealerSlug": self.dealer.slug},
            format="json",
        )
        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(BlockedDealer.objects.count(), 1)

        list_response = self.client.get("/v1/buyers/blocked-dealers")
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(len(list_response.json()["data"]), 1)

        delete_response = self.client.delete(
            f"/v1/buyers/blocked-dealers/{self.dealer.slug}",
        )
        self.assertEqual(delete_response.status_code, 204)
        self.assertEqual(BlockedDealer.objects.count(), 0)
