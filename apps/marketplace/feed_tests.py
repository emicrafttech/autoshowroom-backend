from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock

from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.billing.models import BillingPlan, Subscription
from apps.dealers.models import Dealer, DealerLocation
from apps.marketplace.feed import feed_shuffle_seed, rank_feed_page
from apps.vehicles.models import Vehicle


class FeedRankingUnitTests(SimpleTestCase):
    def test_rank_feed_page_prioritizes_subscribers_after_shuffle(self):
        vehicles = [
            SimpleNamespace(id="free-new", feed_priority=0),
            SimpleNamespace(id="growth-old", feed_priority=10),
            SimpleNamespace(id="free-old", feed_priority=0),
        ]
        params = Mock()
        params.get = lambda key, default=None: "unit-test" if key == "seed" else default
        params.items = lambda: [("seed", "unit-test")]

        ranked = rank_feed_page(vehicles, params=params, page_number=1)
        self.assertEqual([item.id for item in ranked[:1]], ["growth-old"])
        self.assertEqual({item.id for item in ranked[1:]}, {"free-new", "free-old"})

    def test_feed_shuffle_seed_is_stable(self):
        params = Mock()
        params.get = lambda key, default=None: "abc" if key == "seed" else default
        params.items = lambda: [("seed", "abc")]
        self.assertEqual(
            feed_shuffle_seed(params, 2),
            feed_shuffle_seed(params, 2),
        )
        self.assertNotEqual(
            feed_shuffle_seed(params, 1),
            feed_shuffle_seed(params, 2),
        )

    def test_different_feed_sessions_shuffle_differently(self):
        vehicles = [
            SimpleNamespace(id="a", feed_priority=0),
            SimpleNamespace(id="b", feed_priority=0),
            SimpleNamespace(id="c", feed_priority=0),
        ]

        def params_for(session: str):
            mock = Mock()
            mock.get = lambda key, default=None: session if key == "feedSession" else default
            mock.items = lambda session=session: [("feedSession", session)]
            return mock

        first = rank_feed_page(vehicles, params=params_for("session-a"), page_number=1)
        second = rank_feed_page(vehicles, params=params_for("session-b"), page_number=1)
        self.assertNotEqual(
            [item.id for item in first],
            [item.id for item in second],
        )


class FeedAlgorithmTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        BillingPlan.objects.update_or_create(
            id="free",
            defaults={
                "name": "Free",
                "price_ngn": 0,
                "listing_limit": 10,
                "stand_limit": 1,
                "feed_priority": 0,
            },
        )
        BillingPlan.objects.update_or_create(
            id="growth",
            defaults={
                "name": "Growth",
                "price_ngn": 50000,
                "listing_limit": 50,
                "stand_limit": 3,
                "feed_priority": 10,
            },
        )
        BillingPlan.objects.update_or_create(
            id="enterprise",
            defaults={
                "name": "Enterprise",
                "price_ngn": 150000,
                "listing_limit": 500,
                "stand_limit": 20,
                "feed_priority": 20,
            },
        )

        self.free_dealer = self._create_dealer("free-motors", plan_id="free")
        self.growth_dealer = self._create_dealer("growth-motors", plan_id="growth")
        self.free_location = self.free_dealer.locations.get()
        self.growth_location = self.growth_dealer.locations.get()

    def _create_dealer(self, slug: str, *, plan_id: str) -> Dealer:
        dealer = Dealer.objects.create(
            slug=slug,
            name=slug.replace("-", " ").title(),
            legal_name=f"{slug} Ltd",
            area="Wuse",
            phone="+2348011111111",
            plan_id=plan_id,
        )
        DealerLocation.objects.create(
            dealer=dealer,
            name="Main Stand",
            area="Wuse",
            district_slug="wuse",
            is_primary=True,
        )
        return dealer

    def _create_vehicle(
        self,
        dealer: Dealer,
        location: DealerLocation,
        *,
        slug: str,
        make: str,
        listing_approved_at,
    ) -> Vehicle:
        return Vehicle.objects.create(
            dealer=dealer,
            location=location,
            slug=slug,
            make=make,
            model="Camry",
            year=2020,
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
            listing_approved_at=listing_approved_at,
            published_at=listing_approved_at,
        )

    def test_feed_page_slice_uses_publish_time_before_ranking(self):
        now = timezone.now()
        older = self._create_vehicle(
            self.free_dealer,
            self.free_location,
            slug="older-toyota",
            make="Toyota",
            listing_approved_at=now - timedelta(days=2),
        )
        newer = self._create_vehicle(
            self.free_dealer,
            self.free_location,
            slug="newer-toyota",
            make="Toyota",
            listing_approved_at=now - timedelta(hours=1),
        )

        response = self.client.get("/v1/feed?pageSize=1&page=2&seed=feed-test")
        self.assertEqual(response.status_code, 200)
        results = response.json()["data"]["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], str(older.id))

        page_one = self.client.get("/v1/feed?pageSize=1&page=1&seed=feed-test")
        self.assertEqual(page_one.json()["data"]["results"][0]["id"], str(newer.id))

    def test_subscriber_vehicles_rank_before_free_plan_on_same_page(self):
        now = timezone.now()
        free_vehicle = self._create_vehicle(
            self.free_dealer,
            self.free_location,
            slug="free-listing",
            make="Toyota",
            listing_approved_at=now,
        )
        growth_vehicle = self._create_vehicle(
            self.growth_dealer,
            self.growth_location,
            slug="growth-listing",
            make="Honda",
            listing_approved_at=now - timedelta(hours=2),
        )

        response = self.client.get("/v1/feed?pageSize=2&seed=feed-test")
        self.assertEqual(response.status_code, 200)
        results = response.json()["data"]["results"]
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["id"], str(growth_vehicle.id))
        self.assertEqual(results[1]["id"], str(free_vehicle.id))

    def test_active_subscription_overrides_dealer_plan_priority(self):
        now = timezone.now()
        dealer = self._create_dealer("hybrid-motors", plan_id="free")
        location = dealer.locations.get()
        vehicle = self._create_vehicle(
            dealer,
            location,
            slug="hybrid-listing",
            make="Mazda",
            listing_approved_at=now,
        )
        growth_plan = BillingPlan.objects.get(id="growth")
        Subscription.objects.create(
            dealer=dealer,
            plan=growth_plan,
            status=Subscription.Status.ACTIVE,
        )

        response = self.client.get("/v1/feed?seed=feed-test")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["results"][0]["id"], str(vehicle.id))

    def test_shuffle_is_stable_for_same_seed_and_page(self):
        now = timezone.now()
        for index in range(4):
            self._create_vehicle(
                self.free_dealer,
                self.free_location,
                slug=f"stable-{index}",
                make=f"Make{index}",
                listing_approved_at=now - timedelta(hours=index),
            )

        first = self.client.get("/v1/feed?pageSize=4&seed=stable-shuffle")
        second = self.client.get("/v1/feed?pageSize=4&seed=stable-shuffle")
        first_ids = [item["id"] for item in first.json()["data"]["results"]]
        second_ids = [item["id"] for item in second.json()["data"]["results"]]
        self.assertEqual(first_ids, second_ids)

        publish_order_ids = [
            str(item.id)
            for item in Vehicle.objects.filter(dealer=self.free_dealer).order_by(
                "-listing_approved_at", "-updated_at", "-id"
            )
        ]
        self.assertNotEqual(first_ids, publish_order_ids)

    def test_same_priority_preserves_randomized_order(self):
        now = timezone.now()
        vehicles = [
            self._create_vehicle(
                self.free_dealer,
                self.free_location,
                slug=f"random-{index}",
                make=f"Brand{index}",
                listing_approved_at=now - timedelta(minutes=index),
            )
            for index in range(3)
        ]

        response = self.client.get("/v1/feed?pageSize=3&seed=random-only")
        ordered_ids = [item["id"] for item in response.json()["data"]["results"]]
        publish_order_ids = [str(vehicle.id) for vehicle in vehicles]
        self.assertNotEqual(ordered_ids, publish_order_ids)
