from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import StaffUser
from apps.bookings.models import Booking
from apps.dealers.models import Dealer, DealerLocation
from apps.leads.models import Lead
from apps.notifications.models import DealerNotification
from apps.notifications.tasks import (
    send_booking_confirmation_email,
    send_dealer_email_verification_email,
    send_dealer_verification_success_email,
    send_listing_review_issue_email,
    send_new_lead_alert_email,
    send_platform_message_emails,
    send_staff_invite_email,
)
from apps.platform.models import PlatformRole
from apps.vehicles.models import Vehicle, VehicleReviewIssue


class DealerNotificationFlowTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.dealer = Dealer.objects.create(
            slug="notify-dealer",
            name="Notify Dealer",
            legal_name="Notify Dealer Ltd",
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
            email="owner@notify.test",
            password="strong-pass-123",
            name="Owner",
            dealer=self.dealer,
            preferred_location=self.location,
        )
        self.platform_user = StaffUser.objects.create_user(
            email="platform@notify.test",
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
            price_ngn=15000000,
            mileage_km=45000,
            transmission=Vehicle.Transmission.AUTOMATIC,
            fuel=Vehicle.Fuel.PETROL,
            body_type=Vehicle.BodyType.SEDAN,
            drivetrain=Vehicle.Drivetrain.FWD,
            condition_grade=Vehicle.ConditionGrade.GOOD,
            status=Vehicle.Status.AVAILABLE,
            listing_verification_status=Vehicle.ListingVerificationStatus.PENDING_REVIEW,
        )

    def test_platform_message_creates_dealer_notification(self):
        self.client.force_authenticate(self.platform_user)
        with patch("apps.notifications.services.send_platform_message_emails.delay"):
            response = self.client.post(
                f"/v1/platform/dealers/{self.dealer.id}/message",
                {"subject": "Action needed", "message": "Please update your documents."},
                format="json",
            )
        self.assertEqual(response.status_code, 200)
        notification = DealerNotification.objects.get(dealer=self.dealer, recipient=self.staff)
        self.assertEqual(notification.type, DealerNotification.Type.PLATFORM_MESSAGE)
        self.assertEqual(notification.body, "Please update your documents.")

    def test_dealer_lists_marks_read_and_marks_all_read(self):
        first = DealerNotification.objects.create(
            dealer=self.dealer,
            recipient=self.staff,
            type=DealerNotification.Type.PLATFORM_MESSAGE,
            title="Platform message",
            body="First message",
        )
        second = DealerNotification.objects.create(
            dealer=self.dealer,
            recipient=self.staff,
            type=DealerNotification.Type.PLATFORM_MESSAGE,
            title="Platform message",
            body="Second message",
        )
        self.client.force_authenticate(self.staff)

        list_response = self.client.get("/v1/notifications")
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(len(list_response.json()["data"]["results"]), 2)

        read_response = self.client.post(f"/v1/notifications/{first.id}/read")
        self.assertEqual(read_response.status_code, 200)
        self.assertIsNotNone(read_response.json()["data"]["readAt"])

        read_all_response = self.client.post("/v1/notifications/read-all")
        self.assertEqual(read_all_response.status_code, 200)
        self.assertEqual(read_all_response.json()["data"]["updated"], 1)
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertIsNotNone(first.read_at)
        self.assertIsNotNone(second.read_at)

    def test_review_issue_notification_end_to_end(self):
        review_role = PlatformRole.objects.create(
            name="Listing reviewer",
            capabilities=["listing_review.read", "listing_review.write"],
        )
        reviewer = StaffUser.objects.create_user(
            email="reviewer@notify.test",
            password="strong-pass-123",
            name="Reviewer",
            is_staff=True,
            platform_role=review_role,
        )
        self.client.force_authenticate(reviewer)
        with patch("apps.notifications.services.send_listing_review_issue_email.delay"):
            response = self.client.patch(
                f"/v1/vehicles/{self.vehicle.id}/review/reject",
                {
                    "reason": "Needs updates",
                    "issues": [{"category": "details", "message": "Fix the mileage."}],
                },
                format="json",
            )
        self.assertEqual(response.status_code, 200)
        notification = DealerNotification.objects.get(vehicle=self.vehicle, recipient=self.staff)
        self.assertEqual(notification.type, DealerNotification.Type.REVIEW_ISSUE)
        self.assertEqual(notification.body, "2020 Toyota Camry: Fix the mileage.")

        self.client.force_authenticate(self.staff)
        list_response = self.client.get("/v1/notifications")
        self.assertEqual(list_response.status_code, 200)
        payload = list_response.json()["data"]["results"][0]
        self.assertEqual(payload["vehicleId"], str(self.vehicle.id))
        self.assertEqual(payload["vehicleTitle"], "2020 Toyota Camry")


class PlatformNotificationFlowTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.dealer = Dealer.objects.create(
            slug="platform-notify-dealer",
            name="Platform Notify Dealer",
            legal_name="Platform Notify Dealer Ltd",
            area="Wuse",
            phone="+2348022222222",
        )
        self.location = DealerLocation.objects.create(
            dealer=self.dealer,
            name="Main Stand",
            area="Wuse",
            is_primary=True,
        )
        review_role = PlatformRole.objects.create(
            name="Listing reviewer",
            capabilities=["listing_review.read", "listing_review.write"],
        )
        self.platform_reviewer = StaffUser.objects.create_user(
            email="platform-reviewer@notify.test",
            password="strong-pass-123",
            name="Platform Reviewer",
            is_staff=True,
            platform_role=review_role,
        )
        self.platform_other = StaffUser.objects.create_user(
            email="platform-other@notify.test",
            password="strong-pass-123",
            name="Platform Other",
            is_staff=True,
            platform_role=PlatformRole.objects.create(
                name="Billing only",
                capabilities=["billing.read"],
            ),
        )
        self.vehicle = Vehicle.objects.create(
            dealer=self.dealer,
            location=self.location,
            slug="honda-accord-2021",
            make="Honda",
            model="Accord",
            year=2021,
            price_ngn=18000000,
            mileage_km=30000,
            transmission=Vehicle.Transmission.AUTOMATIC,
            fuel=Vehicle.Fuel.PETROL,
            body_type=Vehicle.BodyType.SEDAN,
            drivetrain=Vehicle.Drivetrain.FWD,
            condition_grade=Vehicle.ConditionGrade.GOOD,
            status=Vehicle.Status.AVAILABLE,
            listing_verification_status=Vehicle.ListingVerificationStatus.DRAFT,
        )

    def test_listing_review_submission_notifies_capable_platform_staff(self):
        from apps.notifications.models import PlatformNotification
        from apps.notifications.platform_notifications import notify_listing_review_submitted

        self.vehicle.listing_verification_status = Vehicle.ListingVerificationStatus.PENDING_REVIEW
        self.vehicle.save(update_fields=["listing_verification_status", "updated_at"])
        notify_listing_review_submitted(self.vehicle)

        self.assertTrue(
            PlatformNotification.objects.filter(
                recipient=self.platform_reviewer,
                type=PlatformNotification.Type.LISTING_REVIEW_SUBMITTED,
                vehicle=self.vehicle,
            ).exists()
        )
        self.assertFalse(
            PlatformNotification.objects.filter(recipient=self.platform_other).exists()
        )

        self.client.force_authenticate(self.platform_reviewer)
        list_response = self.client.get("/v1/platform/notifications")
        self.assertEqual(list_response.status_code, 200)
        results = list_response.json()["data"]["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "Listing submitted for review")
        self.assertEqual(results[0]["href"], "/listings/review")
        self.assertEqual(results[0]["vehicleTitle"], "2021 Honda Accord")

        notification_id = results[0]["id"]
        read_response = self.client.post(f"/v1/platform/notifications/{notification_id}/read")
        self.assertEqual(read_response.status_code, 200)
        self.assertIsNotNone(read_response.json()["data"]["readAt"])

        PlatformNotification.objects.create(
            recipient=self.platform_reviewer,
            type=PlatformNotification.Type.DEALER_VERIFICATION_SUBMITTED,
            title="Dealer verification submitted",
            body="Another case",
            href="/verification",
            dealer=self.dealer,
        )
        read_all_response = self.client.post("/v1/platform/notifications/read-all")
        self.assertEqual(read_all_response.status_code, 200)
        self.assertEqual(read_all_response.json()["data"]["updated"], 1)


class TransactionalEmailTests(TestCase):
    def setUp(self):
        self.dealer = Dealer.objects.create(
            slug="email-dealer",
            name="GrandView Motors",
            legal_name="GrandView Motors Ltd",
            area="Wuse",
            phone="+2348033333333",
            verification_status=Dealer.VerificationStatus.APPROVED,
            verified_badge=True,
            verified_at=timezone.now(),
        )
        self.location = DealerLocation.objects.create(
            dealer=self.dealer,
            name="Main Stand",
            area="Wuse 2, Abuja",
            address="12 Ahmadu Bello Way",
            is_primary=True,
        )
        self.staff = StaffUser.objects.create_user(
            email="owner@email-dealer.test",
            password="strong-pass-123",
            name="Dealer Owner",
            dealer=self.dealer,
            preferred_location=self.location,
        )
        self.vehicle = Vehicle.objects.create(
            dealer=self.dealer,
            location=self.location,
            slug="lexus-rc-350",
            make="Lexus",
            model="RC 350",
            trim="F Sport",
            year=2020,
            price_ngn=38500000,
            mileage_km=48200,
            transmission=Vehicle.Transmission.AUTOMATIC,
            fuel=Vehicle.Fuel.PETROL,
            body_type=Vehicle.BodyType.COUPE,
            drivetrain=Vehicle.Drivetrain.RWD,
            condition_grade=Vehicle.ConditionGrade.GOOD,
            status=Vehicle.Status.AVAILABLE,
            listing_verification_status=Vehicle.ListingVerificationStatus.APPROVED,
            feed_ready=True,
        )

    @patch("apps.notifications.emails.EmailMultiAlternatives")
    def test_dealer_email_verification_template(self, email_cls):
        send_dealer_email_verification_email(str(self.staff.id), "verify-token-1234567890")
        email_cls.assert_called_once()
        self.assertEqual(email_cls.call_args.kwargs["subject"], "Confirm your email to start selling cars")
        email_cls.return_value.send.assert_called_once()

    @patch("apps.notifications.emails.EmailMultiAlternatives")
    def test_new_lead_alert_template(self, email_cls):
        lead = Lead.objects.create(
            dealer=self.dealer,
            location=self.location,
            vehicle=self.vehicle,
            name="Emeka",
            phone="+2348044444444",
            message="Is the price negotiable?",
        )
        send_new_lead_alert_email(str(lead.id))
        email_cls.assert_called_once()
        self.assertIn("Emeka is interested in your Lexus RC 350", email_cls.call_args.kwargs["subject"])
        email_cls.return_value.send.assert_called_once()

    @patch("apps.notifications.emails.EmailMultiAlternatives")
    def test_booking_confirmation_template(self, email_cls):
        booking = Booking.objects.create(
            vehicle=self.vehicle,
            dealer=self.dealer,
            location=self.location,
            buyer_name="Ada",
            buyer_phone="+2348055555555",
            buyer_email="ada@buyer.test",
            scheduled_at=timezone.now() + timedelta(days=2),
            status=Booking.Status.CONFIRMED,
        )
        send_booking_confirmation_email(str(booking.id))
        email_cls.assert_called_once()
        self.assertEqual(email_cls.call_args.kwargs["subject"], "Your inspection is confirmed")
        email_cls.return_value.send.assert_called_once()

    @patch("apps.notifications.emails.EmailMultiAlternatives")
    def test_dealer_verification_success_template(self, email_cls):
        send_dealer_verification_success_email(str(self.dealer.id))
        email_cls.assert_called_once()
        self.assertIn("GrandView Motors is now verified", email_cls.call_args.kwargs["subject"])
        email_cls.return_value.send.assert_called_once()

    @patch("apps.notifications.emails.EmailMultiAlternatives")
    def test_listing_review_issue_template(self, email_cls):
        issue = VehicleReviewIssue.objects.create(
            vehicle=self.vehicle,
            reviewer=self.staff,
            category=VehicleReviewIssue.Category.DETAILS,
            message="Fix the mileage.",
        )
        send_listing_review_issue_email(str(self.vehicle.id), str(issue.id))
        email_cls.assert_called_once()
        self.assertIn("Action needed", email_cls.call_args.kwargs["subject"])
        email_cls.return_value.send.assert_called_once()

    @patch("apps.notifications.emails.EmailMultiAlternatives")
    def test_platform_message_template(self, email_cls):
        send_platform_message_emails(str(self.dealer.id), "Action needed", "Please update your documents.")
        email_cls.assert_called_once()
        self.assertEqual(email_cls.call_args.kwargs["subject"], "Action needed")
        email_cls.return_value.send.assert_called_once()

    @patch("apps.notifications.emails.EmailMultiAlternatives")
    def test_staff_invite_template(self, email_cls):
        send_staff_invite_email(str(self.staff.id), "invite-token-1234567890", "dealer")
        email_cls.assert_called_once()
        self.assertIn("invited", email_cls.call_args.kwargs["subject"].lower())
        email_cls.return_value.send.assert_called_once()
