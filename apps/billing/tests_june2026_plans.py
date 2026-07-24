from datetime import timedelta
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
from openpyxl import load_workbook
from rest_framework.test import APIClient

from apps.accounts.models import StaffUser
from apps.billing.limits import soft_deactivate_excess_staff, soft_inactivate_excess_listings
from apps.billing.models import BillingPlan, Invoice, Subscription
from apps.billing.plan_catalogue import PLAN_MATRIX, vat_breakdown
from apps.billing.subscriptions import apply_due_plan_changes, compute_checkout_quote
from apps.dealers.models import Dealer, DealerLocation
from apps.vehicles.models import Vehicle


class June2026PlansTests(TestCase):
    def setUp(self):
        for plan in PLAN_MATRIX:
            BillingPlan.objects.update_or_create(id=plan["id"], defaults=plan)
        self.dealer = Dealer.objects.create(
            slug="amaka-autos",
            name="Amaka Autos",
            legal_name="Amaka Autos Ltd",
            area="Maitama",
            phone="+2348032224567",
            plan_id="starter",
        )
        self.location = DealerLocation.objects.create(
            dealer=self.dealer,
            name="Main",
            area="Maitama",
            district_slug="maitama",
            is_primary=True,
        )
        self.owner = StaffUser.objects.create_user(
            email="owner@example.com",
            password="pass12345",
            name="Owner",
            role=StaffUser.Role.OWNER,
            dealer=self.dealer,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.owner)

    def _vehicle(self, *, slug: str, status=Vehicle.Status.AVAILABLE) -> Vehicle:
        return Vehicle.objects.create(
            dealer=self.dealer,
            location=self.location,
            slug=slug,
            make="Toyota",
            model="Camry",
            year=2020,
            trim="XSE",
            price_ngn=20_000_000,
            mileage_km=10_000,
            transmission=Vehicle.Transmission.AUTOMATIC,
            fuel=Vehicle.Fuel.PETROL,
            colour="Black",
            body_type=Vehicle.BodyType.SEDAN,
            drivetrain=Vehicle.Drivetrain.FWD,
            condition_grade=Vehicle.ConditionGrade.GOOD,
            status=status,
            listing_verification_status=Vehicle.ListingVerificationStatus.APPROVED,
            feed_ready=status == Vehicle.Status.AVAILABLE,
        )

    def test_plans_endpoint_returns_june_matrix(self):
        response = self.client.get("/v1/billing/plans")
        self.assertEqual(response.status_code, 200)
        payload = response.json()["data"]
        items = payload["results"] if isinstance(payload, dict) and "results" in payload else payload
        plans = {item["id"]: item for item in items}
        self.assertIn("starter", plans)
        self.assertIn("growth", plans)
        self.assertIn("prestige", plans)
        self.assertEqual(plans["starter"]["priceNgn"], 20_000)
        self.assertEqual(plans["starter"]["priceYearlyNgn"], 180_000)
        self.assertEqual(plans["growth"]["listingLimit"], 75)
        self.assertIsNone(plans["prestige"]["listingLimit"])
        self.assertTrue(plans["growth"]["bulkUpload"])
        self.assertFalse(plans["starter"]["bulkUpload"])
        self.assertEqual(plans["starter"]["analyticsTier"], "basic")
        self.assertEqual(plans["growth"]["featuredSlotsPerMonth"], 3)
        self.assertEqual(plans["starter"]["videosPerVehicle"], 8)
        self.assertEqual(plans["growth"]["photosPerVehicle"], 30)
        self.assertEqual(plans["prestige"]["maxClipSeconds"], 180)
        self.assertIn("priority_support", plans["prestige"]["features"])
        self.assertNotIn("activeDealerCount", plans["starter"])
        self.assertNotIn("createdAt", plans["starter"])
        self.assertNotIn("updatedAt", plans["starter"])

    def test_vat_breakdown_is_inclusive(self):
        tax = vat_breakdown(20_000)
        self.assertEqual(tax["amountNgn"], 20_000)
        self.assertEqual(tax["amountExVatNgn"] + tax["vatNgn"], 20_000)

    def test_founding_trial_checkout_is_free(self):
        response = self.client.post(
            "/v1/billing/checkout",
            {"planId": "starter", "billingInterval": "monthly"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        payload = response.json()["data"]
        self.assertTrue(payload["foundingTrial"])
        self.assertEqual(payload["amountNgn"], 0)
        self.assertEqual(payload["checkoutKind"], "founding_trial")

        complete = self.client.post(
            "/v1/billing/checkout/complete",
            {"planId": "starter", "reference": payload["reference"]},
            format="json",
        )
        self.assertIn(complete.status_code, (200, 201))
        sub = Subscription.objects.get(dealer=self.dealer)
        self.assertEqual(sub.status, Subscription.Status.TRIALING)
        self.assertEqual(sub.plan_id, "starter")
        self.dealer.refresh_from_db()
        self.assertEqual(self.dealer.plan_id, "starter")

    def test_founding_trial_is_not_applied_to_paid_tiers(self):
        quote = compute_checkout_quote(
            self.dealer,
            BillingPlan.objects.get(id="growth"),
            billing_interval=Subscription.BillingInterval.MONTHLY,
        )

        self.assertFalse(quote["founding_trial"])
        self.assertEqual(quote["checkout_kind"], "new")
        self.assertEqual(quote["amount_ngn"], 50_000)

    def test_billing_summary_exposes_trial_and_blocked_auto_renew(self):
        response = self.client.get("/v1/billing/summary")
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        trial = data["trial"]
        self.assertTrue(trial["isTrialing"])
        self.assertEqual(trial["trialDays"], 90)
        self.assertEqual(trial["renewPriceNgn"], 20_000)
        self.assertEqual(trial["renewInterval"], "monthly")
        self.assertTrue(trial["autoRenewBlockedUntilCard"])
        self.assertFalse(trial["autoRenewEnabled"])
        self.assertEqual(data["subscription"]["status"], "trialing")
        self.assertEqual(data["subscription"]["plan"]["id"], "starter")
        self.assertEqual(data["planId"], "starter")
        self.assertEqual(data["entitlements"]["videosPerVehicle"], 8)
        self.assertEqual(data["entitlements"]["photosPerVehicle"], 30)
        self.assertEqual(data["entitlements"]["maxClipSeconds"], 180)
        self.assertEqual(data["standLimit"], 1)
        self.assertEqual(data["standCount"], 1)
        self.assertFalse(data["canAddStand"])
        self.assertEqual(
            Subscription.objects.filter(dealer=self.dealer, status=Subscription.Status.TRIALING).count(),
            1,
        )

    def test_soft_inactivate_excess_listings_hides_oldest(self):
        Subscription.objects.create(
            dealer=self.dealer,
            plan=BillingPlan.objects.get(id="starter"),
            status=Subscription.Status.ACTIVE,
            current_period_end=timezone.now() + timedelta(days=30),
        )
        vehicles = [self._vehicle(slug=f"car-{i}") for i in range(22)]
        hidden = soft_inactivate_excess_listings(self.dealer)
        self.assertEqual(hidden, 2)
        remaining = Vehicle.objects.filter(dealer=self.dealer).exclude(
            status__in=[Vehicle.Status.HIDDEN, Vehicle.Status.SOLD]
        )
        self.assertEqual(remaining.count(), 20)
        vehicles[0].refresh_from_db()
        vehicles[1].refresh_from_db()
        self.assertEqual(vehicles[0].status, Vehicle.Status.HIDDEN)
        self.assertEqual(vehicles[1].status, Vehicle.Status.HIDDEN)

    def test_staff_invite_respects_limit(self):
        Subscription.objects.create(
            dealer=self.dealer,
            plan=BillingPlan.objects.get(id="starter"),
            status=Subscription.Status.ACTIVE,
            current_period_end=timezone.now() + timedelta(days=30),
        )
        response = self.client.post(
            "/v1/dealers/me/staff",
            {"email": "extra@example.com", "name": "Extra", "role": "sales"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_due_downgrade_deactivates_excess_staff(self):
        growth = BillingPlan.objects.get(id="growth")
        starter = BillingPlan.objects.get(id="starter")
        subscription = Subscription.objects.create(
            dealer=self.dealer,
            plan=growth,
            pending_plan=starter,
            pending_plan_effective_at=timezone.now() - timedelta(seconds=1),
            status=Subscription.Status.ACTIVE,
            current_period_end=timezone.now() + timedelta(days=30),
        )
        extra_users = [
            StaffUser.objects.create_user(
                email=f"staff-{index}@example.com",
                password="pass12345",
                name=f"Staff {index}",
                role=StaffUser.Role.SALES,
                dealer=self.dealer,
            )
            for index in range(4)
        ]

        self.assertTrue(apply_due_plan_changes(self.dealer))

        subscription.refresh_from_db()
        self.owner.refresh_from_db()
        self.assertEqual(subscription.plan_id, "starter")
        self.assertTrue(self.owner.is_active)
        self.assertEqual(self.dealer.staff_users.filter(is_active=True).count(), 1)
        self.assertFalse(
            StaffUser.objects.filter(id__in=[user.id for user in extra_users], is_active=True).exists()
        )

    def test_staff_reconciliation_keeps_accounts_within_limit(self):
        Subscription.objects.create(
            dealer=self.dealer,
            plan=BillingPlan.objects.get(id="starter"),
            status=Subscription.Status.ACTIVE,
            current_period_end=timezone.now() + timedelta(days=30),
        )

        self.assertEqual(soft_deactivate_excess_staff(self.dealer), 0)
        self.owner.refresh_from_db()
        self.assertTrue(self.owner.is_active)

    def test_staff_reconciliation_skips_unlimited_plan(self):
        Subscription.objects.create(
            dealer=self.dealer,
            plan=BillingPlan.objects.get(id="prestige"),
            status=Subscription.Status.ACTIVE,
            current_period_end=timezone.now() + timedelta(days=30),
        )
        staff = StaffUser.objects.create_user(
            email="prestige-staff@example.com",
            password="pass12345",
            name="Prestige Staff",
            role=StaffUser.Role.SALES,
            dealer=self.dealer,
        )

        self.assertEqual(soft_deactivate_excess_staff(self.dealer), 0)
        staff.refresh_from_db()
        self.assertTrue(staff.is_active)

    def test_bulk_upload_blocked_on_starter(self):
        Subscription.objects.create(
            dealer=self.dealer,
            plan=BillingPlan.objects.get(id="starter"),
            status=Subscription.Status.ACTIVE,
            current_period_end=timezone.now() + timedelta(days=30),
        )
        csv_body = (
            "# Allowed values for fields with fixed options:\n"
            "# transmission: automatic | manual\n"
            "make,model,year,trim,priceNgn,mileageKm,transmission,fuel,colour,"
            "bodyType,drivetrain,conditionGrade,negotiable,description,"
            "videoLink1,videoLink2,videoLink3,"
            "imageLink1,imageLink2,imageLink3,imageLink4,imageLink5,imageLink6\n"
            "Toyota,Corolla,2019,X,12000000,40000,automatic,petrol,Silver,"
            "sedan,fwd,good,yes,Well maintained,"
            "https://example.com/video-1.mp4,"
            "https://example.com/video-2.mp4,"
            "https://example.com/video-3.mp4,"
            "https://example.com/image-1.jpg,"
            "https://example.com/image-2.jpg,"
            "https://example.com/image-3.jpg,"
            "https://example.com/image-4.jpg,"
            "https://example.com/image-5.jpg,"
            "https://example.com/image-6.jpg\n"
        )
        response = self.client.post(
            "/v1/vehicles/bulk-upload",
            {"file": SimpleUploadedFile("stock.csv", csv_body.encode("utf-8"), content_type="text/csv")},
            format="multipart",
        )
        self.assertEqual(response.status_code, 403)

    def test_bulk_upload_csv_on_growth(self):
        Subscription.objects.create(
            dealer=self.dealer,
            plan=BillingPlan.objects.get(id="growth"),
            status=Subscription.Status.ACTIVE,
            current_period_end=timezone.now() + timedelta(days=30),
        )
        csv_body = (
            "# Allowed values for fields with fixed options:\n"
            "# transmission: automatic | manual\n"
            "make,model,year,trim,priceNgn,mileageKm,transmission,fuel,colour,"
            "bodyType,drivetrain,conditionGrade,negotiable,description,"
            "videoLink1,videoLink2,videoLink3,"
            "imageLink1,imageLink2,imageLink3,imageLink4,imageLink5,imageLink6\n"
            "Toyota,Corolla,2019,X,12000000,40000,automatic,petrol,Silver,"
            "sedan,fwd,good,yes,Well maintained,"
            "https://example.com/video-1.mp4,"
            "https://example.com/video-2.mp4,"
            "https://example.com/video-3.mp4,"
            "https://example.com/image-1.jpg,"
            "https://example.com/image-2.jpg,"
            "https://example.com/image-3.jpg,"
            "https://example.com/image-4.jpg,"
            "https://example.com/image-5.jpg,"
            "https://example.com/image-6.jpg\n"
        )
        response = self.client.post(
            "/v1/vehicles/bulk-upload",
            {"file": SimpleUploadedFile("stock.csv", csv_body.encode("utf-8"), content_type="text/csv")},
            format="multipart",
        )
        self.assertEqual(response.status_code, 201)
        payload = response.json()["data"]
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["failedCount"], 0)
        vehicle = Vehicle.objects.get(dealer=self.dealer, make="Toyota", model="Corolla")
        self.assertEqual(vehicle.status, Vehicle.Status.HIDDEN)
        self.assertEqual(vehicle.notes, "Well maintained")
        self.assertEqual(vehicle.media_items.count(), 9)
        self.assertEqual(vehicle.media_items.filter(kind="video").count(), 3)
        self.assertEqual(vehicle.media_items.filter(kind="photo").count(), 6)
        self.assertIsNotNone(vehicle.cover_media_id)

    def test_bulk_upload_supports_global_media_limits(self):
        Subscription.objects.create(
            dealer=self.dealer,
            plan=BillingPlan.objects.get(id="growth"),
            status=Subscription.Status.ACTIVE,
            current_period_end=timezone.now() + timedelta(days=30),
        )
        headers = [
            "make",
            "model",
            "year",
            "priceNgn",
            "mileageKm",
            *[f"videoLink{index}" for index in range(1, 9)],
            *[f"imageLink{index}" for index in range(1, 31)],
        ]
        values = [
            "Toyota",
            "Land Cruiser",
            "2021",
            "75000000",
            "25000",
            *[f"https://example.com/video-{index}.mp4" for index in range(1, 9)],
            *[f"https://example.com/photo-{index}.jpg" for index in range(1, 31)],
        ]
        csv_body = f"{','.join(headers)}\n{','.join(values)}\n"

        response = self.client.post(
            "/v1/vehicles/bulk-upload",
            {"file": SimpleUploadedFile("global-limits.csv", csv_body.encode(), content_type="text/csv")},
            format="multipart",
        )

        self.assertEqual(response.status_code, 201)
        vehicle = Vehicle.objects.get(dealer=self.dealer, model="Land Cruiser")
        self.assertEqual(vehicle.media_items.filter(kind="video").count(), 8)
        self.assertEqual(vehicle.media_items.filter(kind="photo").count(), 30)

    def test_bulk_upload_template_download(self):
        response = self.client.get("/v1/vehicles/bulk-upload/template?type=csv")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response["Content-Type"])
        self.assertIn(
            b"# transmission: automatic | manual",
            response.content,
        )
        self.assertIn(
            b"# negotiable: yes | no",
            response.content,
        )
        self.assertIn(b"make,model,year", response.content)
        self.assertIn(b"description", response.content)
        self.assertIn(
            b"videoLink1,videoLink2,videoLink3,videoLink4,videoLink5,videoLink6,videoLink7,videoLink8",
            response.content,
        )
        self.assertIn(
            b"imageLink1,imageLink2,imageLink3,imageLink4,imageLink5,imageLink6,imageLink7,imageLink8,imageLink9,imageLink10,imageLink11,imageLink12,imageLink13,imageLink14,imageLink15,imageLink16,imageLink17,imageLink18,imageLink19,imageLink20,imageLink21,imageLink22,imageLink23,imageLink24,imageLink25,imageLink26,imageLink27,imageLink28,imageLink29,imageLink30",
            response.content,
        )
        xlsx = self.client.get("/v1/vehicles/bulk-upload/template?type=xlsx")
        self.assertEqual(xlsx.status_code, 200)
        self.assertIn(
            "spreadsheetml.sheet",
            xlsx["Content-Type"],
        )
        self.assertTrue(len(xlsx.content) > 100)
        workbook = load_workbook(BytesIO(xlsx.content))
        sheet = workbook["Inventory"]
        headers = [cell.value for cell in sheet[1]]
        self.assertIn("description", headers)
        self.assertNotIn("notes", headers)
        self.assertEqual(
            headers[-38:],
            [
                *[f"videoLink{index}" for index in range(1, 9)],
                *[f"imageLink{index}" for index in range(1, 31)],
            ],
        )
        validations = list(sheet.data_validations.dataValidation)
        self.assertEqual(len(validations), 6)
        formulas = {validation.formula1 for validation in validations}
        self.assertEqual(formulas, {
            '"automatic,manual"',
            '"petrol,diesel,hybrid,electric"',
            '"sedan,suv,hatchback,pickup,coupe,van,wagon,convertible,minivan"',
            '"fwd,rwd,awd,four_wd"',
            '"excellent,good,fair"',
            '"yes,no"',
        })
        workbook.close()

    def test_insights_basic_hides_full_breakdown(self):
        Subscription.objects.create(
            dealer=self.dealer,
            plan=BillingPlan.objects.get(id="starter"),
            status=Subscription.Status.ACTIVE,
            current_period_end=timezone.now() + timedelta(days=30),
        )
        response = self.client.get("/v1/dealers/me/insights")
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["analyticsTier"], "basic")
        self.assertEqual(data["leadSources"], [])
        self.assertEqual(data["carsByMakeModel"], [])

    def test_feature_quota_on_growth(self):
        Subscription.objects.create(
            dealer=self.dealer,
            plan=BillingPlan.objects.get(id="growth"),
            status=Subscription.Status.ACTIVE,
            current_period_end=timezone.now() + timedelta(days=30),
        )
        vehicle = self._vehicle(slug="feature-me")
        ok = self.client.post(f"/v1/vehicles/{vehicle.id}/feature", {}, format="json")
        self.assertEqual(ok.status_code, 200)
        self.assertTrue(ok.json()["data"]["isFeatured"])
        for index in range(2):
            other = self._vehicle(slug=f"feature-{index}")
            self.client.post(f"/v1/vehicles/{other.id}/feature", {}, format="json")
        blocked = self.client.post(
            f"/v1/vehicles/{self._vehicle(slug='too-many').id}/feature",
            {},
            format="json",
        )
        self.assertEqual(blocked.status_code, 400)
