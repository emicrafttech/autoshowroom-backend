from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import StaffUser
from apps.billing.models import BillingDispute, BillingPlan, Invoice, Subscription
from apps.buyers.models import BuyerConversation, BuyerMessage, BuyerOtp
from apps.dealers.models import Dealer, DealerLocation, DealerVerificationDocument
from apps.leads.models import AnalyticsEvent, GenericUploadRequest, Lead
from apps.notifications.models import DealerNotification
from apps.platform.models import (
    AuditLog,
    ContentReport,
    DealerSanction,
    PlatformRole,
    PlatformSetting,
    SanctionAppeal,
)
from apps.vehicles.models import Vehicle


class CsvCoverageCompletionTests(TestCase):
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
            is_primary=True,
        )
        self.staff = StaffUser.objects.create_user(
            email="owner@example.com",
            password="strong-pass-123",
            name="Owner",
            dealer=self.dealer,
            preferred_location=self.location,
        )
        self.platform_user = StaffUser.objects.create_user(
            email="platform@example.com",
            password="strong-pass-123",
            name="Platform",
            is_staff=True,
            is_superuser=True,
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

    def test_platform_user_stats_count_only_platform_staff(self):
        self.client.force_authenticate(self.platform_user)
        users_response = self.client.get("/v1/platform/users")
        self.assertEqual(users_response.status_code, 200)
        users_data = users_response.json()["data"]
        platform_users = users_data["results"] if isinstance(users_data, dict) else users_data
        self.assertNotIn(str(self.staff.id), [user["id"] for user in platform_users])

        users_stats_response = self.client.get("/v1/platform/users/stats")
        self.assertEqual(users_stats_response.status_code, 200)
        self.assertEqual(users_stats_response.json()["data"]["total"], len(platform_users))

    def test_audit_log_is_paginated_in_pages_of_100(self):
        self.client.force_authenticate(self.platform_user)
        AuditLog.objects.bulk_create(
            [
                AuditLog(
                    actor=self.platform_user,
                    action=f"audit.test.{index}",
                    target_type="AuditLog",
                    target_id=str(index),
                )
                for index in range(105)
            ]
        )

        first_page = self.client.get("/v1/platform/audit-trail/recent")
        self.assertEqual(first_page.status_code, 200)
        first_payload = first_page.json()["data"]
        self.assertEqual(len(first_payload["entries"]), 100)
        self.assertEqual(first_payload["pageSize"], 100)
        self.assertTrue(first_payload["hasMore"])
        self.assertEqual(first_payload["nextOffset"], 100)

        second_page = self.client.get("/v1/platform/audit-trail/recent?offset=100")
        self.assertEqual(second_page.status_code, 200)
        second_payload = second_page.json()["data"]
        self.assertGreaterEqual(len(second_payload["entries"]), 5)
        self.assertFalse(second_payload["hasMore"])
        self.assertIsNone(second_payload["nextOffset"])

    def test_audit_log_can_be_filtered_by_period_and_date_range(self):
        self.client.force_authenticate(self.platform_user)
        now = timezone.now()
        recent = AuditLog.objects.create(actor=self.platform_user, action="audit.filter.recent", target_type="AuditLog")
        week_old = AuditLog.objects.create(actor=self.platform_user, action="audit.filter.week", target_type="AuditLog")
        old = AuditLog.objects.create(actor=self.platform_user, action="audit.filter.old", target_type="AuditLog")
        AuditLog.objects.filter(id=recent.id).update(created_at=now - timedelta(hours=12))
        AuditLog.objects.filter(id=week_old.id).update(created_at=now - timedelta(days=3))
        AuditLog.objects.filter(id=old.id).update(created_at=now - timedelta(days=40))

        one_day = self.client.get("/v1/platform/audit-trail/recent?period=1d")
        self.assertEqual(one_day.status_code, 200)
        one_day_actions = [entry["action"] for entry in one_day.json()["data"]["entries"]]
        self.assertIn("audit.filter.recent", one_day_actions)
        self.assertNotIn("audit.filter.week", one_day_actions)
        self.assertNotIn("audit.filter.old", one_day_actions)

        seven_days = self.client.get("/v1/platform/audit-trail/recent?period=7d")
        self.assertEqual(seven_days.status_code, 200)
        seven_day_actions = [entry["action"] for entry in seven_days.json()["data"]["entries"]]
        self.assertIn("audit.filter.recent", seven_day_actions)
        self.assertIn("audit.filter.week", seven_day_actions)
        self.assertNotIn("audit.filter.old", seven_day_actions)

        range_date = (now - timedelta(days=3)).date().isoformat()
        date_range = self.client.get(f"/v1/platform/audit-trail/recent?startDate={range_date}&endDate={range_date}")
        self.assertEqual(date_range.status_code, 200)
        range_actions = [entry["action"] for entry in date_range.json()["data"]["entries"]]
        self.assertEqual(range_actions, ["audit.filter.week"])

    def test_platform_user_cannot_disable_self(self):
        self.client.force_authenticate(self.platform_user)
        response = self.client.patch(
            f"/v1/platform/users/{self.platform_user.id}",
            {"is_active": False},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.platform_user.refresh_from_db()
        self.assertTrue(self.platform_user.is_active)

    def test_platform_admin_can_invite_user_with_platform_role_permissions(self):
        self.client.force_authenticate(self.platform_user)
        role = PlatformRole.objects.create(
            name="Trust Ops",
            capabilities=["session.read", "platform_users.read"],
        )

        with patch("apps.notifications.services.notify_staff_invite") as send_invite:
            response = self.client.post(
                "/v1/platform/users",
                {
                    "name": "Trust Admin",
                    "email": "trust-admin@example.com",
                    "roleId": str(role.id),
                },
                format="json",
            )

        self.assertEqual(response.status_code, 201)
        invited = StaffUser.objects.get(email="trust-admin@example.com")
        self.assertTrue(invited.is_staff)
        self.assertEqual(invited.platform_role, role)
        self.assertTrue(invited.must_change_password)
        self.assertTrue(invited.invite_pending)
        self.assertEqual(response.json()["data"]["roleName"], "Trust Ops")
        self.assertEqual(response.json()["data"]["roleCapabilities"], ["platform_users.read", "session.read"])
        send_invite.assert_called_once()

    def test_platform_user_invite_requires_write_permission(self):
        role = PlatformRole.objects.create(
            name="Read Only",
            capabilities=["session.read", "platform_users.read"],
        )
        limited_user = StaffUser.objects.create_user(
            email="limited-platform@example.com",
            password="strong-pass-123",
            name="Limited Platform",
            is_staff=True,
            platform_role=role,
        )
        self.client.force_authenticate(limited_user)

        response = self.client.post(
            "/v1/platform/users",
            {
                "name": "Blocked Admin",
                "email": "blocked-admin@example.com",
                "roleId": str(role.id),
            },
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(StaffUser.objects.filter(email="blocked-admin@example.com").exists())

    def test_platform_user_permissions_limit_api_access(self):
        role = PlatformRole.objects.create(
            name="User Admin Read",
            capabilities=["session.read", "platform_users.read"],
        )
        limited_user = StaffUser.objects.create_user(
            email="users-readonly@example.com",
            password="strong-pass-123",
            name="Users Read Only",
            is_staff=True,
            platform_role=role,
        )
        self.client.force_authenticate(limited_user)

        self.assertEqual(self.client.get("/v1/platform/users").status_code, 200)
        self.assertEqual(self.client.get("/v1/platform/roles").status_code, 200)
        self.assertEqual(self.client.get("/v1/platform/users/stats").status_code, 200)
        self.assertEqual(self.client.get("/v1/platform/overview").status_code, 403)
        self.assertEqual(self.client.get("/v1/platform/reports").status_code, 403)
        self.assertEqual(self.client.get("/v1/platform/audit-trail/recent").status_code, 403)
        self.assertEqual(self.client.get("/v1/platform/billing/config").status_code, 403)

    def test_platform_billing_read_user_cannot_write_billing(self):
        role = PlatformRole.objects.create(
            name="Billing Reader",
            capabilities=["session.read", "billing.read"],
        )
        limited_user = StaffUser.objects.create_user(
            email="billing-readonly@example.com",
            password="strong-pass-123",
            name="Billing Read Only",
            is_staff=True,
            platform_role=role,
        )
        self.client.force_authenticate(limited_user)

        self.assertEqual(self.client.get("/v1/platform/billing/config").status_code, 200)
        self.assertEqual(self.client.get("/v1/platform/billing/plans").status_code, 200)
        response = self.client.post(
            "/v1/platform/billing/plans",
            {"name": "Blocked Billing Plan", "priceNgn": 1000, "listingLimit": 1, "standLimit": 1},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_listing_review_permission_is_required_for_vehicle_queue(self):
        role = PlatformRole.objects.create(
            name="Platform Users Only",
            capabilities=["session.read", "platform_users.read"],
        )
        limited_user = StaffUser.objects.create_user(
            email="no-listing-review@example.com",
            password="strong-pass-123",
            name="No Listing Review",
            is_staff=True,
            platform_role=role,
        )
        self.client.force_authenticate(limited_user)
        response = self.client.get("/v1/vehicles?listingVerificationStatus=pending_review")
        self.assertEqual(response.status_code, 403)

    def test_platform_can_suspend_dealer_from_directory(self):
        self.client.force_authenticate(self.platform_user)

        response = self.client.patch(
            f"/v1/platform/dealers/{self.dealer.id}/suspend",
            {"reason": "Repeated policy violations"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.dealer.refresh_from_db()
        self.assertEqual(self.dealer.operational_status, Dealer.OperationalStatus.SUSPENDED)
        self.assertEqual(self.dealer.suspended_reason, "Repeated policy violations")
        audit = AuditLog.objects.get(action="dealer.suspended", target_id=str(self.dealer.id))
        self.assertEqual(audit.actor, self.platform_user)
        self.assertEqual(audit.metadata["reason"], "Repeated policy violations")

    def test_platform_approves_sanction_appeal_and_lifts_sanction(self):
        self.client.force_authenticate(self.platform_user)
        sanction = DealerSanction.objects.create(
            dealer=self.dealer,
            reason="Repeated listing policy violations",
        )
        appeal = SanctionAppeal.objects.create(
            dealer=self.dealer,
            sanction=sanction,
            reason="We corrected the policy issue and request reinstatement.",
        )

        response = self.client.patch(
            f"/v1/platform/appeals/{appeal.id}",
            {"status": SanctionAppeal.Status.APPROVED},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        appeal.refresh_from_db()
        sanction.refresh_from_db()
        self.assertEqual(appeal.status, SanctionAppeal.Status.APPROVED)
        self.assertIsNotNone(appeal.decided_at)
        self.assertEqual(sanction.status, DealerSanction.Status.LIFTED)
        self.assertIsNotNone(sanction.lifted_at)
        self.assertTrue(
            AuditLog.objects.filter(
                action="sanction_appeal.approved",
                target_id=str(appeal.id),
            ).exists()
        )

    def test_platform_sanction_payload_includes_dealer_name_and_lift(self):
        self.client.force_authenticate(self.platform_user)
        sanction = DealerSanction.objects.create(
            dealer=self.dealer,
            reason="Manual trust enforcement",
        )

        list_response = self.client.get("/v1/platform/sanctions")
        self.assertEqual(list_response.status_code, 200)
        sanction_payload = list_response.json()["data"]["results"][0]
        self.assertEqual(sanction_payload["dealerName"], self.dealer.name)

        lift_response = self.client.patch(f"/v1/platform/sanctions/{sanction.id}/lift")
        self.assertEqual(lift_response.status_code, 200)
        self.assertEqual(lift_response.json()["data"]["status"], DealerSanction.Status.LIFTED)
        self.assertEqual(lift_response.json()["data"]["dealerName"], self.dealer.name)

    def test_platform_verification_queues_include_review_context(self):
        self.client.force_authenticate(self.platform_user)
        self.dealer.verification_status = Dealer.VerificationStatus.PENDING
        self.dealer.save(update_fields=["verification_status", "updated_at"])
        self.location.premises_verification_status = DealerLocation.PremisesVerificationStatus.PENDING
        self.location.evidence_files = ["https://example.com/showroom.jpg"]
        self.location.save(update_fields=["premises_verification_status", "evidence_files", "updated_at"])
        DealerVerificationDocument.objects.create(
            dealer=self.dealer,
            kind=DealerVerificationDocument.Kind.CAC,
            title="CAC certificate",
            file_url="https://example.com/cac.pdf",
        )

        dealer_response = self.client.get("/v1/platform/dealers/verification-queue")
        self.assertEqual(dealer_response.status_code, 200)
        dealer_case = dealer_response.json()["data"][0]
        self.assertEqual(dealer_case["name"], "Prime Motors")
        self.assertEqual(dealer_case["documents"][0]["title"], "CAC certificate")

        premises_response = self.client.get("/v1/platform/locations/premises-queue")
        self.assertEqual(premises_response.status_code, 200)
        premises_case = premises_response.json()["data"][0]
        self.assertEqual(premises_case["dealerName"], "Prime Motors")
        self.assertEqual(premises_case["dealer"]["name"], "Prime Motors")
        self.assertEqual(premises_case["evidenceFiles"], ["https://example.com/showroom.jpg"])
        self.assertIn("https://example.com/showroom.jpg", premises_case["premisesEvidence"])

    def test_premises_queue_surfaces_pending_stand_with_premises_document(self):
        self.client.force_authenticate(self.platform_user)
        self.location.premises_verification_status = DealerLocation.PremisesVerificationStatus.PENDING
        self.location.evidence_files = []
        self.location.save(update_fields=["premises_verification_status", "evidence_files", "updated_at"])
        DealerVerificationDocument.objects.create(
            dealer=self.dealer,
            kind=DealerVerificationDocument.Kind.PREMISES,
            title="Premises proof",
            file_url="https://example.com/premises.pdf",
        )

        premises_response = self.client.get("/v1/platform/locations/premises-queue")
        self.assertEqual(premises_response.status_code, 200)
        cases = premises_response.json()["data"]
        self.assertEqual(len(cases), 1)
        self.assertEqual(cases[0]["premisesEvidence"], ["https://example.com/premises.pdf"])

        stats_response = self.client.get("/v1/platform/locations/premises-queue/stats")
        self.assertEqual(stats_response.status_code, 200)
        self.assertEqual(stats_response.json()["data"]["total"], 1)

    def test_platform_can_review_dealer_verification_documents(self):
        self.client.force_authenticate(self.platform_user)
        document = DealerVerificationDocument.objects.create(
            dealer=self.dealer,
            kind=DealerVerificationDocument.Kind.IDENTITY,
            title="Director identity",
            file_url="https://example.com/id.pdf",
        )

        approve_response = self.client.patch(f"/v1/platform/dealer-documents/{document.id}/approve")
        self.assertEqual(approve_response.status_code, 200)
        document.refresh_from_db()
        self.assertEqual(document.status, DealerVerificationDocument.Status.APPROVED)
        self.assertIsNotNone(document.reviewed_at)

        missing_reason_response = self.client.patch(f"/v1/platform/dealer-documents/{document.id}/reject", {})
        self.assertEqual(missing_reason_response.status_code, 400)

        reject_response = self.client.patch(
            f"/v1/platform/dealer-documents/{document.id}/reject",
            {"reason": "Document is not legible."},
            format="json",
        )
        self.assertEqual(reject_response.status_code, 200)
        document.refresh_from_db()
        self.assertEqual(document.status, DealerVerificationDocument.Status.REJECTED)
        self.assertEqual(document.rejection_reason, "Document is not legible.")
        self.assertTrue(
            AuditLog.objects.filter(action="dealer_document.reject", target_id=str(document.id)).exists()
        )

    def test_platform_dealer_payload_returns_latest_document_per_kind(self):
        self.client.force_authenticate(self.platform_user)
        DealerVerificationDocument.objects.create(
            dealer=self.dealer,
            kind=DealerVerificationDocument.Kind.PREMISES,
            title="Old premises proof",
            file_url="https://example.com/old.pdf",
            status=DealerVerificationDocument.Status.REJECTED,
        )
        latest = DealerVerificationDocument.objects.create(
            dealer=self.dealer,
            kind=DealerVerificationDocument.Kind.PREMISES,
            title="New premises proof",
            file_url="https://example.com/new.jpg",
        )

        response = self.client.get("/v1/platform/dealers/verification-queue")
        self.assertEqual(response.status_code, 200)
        documents = response.json()["data"][0]["documents"]
        self.assertEqual(len(documents), 1)
        self.assertEqual(documents[0]["id"], str(latest.id))
        self.assertEqual(documents[0]["title"], "New premises proof")

    def test_platform_kyd_queue_includes_dealers_with_submitted_documents(self):
        self.client.force_authenticate(self.platform_user)
        self.dealer.verification_status = Dealer.VerificationStatus.NOT_SUBMITTED
        self.dealer.save(update_fields=["verification_status", "updated_at"])
        DealerVerificationDocument.objects.create(
            dealer=self.dealer,
            kind=DealerVerificationDocument.Kind.IDENTITY,
            title="Director ID",
            file_url="https://example.com/id.pdf",
            status=DealerVerificationDocument.Status.APPROVED,
        )

        response = self.client.get("/v1/platform/dealers/verification-queue")
        self.assertEqual(response.status_code, 200)
        cases = response.json()["data"]
        self.assertEqual(len(cases), 1)
        self.assertEqual(cases[0]["name"], "Prime Motors")

        directory_response = self.client.get("/v1/platform/dealers/directory")
        self.assertEqual(directory_response.status_code, 200)
        directory_cases = directory_response.json()["data"]["results"]
        self.assertEqual(directory_cases[0]["documents"][0]["title"], "Director ID")

        stats_response = self.client.get("/v1/platform/dealers/verification-queue/stats")
        self.assertEqual(stats_response.status_code, 200)
        self.assertEqual(stats_response.json()["data"]["total"], 1)
        pending_row = next(row for row in stats_response.json()["data"]["byStatus"] if row["status"] == "pending")
        self.assertEqual(pending_row["count"], 1)

    def test_platform_can_message_dealer_by_email_and_notification(self):
        self.client.force_authenticate(self.platform_user)

        with patch("apps.notifications.services.notify_platform_dealer_message") as send_message:
            response = self.client.post(
                f"/v1/platform/dealers/{self.dealer.id}/message",
                {"message": "Please update your KYD submission."},
                format="json",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["sent"], 1)
        notification = DealerNotification.objects.get(dealer=self.dealer)
        self.assertEqual(notification.recipient, self.staff)
        self.assertEqual(notification.type, DealerNotification.Type.PLATFORM_MESSAGE)
        self.assertEqual(notification.body, "Please update your KYD submission.")
        send_message.assert_called_once()
        self.assertTrue(AuditLog.objects.filter(action="dealer.message_sent").exists())

    def test_platform_verification_request_info_keeps_cases_pending(self):
        self.client.force_authenticate(self.platform_user)
        self.dealer.verification_status = Dealer.VerificationStatus.PENDING
        self.dealer.save(update_fields=["verification_status", "updated_at"])
        self.location.premises_verification_status = DealerLocation.PremisesVerificationStatus.PENDING
        self.location.evidence_files = ["https://example.com/showroom.jpg"]
        self.location.save(update_fields=["premises_verification_status", "evidence_files", "updated_at"])

        dealer_response = self.client.patch(
            f"/v1/dealers/{self.dealer.id}/verification/request-info",
            {"reason": "Upload a clearer CAC certificate."},
            format="json",
        )
        self.assertEqual(dealer_response.status_code, 200)
        self.dealer.refresh_from_db()
        self.assertEqual(self.dealer.verification_status, Dealer.VerificationStatus.PENDING)
        self.assertTrue(AuditLog.objects.filter(action="dealer.verification.info_requested").exists())

        premises_response = self.client.patch(
            f"/v1/platform/locations/{self.location.id}/request-info",
            {"reason": "Upload exterior signage photos."},
            format="json",
        )
        self.assertEqual(premises_response.status_code, 200)
        self.location.refresh_from_db()
        self.assertEqual(self.location.premises_verification_status, DealerLocation.PremisesVerificationStatus.PENDING)
        self.assertTrue(AuditLog.objects.filter(action="location.request-info").exists())

    def test_platform_admin_can_create_roles_with_valid_permissions(self):
        self.client.force_authenticate(self.platform_user)
        response = self.client.post(
            "/v1/platform/roles",
            {
                "name": "Trust Ops",
                "description": "Handles KYB and dealer verification queues.",
                "color": "#7aa2ff",
                "requireStepUp": True,
                "capabilities": ["overview.read", "dealer_verification.read", "dealer_verification.write"],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        role = PlatformRole.objects.get(name="Trust Ops")
        self.assertEqual(
            role.capabilities,
            ["dealer_verification.read", "dealer_verification.write", "overview.read", "session.read"],
        )
        self.assertEqual(role.description, "Handles KYB and dealer verification queues.")
        self.assertEqual(role.color, "#7aa2ff")
        self.assertTrue(role.require_step_up)

    def test_platform_roles_reject_unknown_permissions(self):
        self.client.force_authenticate(self.platform_user)
        response = self.client.post(
            "/v1/platform/roles",
            {"name": "Bad Role", "capabilities": ["dealers.read", "unknown.write"]},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(PlatformRole.objects.filter(name="Bad Role").exists())

    def buyer_token(self):
        response = self.client.post(
            "/v1/buyers/sign-in/start",
            {"phone": "+2348090000000"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        code = BuyerOtp.objects.get(phone="+2348090000000").code
        response = self.client.post(
            "/v1/buyers/sign-in/verify",
            {"phone": "+2348090000000", "code": code},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        return response.json()["data"]["token"]

    def test_dealer_staff_verification_sanction_and_account_delete_flows(self):
        self.client.force_authenticate(self.staff)
        staff_response = self.client.post(
            "/v1/dealers/me/staff",
            {
                "email": "sales@example.com",
                "name": "Sales User",
                "role": StaffUser.Role.SALES,
            },
            format="json",
        )
        self.assertEqual(staff_response.status_code, 201)
        self.assertIn("inviteToken", staff_response.json()["data"])

        document_response = self.client.post(
            "/v1/dealers/me/verification/documents",
            {
                "kind": "cac",
                "title": "CAC Certificate",
                "fileUrl": "https://example.com/cac.pdf",
            },
            format="json",
        )
        self.assertEqual(document_response.status_code, 201)
        self.assertEqual(DealerVerificationDocument.objects.count(), 1)

        submit_response = self.client.post("/v1/dealers/me/verification/submit")
        self.assertEqual(submit_response.status_code, 200)
        self.dealer.refresh_from_db()
        self.assertEqual(self.dealer.verification_status, Dealer.VerificationStatus.PENDING)

        self.location.evidence_files = ["https://example.com/showroom.jpg"]
        self.location.save(update_fields=["evidence_files", "updated_at"])
        premises_response = self.client.post(
            f"/v1/dealers/me/locations/{self.location.id}/request-verification",
        )
        self.assertEqual(premises_response.status_code, 200)
        self.location.refresh_from_db()
        self.assertEqual(
            self.location.premises_verification_status,
            DealerLocation.PremisesVerificationStatus.PENDING,
        )

        DealerSanction.objects.create(dealer=self.dealer, reason="Policy issue")
        status_response = self.client.get("/v1/dealers/me/sanction-status")
        self.assertEqual(status_response.status_code, 200)
        self.assertTrue(status_response.json()["data"]["hasActiveSanction"])

        appeal_response = self.client.post(
            "/v1/dealers/me/sanction-appeal",
            {"reason": "We fixed this."},
            format="json",
        )
        self.assertEqual(appeal_response.status_code, 201)
        self.assertEqual(SanctionAppeal.objects.count(), 1)

        delete_response = self.client.post("/v1/dealers/me/delete-account", {}, format="json")
        self.assertEqual(delete_response.status_code, 200)
        self.dealer.refresh_from_db()
        self.staff.refresh_from_db()
        self.assertEqual(self.dealer.operational_status, Dealer.OperationalStatus.SUSPENDED)
        self.assertFalse(self.staff.is_active)
        self.assertTrue(AuditLog.objects.filter(action="dealer.account_deleted").exists())

    def test_lead_management_reports_events_and_uploads(self):
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
        lead = Lead.objects.get()

        self.client.force_authenticate(self.staff)
        list_response = self.client.get("/v1/leads")
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.json()["data"]["count"], 1)

        update_response = self.client.patch(
            f"/v1/leads/{lead.id}",
            {"stage": Lead.Stage.CONTACTED},
            format="json",
        )
        self.assertEqual(update_response.status_code, 200)

        self.client.force_authenticate(None)
        report_response = self.client.post(
            "/v1/reports",
            {"vehicleId": str(self.vehicle.id), "reason": "Suspicious details"},
            format="json",
        )
        self.assertEqual(report_response.status_code, 201)
        self.assertEqual(ContentReport.objects.count(), 1)

        event_response = self.client.post(
            "/v1/events",
            {"name": "vehicle_view", "vehicleId": str(self.vehicle.id), "payload": {"source": "test"}},
            format="json",
        )
        self.assertEqual(event_response.status_code, 201)
        self.assertEqual(AnalyticsEvent.objects.count(), 1)

        with patch(
            "apps.leads.views.create_presigned_upload",
            return_value=SimpleNamespace(
                key="uploads/test.pdf",
                upload_url="https://upload.example.com",
                public_url="https://cdn.example.com/test.pdf",
            ),
        ):
            upload_response = self.client.post(
                "/v1/uploads",
                {
                    "purpose": "verification",
                    "fileName": "test.pdf",
                    "contentType": "application/pdf",
                },
                format="json",
            )
        self.assertEqual(upload_response.status_code, 201)
        self.assertEqual(GenericUploadRequest.objects.count(), 1)

    def test_buyer_vehicle_chat_and_dealer_response(self):
        token = self.buyer_token()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        open_response = self.client.post(
            f"/v1/vehicles/{self.vehicle.id}/chats",
            {"message": "Is this still available?"},
            format="json",
        )
        self.assertEqual(open_response.status_code, 201)
        conversation = BuyerConversation.objects.get()
        self.assertEqual(BuyerMessage.objects.count(), 1)

        list_response = self.client.get(f"/v1/vehicles/{self.vehicle.id}/chats")
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(len(list_response.json()["data"]), 1)

        detail_response = self.client.get(f"/v1/vehicles/{self.vehicle.id}/chats/{conversation.id}")
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(detail_response.json()["data"]["vehicle"]["id"], str(self.vehicle.id))

        self.client.credentials()
        self.client.force_authenticate(self.staff)
        dealer_response = self.client.post(
            f"/v1/vehicles/{self.vehicle.id}/chats/{conversation.id}/messages",
            {"message": "Yes, it is available."},
            format="json",
        )
        self.assertEqual(dealer_response.status_code, 201)
        self.assertEqual(BuyerMessage.objects.count(), 2)

        other_dealer = Dealer.objects.create(slug="other-motors", name="Other Motors")
        other_staff = StaffUser.objects.create_user(
            email="other@example.com",
            password="strong-pass-123",
            name="Other Owner",
            dealer=other_dealer,
        )
        self.client.force_authenticate(other_staff)
        blocked_response = self.client.get(f"/v1/vehicles/{self.vehicle.id}/chats/{conversation.id}")
        self.assertEqual(blocked_response.status_code, 404)

    def test_platform_console_and_billing_operations(self):
        self.client.force_authenticate(self.platform_user)
        settings_response = self.client.patch(
            "/v1/platform/settings",
            {"marketplace": {"maintenanceMode": False}},
            format="json",
        )
        self.assertEqual(settings_response.status_code, 200)
        self.assertEqual(PlatformSetting.objects.count(), 1)

        overview_response = self.client.get("/v1/platform/overview")
        self.assertEqual(overview_response.status_code, 200)

        missing_reason_response = self.client.patch(
            f"/v1/dealers/{self.dealer.id}/verification/reject",
            {},
            format="json",
        )
        self.assertEqual(missing_reason_response.status_code, 400)

        reject_response = self.client.patch(
            f"/v1/dealers/{self.dealer.id}/verification/reject",
            {"reason": "Business documents could not be verified."},
            format="json",
        )
        self.assertEqual(reject_response.status_code, 200)

        incident_response = self.client.post(
            "/v1/platform/security-incidents",
            {"title": "Suspicious login", "severity": "high"},
            format="json",
        )
        self.assertEqual(incident_response.status_code, 201)

        watchlist_response = self.client.post(
            "/v1/platform/watchlists",
            {"dealerId": str(self.dealer.id), "reason": "Monitor activity"},
            format="json",
        )
        self.assertEqual(watchlist_response.status_code, 201)

        plan_response = self.client.post(
            "/v1/platform/billing/plans",
            {
                "id": "growth",
                "name": "Growth",
                "priceNgn": 50000,
                "listingLimit": 50,
                "features": [],
                "isActive": True,
            },
            format="json",
        )
        self.assertEqual(plan_response.status_code, 201)
        plan = BillingPlan.objects.get(id="growth")
        subscription = Subscription.objects.create(
            dealer=self.dealer,
            plan=plan,
            current_period_end=timezone.now() + timedelta(days=30),
        )
        invoice = Invoice.objects.create(
            dealer=self.dealer,
            subscription=subscription,
            amount_ngn=50000,
        )
        dispute_response = self.client.post(
            "/v1/platform/billing/disputes",
            {
                "dealerId": str(self.dealer.id),
                "invoiceId": str(invoice.id),
                "reason": "Wrong amount",
            },
            format="json",
        )
        self.assertEqual(dispute_response.status_code, 201)
        self.assertEqual(dispute_response.json()["data"]["dealerName"], self.dealer.name)
        self.assertEqual(dispute_response.json()["data"]["amountNgn"], 50000)
        dispute = BillingDispute.objects.get()

        subscriptions_response = self.client.get("/v1/platform/billing/subscriptions")
        self.assertEqual(subscriptions_response.status_code, 200)
        subscription_payload = subscriptions_response.json()["data"]["results"][0]
        self.assertEqual(subscription_payload["dealerName"], self.dealer.name)
        self.assertEqual(subscription_payload["planName"], "Growth")
        self.assertEqual(subscription_payload["amountNgn"], 50000)

        accept_response = self.client.post(
            f"/v1/platform/billing/disputes/{dispute.id}/accept",
        )
        self.assertEqual(accept_response.status_code, 200)

        refund_response = self.client.post(
            f"/v1/platform/billing/subscriptions/{subscription.id}/refund",
            {"amountNgn": 1000, "reason": "Goodwill"},
            format="json",
        )
        self.assertEqual(refund_response.status_code, 202)
