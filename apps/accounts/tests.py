from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import StaffUser
from apps.accounts.tokens import hash_invite_token, invite_expiry
from apps.dealers.models import Dealer, DealerLocation


class AuthDealerFoundationTests(TestCase):
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
        self.second_location = DealerLocation.objects.create(
            dealer=self.dealer,
            name="Garki Stand",
            area="Garki",
            district_slug="garki",
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
        user = user or self.user
        self.client.force_authenticate(user=user)

    def test_login_and_refresh_return_tokens(self):
        login_response = self.client.post(
            "/v1/auth/login",
            {"email": "owner@example.com", "password": "strong-pass-123"},
            format="json",
        )

        self.assertEqual(login_response.status_code, 200)
        login_data = login_response.json()["data"]
        self.assertIn("accessToken", login_data)
        self.assertIn("refreshToken", login_data)
        self.assertEqual(login_data["user"]["dealerId"], str(self.dealer.id))
        self.assertEqual(login_data["user"]["locationId"], str(self.primary_location.id))

        refresh_response = self.client.post(
            "/v1/auth/refresh",
            {"refreshToken": login_data["refreshToken"]},
            format="json",
        )

        self.assertEqual(refresh_response.status_code, 200)
        refresh_data = refresh_response.json()["data"]
        self.assertIn("accessToken", refresh_data)
        self.assertIn("refreshToken", refresh_data)

    def test_login_rejects_invalid_credentials(self):
        response = self.client.post(
            "/v1/auth/login",
            {"email": "owner@example.com", "password": "wrong-pass-123"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())

    def test_staff_invitation_preview_and_accept(self):
        token = "invite-token-with-enough-length"
        invited = StaffUser.objects.create_user(
            email="sales@example.com",
            password=None,
            name="Sales User",
            role=StaffUser.Role.SALES,
            dealer=self.dealer,
            invite_token_hash=hash_invite_token(token),
            invite_expires_at=invite_expiry(),
            must_change_password=True,
        )

        preview_response = self.client.get(
            "/v1/staff-invitations/preview",
            {"token": token},
        )

        self.assertEqual(preview_response.status_code, 200)
        self.assertEqual(
            preview_response.json()["data"]["dealerName"],
            self.dealer.name,
        )

        accept_response = self.client.post(
            "/v1/staff-invitations/accept",
            {"token": token, "password": "accepted-pass-123"},
            format="json",
        )

        self.assertEqual(accept_response.status_code, 200)
        invited.refresh_from_db()
        self.assertTrue(invited.check_password("accepted-pass-123"))
        self.assertIsNone(invited.invite_token_hash)
        self.assertFalse(invited.must_change_password)
        self.assertIn("accessToken", accept_response.json()["data"])

    def test_change_password(self):
        self.authenticate()
        response = self.client.patch(
            "/v1/auth/password",
            {
                "currentPassword": "strong-pass-123",
                "newPassword": "new-strong-pass-123",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"], {"ok": True})
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("new-strong-pass-123"))

    def test_session_location_update_returns_new_session_tokens(self):
        self.authenticate()
        response = self.client.patch(
            "/v1/auth/session/location",
            {"locationId": str(self.second_location.id)},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["user"]["locationId"], str(self.second_location.id))
        self.assertIn("accessToken", data)
        self.user.refresh_from_db()
        self.assertEqual(self.user.preferred_location_id, self.second_location.id)

    def test_dealer_profile_context_and_location_crud(self):
        self.authenticate()

        profile_response = self.client.get("/v1/dealers/me")
        self.assertEqual(profile_response.status_code, 200)
        self.assertEqual(profile_response.json()["data"]["name"], "Prime Motors")

        update_response = self.client.patch(
            "/v1/dealers/me",
            {"name": "Prime Autos", "whatsapp": "+2348022222222"},
            format="json",
        )
        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(update_response.json()["data"]["name"], "Prime Autos")

        context_response = self.client.get("/v1/dealers/me/context")
        self.assertEqual(context_response.status_code, 200)
        self.assertEqual(
            context_response.json()["data"]["activeLocationId"],
            str(self.primary_location.id),
        )

        list_response = self.client.get("/v1/dealers/me/locations")
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(len(list_response.json()["data"]["results"]), 2)

        create_response = self.client.post(
            "/v1/dealers/me/locations",
            {"name": "Maitama Stand", "districtSlug": "maitama"},
            format="json",
        )
        self.assertEqual(create_response.status_code, 201)
        created_id = create_response.json()["data"]["id"]

        patch_response = self.client.patch(
            f"/v1/dealers/me/locations/{created_id}",
            {"area": "Maitama District"},
            format="json",
        )
        self.assertEqual(patch_response.status_code, 200)
        self.assertEqual(patch_response.json()["data"]["area"], "Maitama District")

        set_primary_response = self.client.post(
            f"/v1/dealers/me/locations/{created_id}/set-primary",
        )
        self.assertEqual(set_primary_response.status_code, 200)
        self.assertTrue(set_primary_response.json()["data"]["isPrimary"])

        delete_response = self.client.delete(f"/v1/dealers/me/locations/{created_id}")
        self.assertEqual(delete_response.status_code, 204)

    def test_dealer_location_routes_are_tenant_scoped(self):
        other_dealer = Dealer.objects.create(
            slug="other-motors",
            name="Other Motors",
            legal_name="Other Motors Limited",
            area="Asokoro",
            phone="+2348033333333",
        )
        other_location = DealerLocation.objects.create(
            dealer=other_dealer,
            name="Other Stand",
            area="Asokoro",
            district_slug="asokoro",
            is_primary=True,
        )

        self.authenticate()
        response = self.client.get(f"/v1/dealers/me/locations/{other_location.id}")

        self.assertEqual(response.status_code, 404)
