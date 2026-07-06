from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import DealerPushDevice, StaffUser
from apps.dealers.models import Dealer, DealerLocation


class DealerPushTokenTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.dealer = Dealer.objects.create(
            slug="prime-motors",
            name="Prime Motors",
            legal_name="Prime Motors Limited",
            area="Wuse",
            phone="+2348011111111",
        )
        self.primary_location = DealerLocation.objects.create(
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
            preferred_location=self.primary_location,
        )

    def authenticate(self, user=None):
        self.client.force_authenticate(user=user or self.user)

    def test_push_token_upsert_and_delete(self):
        self.authenticate()

        upsert_response = self.client.put(
            "/v1/dealers/me/push-token",
            {"token": "fcm-dealer-test-token", "platform": "android"},
            format="json",
        )
        self.assertEqual(upsert_response.status_code, 200)
        self.assertEqual(DealerPushDevice.objects.count(), 1)
        device = DealerPushDevice.objects.get()
        self.assertEqual(device.staff_user_id, self.user.id)
        self.assertEqual(device.fcm_token, "fcm-dealer-test-token")

        delete_response = self.client.delete(
            "/v1/dealers/me/push-token",
            {"token": "fcm-dealer-test-token"},
            format="json",
        )
        self.assertEqual(delete_response.status_code, 204)
        self.assertEqual(DealerPushDevice.objects.count(), 0)

    def test_push_token_requires_auth(self):
        response = self.client.put(
            "/v1/dealers/me/push-token",
            {"token": "fcm-dealer-test-token", "platform": "android"},
            format="json",
        )
        self.assertIn(response.status_code, (401, 403))

    def test_push_token_requires_token(self):
        self.authenticate()
        response = self.client.put(
            "/v1/dealers/me/push-token",
            {"platform": "android"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
