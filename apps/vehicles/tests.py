from django.contrib.auth.models import Group
from django.urls import resolve
from django.urls.exceptions import Resolver404
from django.utils import timezone
from rest_framework.test import APIClient
from django.test import TestCase
from unittest.mock import patch

from apps.accounts.models import StaffUser
from apps.dealers.models import Dealer, DealerLocation
from apps.notifications.models import DealerNotification
from apps.platform.models import AuditLog, PlatformRole

from .models import Vehicle, VehicleReviewIssue


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
            platform_role=PlatformRole.objects.create(
                name="Listing reviewer",
                capabilities=["listing_review.read", "listing_review.write"],
            ),
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

    def test_dealer_can_create_vehicle_with_listing_trust_fields(self):
        self.authenticate()

        response = self.client.post(
            "/v1/vehicles",
            self.vehicle_payload(
                chassisNumber="CHS123",
                yearOfManufacture=2020,
                engineCapacityCc=2500,
                registrationPlate="ABC123DE",
                registrationState="FCT",
                registrationLga="Abuja Municipal",
                customsDutyStatus="cleared",
                customsReference="SGD123",
                bodyHistory="first_body",
                papersStatus="complete",
                dutyPaidClaim="dealer_claimed",
                listingTrust="Full service history and customs duty available.",
            ),
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        vehicle = Vehicle.objects.get(id=response.json()["data"]["id"])
        self.assertEqual(vehicle.listing_trust, "Full service history and customs duty available.")
        self.assertEqual(vehicle.chassis_number, "CHS123")
        self.assertEqual(vehicle.customs_duty_status, Vehicle.CustomsDutyStatus.CLEARED)

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
        self.assertEqual(list_response.json()["data"]["results"][0]["dealerName"], "Prime Motors")

        detail_response = self.client.get(f"/v1/vehicles/{vehicle_id}")
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(detail_response.json()["data"]["make"], "Toyota")
        self.assertEqual(detail_response.json()["data"]["dealerName"], "Prime Motors")

        update_response = self.client.patch(
            f"/v1/vehicles/{vehicle_id}",
            {"priceNgn": 14500000, "notes": "Fresh import"},
            format="json",
        )
        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(update_response.json()["data"]["priceNgn"], 14500000)

    def test_auto_generated_vehicle_slugs_are_unique_per_dealer(self):
        self.authenticate()
        payload = self.vehicle_payload()
        payload.pop("slug")

        first_response = self.client.post("/v1/vehicles", payload, format="json")
        second_response = self.client.post("/v1/vehicles", payload, format="json")

        self.assertEqual(first_response.status_code, 201)
        self.assertEqual(second_response.status_code, 201)
        self.assertNotEqual(
            first_response.json()["data"]["slug"],
            second_response.json()["data"]["slug"],
        )

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

    def test_dealer_can_delete_own_vehicle(self):
        vehicle = self.create_vehicle()
        vehicle.media_items.create(
            kind="photo",
            url="https://example.com/front.jpg",
            content_type="image/jpeg",
            file_name="front.jpg",
            s3_key="vehicle-media/front.jpg",
            status="ready",
            sort_order=1,
        )
        self.authenticate()

        with patch("apps.vehicles.views.delete_media_objects") as delete_media_objects:
            response = self.client.delete(f"/v1/vehicles/{vehicle.id}")

        self.assertEqual(response.status_code, 204)
        delete_media_objects.assert_called_once_with(["vehicle-media/front.jpg"])
        self.assertFalse(Vehicle.objects.filter(id=vehicle.id).exists())

    def test_dealer_cannot_delete_other_dealer_vehicle(self):
        vehicle = self.create_vehicle(
            dealer=self.other_dealer,
            location=self.other_location,
            slug="honda-accord-other",
            make="Honda",
            model="Accord",
        )
        self.authenticate()

        response = self.client.delete(f"/v1/vehicles/{vehicle.id}")

        self.assertEqual(response.status_code, 404)
        self.assertTrue(Vehicle.objects.filter(id=vehicle.id).exists())

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

    def test_relist_after_sold_restores_feed_without_review(self):
        vehicle = self.create_vehicle(
            status=Vehicle.Status.AVAILABLE,
            listing_verification_status=Vehicle.ListingVerificationStatus.APPROVED,
            feed_ready=True,
            published_at=timezone.now(),
        )
        self.authenticate()

        sold_response = self.client.patch(
            f"/v1/vehicles/{vehicle.id}/status",
            {"status": "sold"},
            format="json",
        )
        self.assertEqual(sold_response.status_code, 200)
        vehicle.refresh_from_db()
        self.assertEqual(vehicle.status, Vehicle.Status.SOLD)
        self.assertFalse(vehicle.feed_ready)

        available_response = self.client.patch(
            f"/v1/vehicles/{vehicle.id}/status",
            {"status": "available", "attestationAccepted": True},
            format="json",
        )
        self.assertEqual(available_response.status_code, 200)
        vehicle.refresh_from_db()
        self.assertEqual(vehicle.status, Vehicle.Status.AVAILABLE)
        self.assertEqual(
            vehicle.listing_verification_status,
            Vehicle.ListingVerificationStatus.APPROVED,
        )
        self.assertTrue(vehicle.feed_ready)
        self.assertIsNotNone(vehicle.published_at)

    def test_relist_after_reserved_restores_feed_without_review(self):
        vehicle = self.create_vehicle(
            status=Vehicle.Status.RESERVED,
            listing_verification_status=Vehicle.ListingVerificationStatus.APPROVED,
            feed_ready=False,
            published_at=timezone.now(),
        )
        self.authenticate()

        available_response = self.client.patch(
            f"/v1/vehicles/{vehicle.id}/status",
            {"status": "available", "attestationAccepted": True},
            format="json",
        )
        self.assertEqual(available_response.status_code, 200)
        vehicle.refresh_from_db()
        self.assertEqual(vehicle.status, Vehicle.Status.AVAILABLE)
        self.assertEqual(
            vehicle.listing_verification_status,
            Vehicle.ListingVerificationStatus.APPROVED,
        )
        self.assertTrue(vehicle.feed_ready)

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
        approve_audit = AuditLog.objects.get(
            action="vehicle.review.approved",
            target_id=str(own_vehicle.id),
        )
        self.assertEqual(approve_audit.actor, self.reviewer)
        self.assertEqual(approve_audit.metadata["feedReady"], True)

        with patch("apps.notifications.services.send_listing_review_issue_email.delay"):
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
        reject_audit = AuditLog.objects.get(
            action="vehicle.review.rejected",
            target_id=str(other_vehicle.id),
        )
        self.assertEqual(reject_audit.actor, self.reviewer)
        self.assertEqual(reject_audit.metadata["reason"], "Incomplete documents")
        self.assertEqual(reject_audit.metadata["issueCount"], 1)

        with patch("apps.notifications.services.send_listing_review_issue_email.delay") as remove_email_task:
            remove_response = self.client.patch(
                f"/v1/vehicles/{own_vehicle.id}/review/remove-from-feed",
                {"reason": "Needs updated pricing"},
                format="json",
            )
        self.assertEqual(remove_response.status_code, 200)
        own_vehicle.refresh_from_db()
        self.assertFalse(own_vehicle.feed_ready)
        self.assertEqual(own_vehicle.listing_rejected_reason, "Needs updated pricing")
        remove_issue = VehicleReviewIssue.objects.get(vehicle=own_vehicle)
        self.assertEqual(remove_issue.category, VehicleReviewIssue.Category.COMPLIANCE)
        self.assertEqual(remove_issue.message, "Needs updated pricing")
        self.assertEqual(DealerNotification.objects.filter(review_issue=remove_issue).count(), 1)
        remove_email_task.assert_called_once()
        remove_audit = AuditLog.objects.get(
            action="vehicle.feed.removed",
            target_id=str(own_vehicle.id),
        )
        self.assertEqual(remove_audit.actor, self.reviewer)
        self.assertEqual(remove_audit.metadata["reason"], "Needs updated pricing")
        self.assertEqual(remove_audit.metadata["issueCount"], 1)

        own_vehicle.listing_verification_status = Vehicle.ListingVerificationStatus.APPROVED
        own_vehicle.save(update_fields=["listing_verification_status", "updated_at"])
        restore_response = self.client.patch(
            f"/v1/vehicles/{own_vehicle.id}/review/restore-to-feed",
            {},
            format="json",
        )
        self.assertEqual(restore_response.status_code, 200)
        own_vehicle.refresh_from_db()
        self.assertTrue(own_vehicle.feed_ready)
        self.assertIsNotNone(own_vehicle.published_at)
        self.assertIsNone(own_vehicle.listing_rejected_reason)
        remove_issue.refresh_from_db()
        self.assertEqual(remove_issue.status, VehicleReviewIssue.Status.APPROVED)
        restore_audit = AuditLog.objects.get(
            action="vehicle.feed.restored",
            target_id=str(own_vehicle.id),
        )
        self.assertEqual(restore_audit.actor, self.reviewer)

    def test_dealer_cannot_run_review_actions(self):
        vehicle = self.create_vehicle(
            status=Vehicle.Status.AVAILABLE,
            listing_verification_status=Vehicle.ListingVerificationStatus.PENDING_REVIEW,
        )
        self.authenticate()

        response = self.client.patch(f"/v1/vehicles/{vehicle.id}/review/approve")

        self.assertEqual(response.status_code, 403)

    def test_reviewer_creates_review_issues_notifications_and_email_jobs(self):
        vehicle = self.create_vehicle(
            status=Vehicle.Status.AVAILABLE,
            listing_verification_status=Vehicle.ListingVerificationStatus.PENDING_REVIEW,
        )
        self.authenticate(self.reviewer)

        with patch("apps.notifications.services.send_listing_review_issue_email.delay") as email_task:
            response = self.client.patch(
                f"/v1/vehicles/{vehicle.id}/review/reject",
                {
                    "reason": "Media needs work",
                    "issues": [
                        {
                            "category": "media",
                            "message": "Add clear walkaround videos of the engine bay.",
                        },
                        {
                            "category": "details",
                            "message": "Confirm the VIN matches the documents.",
                        },
                    ],
                },
                format="json",
            )

        self.assertEqual(response.status_code, 200)
        vehicle.refresh_from_db()
        self.assertEqual(
            vehicle.listing_verification_status,
            Vehicle.ListingVerificationStatus.REJECTED,
        )
        self.assertEqual(VehicleReviewIssue.objects.filter(vehicle=vehicle).count(), 2)
        self.assertEqual(DealerNotification.objects.filter(vehicle=vehicle).count(), 2)
        self.assertEqual(email_task.call_count, 2)

    def test_reviewer_cannot_approve_while_open_issues_remain(self):
        vehicle = self.create_vehicle(
            status=Vehicle.Status.AVAILABLE,
            listing_verification_status=Vehicle.ListingVerificationStatus.PENDING_REVIEW,
        )
        VehicleReviewIssue.objects.create(
            vehicle=vehicle,
            reviewer=self.reviewer,
            category=VehicleReviewIssue.Category.MEDIA,
            message="Add more videos.",
        )
        self.authenticate(self.reviewer)

        response = self.client.patch(
            f"/v1/vehicles/{vehicle.id}/review/approve",
            {},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        vehicle.refresh_from_db()
        self.assertEqual(
            vehicle.listing_verification_status,
            Vehicle.ListingVerificationStatus.PENDING_REVIEW,
        )

    def test_dealer_resolves_issue_and_listing_returns_to_pending_review(self):
        vehicle = self.create_vehicle(
            status=Vehicle.Status.AVAILABLE,
            listing_verification_status=Vehicle.ListingVerificationStatus.REJECTED,
            listing_rejected_reason="Fix photos",
        )
        issue = VehicleReviewIssue.objects.create(
            vehicle=vehicle,
            reviewer=self.reviewer,
            category=VehicleReviewIssue.Category.MEDIA,
            message="Add clean dashboard photos.",
        )
        self.authenticate()

        update_response = self.client.patch(
            f"/v1/vehicles/{vehicle.id}",
            {"notes": "Added clearer dashboard media and updated description."},
            format="json",
        )
        resolve_response = self.client.patch(
            f"/v1/vehicles/{vehicle.id}/review/issues/{issue.id}/resolve",
            {"dealerResponse": "Added clearer dashboard photos."},
            format="json",
        )

        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(resolve_response.status_code, 200)
        vehicle.refresh_from_db()
        issue.refresh_from_db()
        self.assertEqual(issue.status, VehicleReviewIssue.Status.RESOLVED)
        self.assertEqual(issue.dealer_response, "Added clearer dashboard photos.")
        self.assertEqual(
            vehicle.listing_verification_status,
            Vehicle.ListingVerificationStatus.PENDING_REVIEW,
        )

    def test_review_trail_retains_request_response_and_snapshot(self):
        vehicle = self.create_vehicle(
            status=Vehicle.Status.AVAILABLE,
            listing_verification_status=Vehicle.ListingVerificationStatus.PENDING_REVIEW,
        )
        self.authenticate(self.reviewer)
        with patch("apps.notifications.services.send_listing_review_issue_email.delay"):
            reject_response = self.client.patch(
                f"/v1/vehicles/{vehicle.id}/review/reject",
                {
                    "issues": [
                        {
                            "category": "price",
                            "message": "Price looks inconsistent with listed mileage.",
                        }
                    ]
                },
                format="json",
            )
        self.assertEqual(reject_response.status_code, 200)
        issue = VehicleReviewIssue.objects.get(vehicle=vehicle)
        self.authenticate()
        self.client.patch(
            f"/v1/vehicles/{vehicle.id}",
            {"priceNgn": 14000000},
            format="json",
        )
        self.client.patch(
            f"/v1/vehicles/{vehicle.id}/review/issues/{issue.id}/resolve",
            {"dealerResponse": "Adjusted the price after review."},
            format="json",
        )
        self.authenticate(self.reviewer)

        trail_response = self.client.get(f"/v1/vehicles/{vehicle.id}/review/issues")

        self.assertEqual(trail_response.status_code, 200)
        trail = trail_response.json()["data"]
        self.assertEqual(trail[0]["message"], "Price looks inconsistent with listed mileage.")
        self.assertEqual(trail[0]["dealerResponse"], "Adjusted the price after review.")
        self.assertEqual(trail[0]["vehicleSnapshot"]["priceNgn"], 15000000)

    def test_dealer_can_list_and_mark_notifications_read(self):
        vehicle = self.create_vehicle()
        issue = VehicleReviewIssue.objects.create(
            vehicle=vehicle,
            reviewer=self.reviewer,
            category=VehicleReviewIssue.Category.DETAILS,
            message="Update the vehicle details.",
        )
        notification = DealerNotification.objects.create(
            dealer=self.dealer,
            recipient=self.user,
            vehicle=vehicle,
            review_issue=issue,
            type=DealerNotification.Type.REVIEW_ISSUE,
            title="Listing review issue",
            body="Update the vehicle details.",
        )
        self.authenticate()

        list_response = self.client.get("/v1/notifications")
        read_response = self.client.post(f"/v1/notifications/{notification.id}/read")
        read_all_response = self.client.post("/v1/notifications/read-all")

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.json()["data"]["results"][0]["id"], str(notification.id))
        self.assertEqual(read_response.status_code, 200)
        self.assertIsNotNone(read_response.json()["data"]["readAt"])
        self.assertEqual(read_all_response.status_code, 200)

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
