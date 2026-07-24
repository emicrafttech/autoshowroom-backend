from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from unittest.mock import patch

from apps.accounts.models import DealerSignupOtp, StaffUser
from apps.accounts.tasks import EMAIL_SUSPENSION_REASON, enforce_dealer_email_verification
from apps.accounts.tokens import hash_invite_token, invite_expiry
from apps.billing.models import BillingPlan
from apps.dealers.models import Dealer, DealerLocation, DealerVerificationDocument
from apps.vehicles.models import Vehicle


class AuthDealerFoundationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        BillingPlan.objects.create(
            id="free",
            name="Free",
            price_ngn=0,
            listing_limit=5,
            stand_limit=5,
        )
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

    def test_refresh_accepts_valid_refresh_with_expired_access_header(self):
        from rest_framework_simplejwt.tokens import RefreshToken

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

        expired_access = RefreshToken(login_data["refreshToken"]).access_token
        expired_access.set_exp(lifetime=timedelta(seconds=-1))
        refresh_response = self.client.post(
            "/v1/auth/refresh",
            {"refreshToken": login_data["refreshToken"]},
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {expired_access}",
        )

        self.assertEqual(refresh_response.status_code, 200)
        refresh_data = refresh_response.json()["data"]
        self.assertIn("accessToken", refresh_data)
        self.assertIn("refreshToken", refresh_data)

    def test_mobile_login_issues_longer_refresh_token(self):
        from django.conf import settings
        from django.utils import timezone
        from rest_framework_simplejwt.tokens import RefreshToken

        desktop = self.client.post(
            "/v1/auth/login",
            {"email": "owner@example.com", "password": "strong-pass-123"},
            format="json",
        )
        mobile = self.client.post(
            "/v1/auth/login",
            {"email": "owner@example.com", "password": "strong-pass-123"},
            format="json",
            HTTP_X_CLIENT_PLATFORM="mobile",
        )
        self.assertEqual(desktop.status_code, 200)
        self.assertEqual(mobile.status_code, 200)

        desktop_refresh = RefreshToken(desktop.json()["data"]["refreshToken"])
        mobile_refresh = RefreshToken(mobile.json()["data"]["refreshToken"])
        now_ts = int(timezone.now().timestamp())
        desktop_ttl = desktop_refresh["exp"] - now_ts
        mobile_ttl = mobile_refresh["exp"] - now_ts

        self.assertAlmostEqual(
            desktop_ttl,
            settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds(),
            delta=30,
        )
        self.assertAlmostEqual(
            mobile_ttl,
            settings.JWT_MOBILE_REFRESH_TOKEN_DAYS * 24 * 60 * 60,
            delta=30,
        )
        self.assertGreater(mobile_ttl, desktop_ttl)

    def test_me_returns_current_user_with_verification_status(self):
        login_response = self.client.post(
            "/v1/auth/login",
            {"email": "owner@example.com", "password": "strong-pass-123"},
            format="json",
        )
        access = login_response.json()["data"]["accessToken"]

        me_response = self.client.get(
            "/v1/auth/me",
            HTTP_AUTHORIZATION=f"Bearer {access}",
        )
        self.assertEqual(me_response.status_code, 200)
        me_data = me_response.json()["data"]
        self.assertEqual(me_data["email"], "owner@example.com")
        self.assertEqual(me_data["dealerId"], str(self.dealer.id))
        self.assertEqual(me_data["locationId"], str(self.primary_location.id))
        self.assertFalse(me_data["emailVerified"])

        self.user.email_verified_at = timezone.now()
        self.user.save(update_fields=["email_verified_at", "updated_at"])
        me_response2 = self.client.get(
            "/v1/auth/me",
            HTTP_AUTHORIZATION=f"Bearer {access}",
        )
        self.assertEqual(me_response2.status_code, 200)
        self.assertTrue(me_response2.json()["data"]["emailVerified"])

    def test_me_requires_authentication(self):
        response = self.client.get("/v1/auth/me")
        self.assertIn(response.status_code, (401, 403))

    def test_login_rejects_invalid_credentials(self):
        response = self.client.post(
            "/v1/auth/login",
            {"email": "owner@example.com", "password": "wrong-pass-123"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())

    def test_dealer_can_request_and_confirm_password_reset(self):
        with patch("apps.notifications.services.notify_dealer_password_reset") as notify_reset:
            request_response = self.client.post(
                "/v1/auth/password-reset/request",
                {"email": "owner@example.com"},
                format="json",
            )

        self.assertEqual(request_response.status_code, 200)
        self.assertTrue(request_response.json()["data"]["ok"])
        token = notify_reset.call_args.args[1]
        self.user.refresh_from_db()
        self.assertEqual(self.user.password_reset_token_hash, hash_invite_token(token))
        self.assertIsNotNone(self.user.password_reset_expires_at)
        notify_reset.assert_called_once()

        confirm_response = self.client.post(
            "/v1/auth/password-reset/confirm",
            {
                "token": token,
                "password": "new-strong-pass-123",
                "confirmPassword": "new-strong-pass-123",
            },
            format="json",
        )

        self.assertEqual(confirm_response.status_code, 200)
        self.assertIn("accessToken", confirm_response.json()["data"])
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("new-strong-pass-123"))
        self.assertIsNone(self.user.password_reset_token_hash)
        self.assertIsNone(self.user.password_reset_expires_at)

    def test_password_reset_request_does_not_reveal_unknown_email(self):
        with patch("apps.notifications.services.notify_dealer_password_reset") as notify_reset:
            response = self.client.post(
                "/v1/auth/password-reset/request",
                {"email": "missing@example.com"},
                format="json",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"], {"ok": True})
        notify_reset.assert_not_called()

    def test_dealer_signup_start_and_verify_creates_owner_account(self):
        start_response = self.client.post(
            "/v1/auth/dealer-signup/start",
            {"phone": "+2348099999999"},
            format="json",
        )

        self.assertEqual(start_response.status_code, 201)
        code = DealerSignupOtp.objects.get(phone="+2348099999999").code

        verify_response = self.client.post(
            "/v1/auth/dealer-signup/verify",
            {
                "phone": "+2348099999999",
                "code": code,
            },
            format="json",
        )

        self.assertEqual(verify_response.status_code, 201)
        data = verify_response.json()["data"]
        self.assertIn("accessToken", data)
        self.assertTrue(data["user"]["email"].endswith("@pending.autoshowroom.local"))
        self.assertTrue(data["user"]["mustChangePassword"])
        created_user = StaffUser.objects.get(id=data["user"]["id"])
        self.assertEqual(created_user.role, StaffUser.Role.OWNER)
        self.assertEqual(created_user.dealer.name, "New Dealer")
        self.assertEqual(created_user.dealer.locations.count(), 1)
        from apps.billing.models import Subscription

        trial = Subscription.objects.get(dealer=created_user.dealer)
        self.assertEqual(trial.status, Subscription.Status.TRIALING)
        self.assertEqual(trial.plan_id, "starter")
        self.assertEqual(created_user.dealer.plan_id, "starter")
        self.assertIsNotNone(trial.current_period_end)

        self.client.force_authenticate(user=created_user)
        with patch("apps.accounts.views.issue_dealer_email_verification", return_value="dev-token"):
            setup_response = self.client.patch(
                "/v1/auth/dealer-signup/setup",
                {
                    "dealerName": "New Dealer Motors",
                    "email": "new-owner@example.com",
                    "standName": "Central Stand",
                    "districtSlug": "garki",
                    "address": "Plot 12, Garki, Abuja",
                },
                format="json",
            )
        self.assertEqual(setup_response.status_code, 200)
        created_user.refresh_from_db()
        self.assertEqual(created_user.email, "new-owner@example.com")
        self.assertEqual(created_user.dealer.name, "New Dealer Motors")
        self.assertEqual(created_user.preferred_location.name, "Central Stand")

        password_response = self.client.patch(
            "/v1/auth/dealer-signup/password",
            {"password": "signup-pass-123", "confirmPassword": "signup-pass-123"},
            format="json",
        )
        self.assertEqual(password_response.status_code, 200)
        created_user.refresh_from_db()
        self.assertTrue(created_user.check_password("signup-pass-123"))
        self.assertFalse(created_user.must_change_password)

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

    def test_staff_deactivation_role_hierarchy(self):
        manager = StaffUser.objects.create_user(
            email="manager@example.com",
            password="strong-pass-123",
            name="Manager User",
            role=StaffUser.Role.MANAGER,
            dealer=self.dealer,
        )
        sales = StaffUser.objects.create_user(
            email="sales@example.com",
            password="strong-pass-123",
            name="Sales User",
            role=StaffUser.Role.SALES,
            dealer=self.dealer,
        )

        # Owner cannot deactivate self.
        self.authenticate(self.user)
        self_deactivate = self.client.delete(f"/v1/dealers/me/staff/{self.user.id}")
        self.assertEqual(self_deactivate.status_code, 400)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)

        # Manager cannot deactivate an owner.
        self.authenticate(manager)
        manager_deactivate_owner = self.client.delete(f"/v1/dealers/me/staff/{self.user.id}")
        self.assertEqual(manager_deactivate_owner.status_code, 403)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)

        # Sales cannot deactivate a manager.
        self.authenticate(sales)
        sales_deactivate_manager = self.client.delete(f"/v1/dealers/me/staff/{manager.id}")
        self.assertEqual(sales_deactivate_manager.status_code, 403)
        manager.refresh_from_db()
        self.assertTrue(manager.is_active)

        # Manager can deactivate a sales member.
        self.authenticate(manager)
        manager_deactivate_sales = self.client.delete(f"/v1/dealers/me/staff/{sales.id}")
        self.assertEqual(manager_deactivate_sales.status_code, 204)
        sales.refresh_from_db()
        self.assertFalse(sales.is_active)

        # Owner can deactivate a manager.
        self.authenticate(self.user)
        owner_deactivate_manager = self.client.delete(f"/v1/dealers/me/staff/{manager.id}")
        self.assertEqual(owner_deactivate_manager.status_code, 204)
        manager.refresh_from_db()
        self.assertFalse(manager.is_active)

    def test_staff_reactivation_role_hierarchy(self):
        manager = StaffUser.objects.create_user(
            email="react-manager@example.com",
            password="strong-pass-123",
            name="Manager User",
            role=StaffUser.Role.MANAGER,
            dealer=self.dealer,
            is_active=False,
        )
        sales = StaffUser.objects.create_user(
            email="react-sales@example.com",
            password="strong-pass-123",
            name="Sales User",
            role=StaffUser.Role.SALES,
            dealer=self.dealer,
            is_active=False,
        )

        # Owner can reactivate a manager.
        self.authenticate(self.user)
        owner_reactivate = self.client.patch(
            f"/v1/dealers/me/staff/{manager.id}", {"is_active": True}, format="json"
        )
        self.assertEqual(owner_reactivate.status_code, 200)
        manager.refresh_from_db()
        self.assertTrue(manager.is_active)

        # Manager can reactivate a sales member.
        self.authenticate(manager)
        manager_reactivate = self.client.patch(
            f"/v1/dealers/me/staff/{sales.id}", {"is_active": True}, format="json"
        )
        self.assertEqual(manager_reactivate.status_code, 200)
        sales.refresh_from_db()
        self.assertTrue(sales.is_active)

        # Manager cannot reactivate the owner (owner inactive -> simulate).
        self.user.is_active = False
        self.user.save(update_fields=["is_active", "updated_at"])
        manager_reactivate_owner = self.client.patch(
            f"/v1/dealers/me/staff/{self.user.id}", {"is_active": True}, format="json"
        )
        self.assertEqual(manager_reactivate_owner.status_code, 403)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)

    def test_staff_role_change_hierarchy(self):
        manager = StaffUser.objects.create_user(
            email="role-manager@example.com",
            password="strong-pass-123",
            name="Manager User",
            role=StaffUser.Role.MANAGER,
            dealer=self.dealer,
        )
        sales = StaffUser.objects.create_user(
            email="role-sales@example.com",
            password="strong-pass-123",
            name="Sales User",
            role=StaffUser.Role.SALES,
            dealer=self.dealer,
        )

        # Owner cannot change own role.
        self.authenticate(self.user)
        self_role = self.client.patch(
            f"/v1/dealers/me/staff/{self.user.id}", {"role": "manager"}, format="json"
        )
        self.assertEqual(self_role.status_code, 400)
        self.user.refresh_from_db()
        self.assertEqual(self.user.role, StaffUser.Role.OWNER)

        # Sales cannot change anyone's role.
        self.authenticate(sales)
        sales_change = self.client.patch(
            f"/v1/dealers/me/staff/{manager.id}", {"role": "sales"}, format="json"
        )
        self.assertEqual(sales_change.status_code, 403)
        manager.refresh_from_db()
        self.assertEqual(manager.role, StaffUser.Role.MANAGER)

        # Manager cannot promote sales to owner.
        self.authenticate(manager)
        manager_promote = self.client.patch(
            f"/v1/dealers/me/staff/{sales.id}", {"role": "owner"}, format="json"
        )
        self.assertEqual(manager_promote.status_code, 403)
        sales.refresh_from_db()
        self.assertEqual(sales.role, StaffUser.Role.SALES)

        # Manager can change a sales member to manager.
        self.authenticate(manager)
        manager_change = self.client.patch(
            f"/v1/dealers/me/staff/{sales.id}", {"role": "manager"}, format="json"
        )
        self.assertEqual(manager_change.status_code, 200)
        sales.refresh_from_db()
        self.assertEqual(sales.role, StaffUser.Role.MANAGER)

        # Owner can change a manager to sales.
        self.authenticate(self.user)
        owner_change = self.client.patch(
            f"/v1/dealers/me/staff/{manager.id}", {"role": "sales"}, format="json"
        )
        self.assertEqual(owner_change.status_code, 200)
        manager.refresh_from_db()
        self.assertEqual(manager.role, StaffUser.Role.SALES)

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

    def test_dealer_profile_context_and_single_location_update(self):
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
        self.assertEqual(create_response.status_code, 405)

        patch_response = self.client.patch(
            f"/v1/dealers/me/locations/{self.primary_location.id}",
            {
                "area": "Maitama District",
                "evidenceFiles": ["https://cdn.example.com/maitama-stand.jpg"],
            },
            format="json",
        )
        self.assertEqual(patch_response.status_code, 200)
        self.assertEqual(patch_response.json()["data"]["area"], "Wuse")
        self.assertEqual(patch_response.json()["data"]["pendingChanges"]["area"], "Maitama District")
        self.assertEqual(patch_response.json()["data"]["premisesVerificationStatus"], "pending")

        set_primary_response = self.client.post(
            f"/v1/dealers/me/locations/{self.primary_location.id}/set-primary",
        )
        self.assertEqual(set_primary_response.status_code, 404)

        delete_response = self.client.delete(f"/v1/dealers/me/locations/{self.primary_location.id}")
        self.assertEqual(delete_response.status_code, 405)

    def test_email_verification_send_and_verify(self):
        self.authenticate()

        token = "email-token-with-enough-length"
        with patch("apps.notifications.email_verification.generate_invite_token", return_value=token), patch(
            "apps.notifications.tasks.send_dealer_email_verification_email.delay"
        ) as send_email:
            send_response = self.client.post("/v1/auth/email-verification/send", {}, format="json")

        self.assertEqual(send_response.status_code, 200)
        self.assertTrue(send_response.json()["data"]["sent"])
        self.assertFalse(send_response.json()["data"]["user"]["emailVerified"])
        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.email_verification_token_hash)
        self.assertIsNotNone(self.user.email_verification_sent_at)
        send_email.assert_called_once()

        verify_response = self.client.post(
            "/v1/auth/email-verification/verify",
            {"token": token},
            format="json",
        )

        self.assertEqual(verify_response.status_code, 200)
        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.email_verified_at)
        self.assertIsNone(self.user.email_verification_token_hash)

    def test_dealer_verification_document_upload_sets_pending_status(self):
        self.dealer.verification_status = Dealer.VerificationStatus.APPROVED
        self.dealer.verified_badge = True
        self.dealer.verified_at = timezone.now()
        self.dealer.save(update_fields=["verification_status", "verified_badge", "verified_at", "updated_at"])
        self.authenticate()

        response = self.client.post(
            "/v1/dealers/me/verification/documents",
            {
                "kind": "cac",
                "title": "CAC certificate",
                "fileUrl": "https://example.com/cac.pdf",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["data"]["status"], "pending")
        self.assertEqual(DealerVerificationDocument.objects.count(), 1)
        self.dealer.refresh_from_db()
        self.assertEqual(self.dealer.verification_status, Dealer.VerificationStatus.PENDING)
        self.assertFalse(self.dealer.verified_badge)

    def test_dealer_verification_document_resubmission_replaces_same_kind(self):
        old_document = DealerVerificationDocument.objects.create(
            dealer=self.dealer,
            kind=DealerVerificationDocument.Kind.PREMISES,
            title="Premises proof",
            file_url="https://example.com/old.pdf",
            status=DealerVerificationDocument.Status.REJECTED,
            rejection_reason="Too blurry.",
            reviewed_at=timezone.now(),
        )
        self.authenticate()

        response = self.client.post(
            "/v1/dealers/me/verification/documents",
            {
                "kind": "premises",
                "title": "New premises proof",
                "fileUrl": "https://example.com/new.jpg",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(DealerVerificationDocument.objects.count(), 1)
        old_document.refresh_from_db()
        self.assertEqual(old_document.title, "Premises proof")
        self.assertEqual(old_document.file_url, "https://example.com/new.jpg")
        self.assertEqual(old_document.status, DealerVerificationDocument.Status.PENDING)
        self.assertEqual(old_document.rejection_reason, "")
        self.assertIsNone(old_document.reviewed_at)
        self.primary_location.refresh_from_db()
        self.assertEqual(
            self.primary_location.premises_verification_status,
            DealerLocation.PremisesVerificationStatus.PENDING,
        )

    def test_primary_stand_can_request_verification_with_kyd_premises_proof(self):
        DealerVerificationDocument.objects.create(
            dealer=self.dealer,
            kind=DealerVerificationDocument.Kind.PREMISES,
            title="Premises proof",
            file_url="https://example.com/premises.jpg",
        )
        self.authenticate()

        primary_response = self.client.post(
            f"/v1/dealers/me/locations/{self.primary_location.id}/request-verification",
            {},
            format="json",
        )
        self.assertEqual(primary_response.status_code, 200)
        self.assertEqual(primary_response.json()["data"]["premisesVerificationStatus"], "pending")

        secondary_response = self.client.post(
            f"/v1/dealers/me/locations/{self.second_location.id}/request-verification",
            {},
            format="json",
        )
        self.assertEqual(secondary_response.status_code, 400)

    def test_email_verification_job_suspends_and_hides_overdue_dealer(self):
        self.user.email_verification_required_at = timezone.now() - timedelta(days=8)
        self.user.email_verified_at = None
        self.user.save(update_fields=["email_verification_required_at", "email_verified_at", "updated_at"])
        Vehicle.objects.create(
            dealer=self.dealer,
            location=self.primary_location,
            make="Toyota",
            model="Camry",
            slug="toyota-camry",
            year=2022,
            trim="SE",
            price_ngn=25000000,
            mileage_km=12000,
            transmission=Vehicle.Transmission.AUTOMATIC,
            fuel=Vehicle.Fuel.PETROL,
            colour="Black",
            body_type=Vehicle.BodyType.SEDAN,
            drivetrain=Vehicle.Drivetrain.FWD,
            condition_grade=Vehicle.ConditionGrade.GOOD,
            status=Vehicle.Status.AVAILABLE,
            listing_verification_status=Vehicle.ListingVerificationStatus.APPROVED,
            feed_ready=True,
        )

        result = enforce_dealer_email_verification()

        self.assertEqual(result["suspended"], 1)
        self.dealer.refresh_from_db()
        self.assertEqual(self.dealer.operational_status, Dealer.OperationalStatus.SUSPENDED)
        self.assertEqual(self.dealer.suspended_reason, EMAIL_SUSPENSION_REASON)

        login_response = self.client.post(
            "/v1/auth/login",
            {"email": "owner@example.com", "password": "strong-pass-123"},
            format="json",
        )
        self.assertEqual(login_response.status_code, 200)

        self.authenticate()
        profile_response = self.client.get("/v1/dealers/me")
        self.assertEqual(profile_response.status_code, 200)

        with patch("apps.notifications.tasks.send_dealer_email_verification_email.delay"):
            resend_response = self.client.post("/v1/auth/email-verification/send", {}, format="json")
        self.assertEqual(resend_response.status_code, 200)

        blocked_response = self.client.get("/v1/vehicles")
        self.assertEqual(blocked_response.status_code, 403)

        feed_response = self.client.get("/v1/feed")
        self.assertEqual(feed_response.status_code, 200)
        self.assertEqual(feed_response.json()["data"]["results"], [])

    def test_email_verification_reactivates_email_suspended_dealer(self):
        self.dealer.operational_status = Dealer.OperationalStatus.SUSPENDED
        self.dealer.suspended_at = timezone.now()
        self.dealer.suspended_reason = EMAIL_SUSPENSION_REASON
        self.dealer.save(update_fields=["operational_status", "suspended_at", "suspended_reason", "updated_at"])
        self.authenticate()

        token = "email-token-with-enough-length"
        with patch("apps.notifications.email_verification.generate_invite_token", return_value=token), patch(
            "apps.notifications.tasks.send_dealer_email_verification_email.delay"
        ):
            send_response = self.client.post("/v1/auth/email-verification/send", {}, format="json")
        verify_response = self.client.post(
            "/v1/auth/email-verification/verify",
            {"token": token},
            format="json",
        )

        self.assertEqual(verify_response.status_code, 200)
        self.dealer.refresh_from_db()
        self.assertEqual(self.dealer.operational_status, Dealer.OperationalStatus.ACTIVE)
        self.assertIsNone(self.dealer.suspended_reason)

    def test_dealer_location_create_is_not_exposed(self):
        self.authenticate()

        response = self.client.post(
            "/v1/dealers/me/locations",
            {"name": "Extra Stand", "districtSlug": "maitama"},
            format="json",
        )

        self.assertEqual(response.status_code, 405)

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
