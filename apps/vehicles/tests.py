from django.contrib.auth.models import Group
from django.urls import resolve
from django.urls.exceptions import Resolver404
from rest_framework.test import APIClient
from django.test import TestCase

from apps.accounts.models import StaffUser
from apps.dealers.models import Dealer, DealerLocation

from .models import Vehicle


class UnifiedVehicleCatalogTests(TestCase):
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
        self.user = StaffUser.objects.create_user(
            email="owner@example.com",
            password="strong-pass-123",
            name="Owner User",
            role=StaffUser.Role.OWNER,
            dealer=self.dealer,
            preferred_location=self.location,
        )
        self.other_dealer = Dealer.objects.create(
            slug="other-motors",
            name="Other Motors",
            legal_name="Other Motors Limited",
            area="Garki",
            phone="+2348022222222",
        )
        self.other_location = DealerLocation.objects.create(
            dealer=self.other_dealer,
            name="Other Stand",
            area="Garki",
            district_slug="garki",
            is_primary=True,
        )
        self.reviewer = StaffUser.objects.create_user(
            email="reviewer@example.com",
            password="strong-pass-123",
            name="Reviewer User",
            role=StaffUser.Role.OWNER,
            is_staff=True,
        )
        Group.objects.create(name="listing_reviewers")

    def vehicle_payload(self, **overrides):
        payload = {
            "slug": "toyota-camry-2020-xle",
            "make": "Toyota",
            "model": "Camry",
            "year": 2020,
            "trim": "XLE",
            "priceNgn": 15000000,
            "mileageKm": 45000,
            "transmission": "automatic",
            "fuel": "petrol",
            "colour": "Black",
            "bodyType": "sedan",
            "drivetrain": "fwd",
            "conditionGrade": "good",
            "locationId": str(self.location.id),
        }
        payload.update(overrides)
        return payload

    def authenticate(self, user=None):
        self.client.force_authenticate(user=user or self.user)

    def create_vehicle(self, dealer=None, location=None, **overrides):
        dealer = dealer or self.dealer
        location = location or self.location
        values = {
            "dealer": dealer,
            "location": location,
            "slug": overrides.pop("slug", "toyota-camry-2020-xle"),
            "make": overrides.pop("make", "Toyota"),
            "model": overrides.pop("model", "Camry"),
            "year": overrides.pop("year", 2020),
            "trim": overrides.pop("trim", "XLE"),
            "price_ngn": overrides.pop("price_ngn", 15000000),
            "mileage_km": overrides.pop("mileage_km", 45000),
            "transmission": overrides.pop("transmission", "automatic"),
            "fuel": overrides.pop("fuel", "petrol"),
            "colour": overrides.pop("colour", "Black"),
            "body_type": overrides.pop("body_type", "sedan"),
            "drivetrain": overrides.pop("drivetrain", "fwd"),
            "condition_grade": overrides.pop("condition_grade", "good"),
        }
        values.update(overrides)
        return Vehicle.objects.create(**values)

    def test_catalog_makes_and_models(self):
        makes_response = self.client.get("/v1/catalog/makes")
        self.assertEqual(makes_response.status_code, 200)
        makes_data = makes_response.json()["data"]
        self.assertEqual(makes_data["source"], "local")
        self.assertTrue(any(item["name"] == "Toyota" for item in makes_data["makes"]))

        models_response = self.client.get(
            "/v1/catalog/models",
            {"make": "toyota", "year": "2020"},
        )
        self.assertEqual(models_response.status_code, 200)
        models_data = models_response.json()["data"]
        self.assertEqual(models_data["make"], "Toyota")
        self.assertEqual(models_data["year"], 2020)
        self.assertTrue(any(item["name"] == "Camry" for item in models_data["models"]))

    def test_dealer_can_create_list_retrieve_and_update_own_vehicle(self):
        self.authenticate()

        create_response = self.client.post(
            "/v1/vehicles",
            self.vehicle_payload(),
            format="json",
        )
        self.assertEqual(create_response.status_code, 201)
        vehicle_id = create_response.json()["data"]["id"]

        list_response = self.client.get("/v1/vehicles")
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(len(list_response.json()["data"]["results"]), 1)

        detail_response = self.client.get(f"/v1/vehicles/{vehicle_id}")
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(detail_response.json()["data"]["make"], "Toyota")

        update_response = self.client.patch(
            f"/v1/vehicles/{vehicle_id}",
            {"priceNgn": 14500000, "notes": "Fresh import"},
            format="json",
        )
        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(update_response.json()["data"]["priceNgn"], 14500000)

    def test_dealer_vehicle_queries_are_tenant_scoped(self):
        own_vehicle = self.create_vehicle()
        other_vehicle = self.create_vehicle(
            dealer=self.other_dealer,
            location=self.other_location,
            slug="honda-accord-other",
            make="Honda",
            model="Accord",
        )
        self.authenticate()

        list_response = self.client.get("/v1/vehicles")
        ids = {item["id"] for item in list_response.json()["data"]["results"]}
        self.assertIn(str(own_vehicle.id), ids)
        self.assertNotIn(str(other_vehicle.id), ids)

        detail_response = self.client.get(f"/v1/vehicles/{other_vehicle.id}")
        self.assertEqual(detail_response.status_code, 404)

    def test_status_transition_requires_attestation_for_available(self):
        vehicle = self.create_vehicle()
        self.authenticate()

        bad_response = self.client.patch(
            f"/v1/vehicles/{vehicle.id}/status",
            {"status": "available"},
            format="json",
        )
        self.assertEqual(bad_response.status_code, 400)

        ok_response = self.client.patch(
            f"/v1/vehicles/{vehicle.id}/status",
            {"status": "available", "attestationAccepted": True},
            format="json",
        )
        self.assertEqual(ok_response.status_code, 200)
        vehicle.refresh_from_db()
        self.assertEqual(vehicle.status, Vehicle.Status.AVAILABLE)
        self.assertEqual(
            vehicle.listing_verification_status,
            Vehicle.ListingVerificationStatus.PENDING_REVIEW,
        )

    def test_refresh_updates_vehicle_refresh_timestamp(self):
        vehicle = self.create_vehicle()
        self.authenticate()

        response = self.client.post(f"/v1/vehicles/{vehicle.id}/refresh")

        self.assertEqual(response.status_code, 200)
        vehicle.refresh_from_db()
        self.assertIsNotNone(vehicle.refreshed_at)

    def test_reviewer_can_access_all_vehicles_and_review_actions(self):
        own_vehicle = self.create_vehicle(
            status=Vehicle.Status.AVAILABLE,
            listing_verification_status=Vehicle.ListingVerificationStatus.PENDING_REVIEW,
        )
        other_vehicle = self.create_vehicle(
            dealer=self.other_dealer,
            location=self.other_location,
            slug="honda-accord-other",
            make="Honda",
            model="Accord",
            status=Vehicle.Status.AVAILABLE,
            listing_verification_status=Vehicle.ListingVerificationStatus.PENDING_REVIEW,
        )
        self.authenticate(self.reviewer)

        list_response = self.client.get("/v1/vehicles")
        ids = {item["id"] for item in list_response.json()["data"]["results"]}
        self.assertIn(str(own_vehicle.id), ids)
        self.assertIn(str(other_vehicle.id), ids)

        approve_response = self.client.patch(
            f"/v1/vehicles/{own_vehicle.id}/review/approve",
            {},
            format="json",
        )
        self.assertEqual(approve_response.status_code, 200)
        own_vehicle.refresh_from_db()
        self.assertEqual(
            own_vehicle.listing_verification_status,
            Vehicle.ListingVerificationStatus.APPROVED,
        )
        self.assertTrue(own_vehicle.feed_ready)

        reject_response = self.client.patch(
            f"/v1/vehicles/{other_vehicle.id}/review/reject",
            {"reason": "Incomplete documents"},
            format="json",
        )
        self.assertEqual(reject_response.status_code, 200)
        other_vehicle.refresh_from_db()
        self.assertEqual(
            other_vehicle.listing_verification_status,
            Vehicle.ListingVerificationStatus.REJECTED,
        )
        self.assertEqual(other_vehicle.listing_rejected_reason, "Incomplete documents")

        remove_response = self.client.patch(
            f"/v1/vehicles/{own_vehicle.id}/review/remove-from-feed",
            {"reason": "Needs updated pricing"},
            format="json",
        )
        self.assertEqual(remove_response.status_code, 200)
        own_vehicle.refresh_from_db()
        self.assertFalse(own_vehicle.feed_ready)
        self.assertEqual(own_vehicle.listing_rejected_reason, "Needs updated pricing")

    def test_dealer_cannot_run_review_actions(self):
        vehicle = self.create_vehicle(
            status=Vehicle.Status.AVAILABLE,
            listing_verification_status=Vehicle.ListingVerificationStatus.PENDING_REVIEW,
        )
        self.authenticate()

        response = self.client.patch(f"/v1/vehicles/{vehicle.id}/review/approve")

        self.assertEqual(response.status_code, 403)

    def test_platform_listing_duplicate_routes_are_not_registered(self):
        with self.assertRaises(Resolver404):
            resolve("/v1/platform/listings/review-queue")

    def test_vehicle_media_upload_session_complete_and_cover_selection(self):
        vehicle = self.create_vehicle()
        self.authenticate()

        session_response = self.client.post(
            f"/v1/vehicles/{vehicle.id}/media/upload-session",
            {
                "items": [
                    {
                        "kind": "photo",
                        "contentType": "image/jpeg",
                        "fileName": "front.jpg",
                        "fileSize": 1200,
                    },
                    {
                        "kind": "video",
                        "contentType": "video/mp4",
                        "fileName": "walkaround.mp4",
                        "fileSize": 5000,
                    },
                ]
            },
            format="json",
        )

        self.assertEqual(session_response.status_code, 201)
        items = session_response.json()["data"]["items"]
        self.assertEqual(len(items), 2)
        self.assertIn("uploadUrl", items[0])
        self.assertIn("publicUrl", items[0])
        self.assertTrue(str(vehicle.id) in items[0]["publicUrl"])

        media_id = items[0]["mediaId"]
        complete_response = self.client.post(
            f"/v1/vehicles/{vehicle.id}/media/{media_id}/complete",
            {"thumbnailUrl": items[0]["publicUrl"], "status": "ready"},
            format="json",
        )

        self.assertEqual(complete_response.status_code, 200)
        data = complete_response.json()["data"]
        self.assertEqual(data["coverMedia"]["id"], media_id)
        self.assertEqual(len(data["media"]), 2)
        self.assertEqual(data["media"][0]["status"], "ready")

    def test_vehicle_cover_media_can_be_updated_by_vehicle_patch(self):
        vehicle = self.create_vehicle()
        first = vehicle.media_items.create(
            kind="photo",
            url="https://example.com/front.jpg",
            thumbnail_url="https://example.com/front-thumb.jpg",
            content_type="image/jpeg",
            file_name="front.jpg",
            s3_key="vehicle-media/front.jpg",
            status="ready",
            sort_order=1,
        )
        second = vehicle.media_items.create(
            kind="photo",
            url="https://example.com/rear.jpg",
            thumbnail_url="https://example.com/rear-thumb.jpg",
            content_type="image/jpeg",
            file_name="rear.jpg",
            s3_key="vehicle-media/rear.jpg",
            status="ready",
            sort_order=2,
        )
        vehicle.cover_media = first
        vehicle.save(update_fields=["cover_media", "updated_at"])
        self.authenticate()

        response = self.client.patch(
            f"/v1/vehicles/{vehicle.id}",
            {"coverMediaId": str(second.id)},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["coverMedia"]["id"], str(second.id))

    def test_vehicle_media_upload_is_tenant_scoped(self):
        other_vehicle = self.create_vehicle(
            dealer=self.other_dealer,
            location=self.other_location,
            slug="honda-accord-other",
            make="Honda",
            model="Accord",
        )
        self.authenticate()

        response = self.client.post(
            f"/v1/vehicles/{other_vehicle.id}/media/upload-session",
            {
                "items": [
                    {
                        "kind": "photo",
                        "contentType": "image/jpeg",
                        "fileName": "front.jpg",
                    }
                ]
            },
            format="json",
        )

        self.assertEqual(response.status_code, 404)
