from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import StaffUser
from apps.buyers.auth import create_buyer_token
from apps.buyers.models import Buyer, BuyerConversation, BuyerMessage, BuyerOtp
from apps.dealers.models import Dealer, DealerLocation
from apps.vehicles.models import Vehicle
from apps.vehicles.storage import PresignedUpload


class BuyerChatTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.dealer = Dealer.objects.create(
            slug="prime-motors",
            name="Prime Motors",
            legal_name="Prime Motors Limited",
            area="Wuse",
            phone="+2348011111111",
            verified_badge=True,
        )
        self.location = DealerLocation.objects.create(
            dealer=self.dealer,
            name="Main Stand",
            area="Wuse",
            district_slug="wuse",
            is_primary=True,
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
        self.buyer = Buyer.objects.create(phone="+2348090000000")
        self.token = create_buyer_token(self.buyer)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")

    def test_open_chat_creates_conversation_and_accepts_initial_message(self):
        response = self.client.post(
            f"/v1/buyers/chat/vehicles/{self.vehicle.id}",
            {"message": "Hi, is this still available?"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()["data"]
        self.assertEqual(BuyerConversation.objects.count(), 1)
        self.assertEqual(data["messages"][0]["body"], "Hi, is this still available?")
        self.assertEqual(data["messages"][0]["senderType"], "buyer")
        conversation_id = data["id"]

        second = self.client.post(
            f"/v1/buyers/chat/vehicles/{self.vehicle.id}",
            {"message": "Another"},
            format="json",
        )
        self.assertEqual(second.status_code, 201)
        self.assertEqual(BuyerConversation.objects.count(), 1)
        self.assertEqual(second.json()["data"]["id"], conversation_id)

    def test_chat_detail_returns_messages(self):
        opened = self.client.post(
            f"/v1/buyers/chat/vehicles/{self.vehicle.id}",
            {"message": "Hello"},
            format="json",
        )
        conversation_id = opened.json()["data"]["id"]

        detail = self.client.get(f"/v1/buyers/chat/conversations/{conversation_id}")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["data"]["id"], conversation_id)
        self.assertEqual(len(detail.json()["data"]["messages"]), 1)

    def test_send_message_appends_and_notifies(self):
        opened = self.client.post(
            f"/v1/buyers/chat/vehicles/{self.vehicle.id}",
            format="json",
        )
        conversation_id = opened.json()["data"]["id"]

        send = self.client.post(
            f"/v1/buyers/chat/conversations/{conversation_id}/messages",
            {"body": "Can I book an inspection?"},
            format="json",
        )
        self.assertEqual(send.status_code, 201)
        self.assertEqual(BuyerMessage.objects.count(), 1)
        self.assertEqual(
            send.json()["data"]["messages"][-1]["body"],
            "Can I book an inspection?",
        )

    @patch("apps.buyers.chat_service.broadcast_chat_message")
    def test_open_chat_broadcasts_initial_message(self, broadcast):
        self.client.post(
            f"/v1/buyers/chat/vehicles/{self.vehicle.id}",
            {"message": "Is it still available?"},
            format="json",
        )
        broadcast.assert_called_once()

    @patch("apps.buyers.chat_service.broadcast_chat_message")
    def test_send_message_broadcasts_to_realtime(self, broadcast):
        opened = self.client.post(
            f"/v1/buyers/chat/vehicles/{self.vehicle.id}",
            format="json",
        )
        conversation_id = opened.json()["data"]["id"]

        self.client.post(
            f"/v1/buyers/chat/conversations/{conversation_id}/messages",
            {"body": "Can I book an inspection?"},
            format="json",
        )
        broadcast.assert_called_once()

    def test_send_message_rejects_blank_body(self):
        opened = self.client.post(
            f"/v1/buyers/chat/vehicles/{self.vehicle.id}",
            format="json",
        )
        conversation_id = opened.json()["data"]["id"]

        send = self.client.post(
            f"/v1/buyers/chat/conversations/{conversation_id}/messages",
            {"body": "   "},
            format="json",
        )
        self.assertEqual(send.status_code, 400)

    @patch("apps.buyers.chat_service.create_presigned_upload")
    def test_chat_attachment_upload_session_returns_presigned_urls(self, create_upload):
        from apps.vehicles.storage import PresignedUpload

        create_upload.return_value = PresignedUpload(
            key="chat-attachments/test/image.jpg",
            upload_url="https://upload.test/chat",
            public_url="https://cdn.test/chat/image.jpg",
        )
        opened = self.client.post(
            f"/v1/buyers/chat/vehicles/{self.vehicle.id}",
            format="json",
        )
        conversation_id = opened.json()["data"]["id"]

        response = self.client.post(
            f"/v1/buyers/chat/conversations/{conversation_id}/attachments/upload-session",
            {"contentType": "image/jpeg", "fileName": "photo.jpg"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["data"]["publicUrl"], "https://cdn.test/chat/image.jpg")

    @patch("apps.buyers.chat_service.broadcast_chat_message")
    def test_send_image_attachment_without_body(self, broadcast):
        opened = self.client.post(
            f"/v1/buyers/chat/vehicles/{self.vehicle.id}",
            format="json",
        )
        conversation_id = opened.json()["data"]["id"]

        send = self.client.post(
            f"/v1/buyers/chat/conversations/{conversation_id}/messages",
            {"attachmentUrl": "https://cdn.test/chat/image.jpg"},
            format="json",
        )
        self.assertEqual(send.status_code, 201)
        message = send.json()["data"]["messages"][-1]
        self.assertEqual(message["attachmentUrl"], "https://cdn.test/chat/image.jpg")
        self.assertEqual(message["body"], "")
        broadcast.assert_called_once()

    def test_chat_requires_buyer_token(self):
        self.client.credentials()
        response = self.client.post(
            f"/v1/buyers/chat/vehicles/{self.vehicle.id}",
            format="json",
        )
        self.assertIn(response.status_code, (401, 403))

    def test_chat_list_shows_buyer_conversations(self):
        self.client.post(
            f"/v1/buyers/chat/vehicles/{self.vehicle.id}",
            {"message": "Hello"},
            format="json",
        )
        response = self.client.get("/v1/buyers/chat")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["count"], 1)

    def test_public_vehicle_exposes_trust_check_fields(self):
        response = self.client.get(f"/v1/feed/vehicles/{self.vehicle.id}")
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertTrue(data["feedReady"])
        self.assertIn("updatedAt", data)


class DealerChatReadTests(TestCase):
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
        self.vehicle = Vehicle.objects.create(
            dealer=self.dealer,
            location=self.location,
            slug="lexus-gx",
            make="Lexus",
            model="GX",
            year=2026,
            price_ngn=27000000,
            mileage_km=43000,
            transmission=Vehicle.Transmission.AUTOMATIC,
            fuel=Vehicle.Fuel.PETROL,
            colour="White",
            body_type=Vehicle.BodyType.SUV,
            drivetrain=Vehicle.Drivetrain.AWD,
            condition_grade=Vehicle.ConditionGrade.GOOD,
            status=Vehicle.Status.AVAILABLE,
            listing_verification_status=Vehicle.ListingVerificationStatus.APPROVED,
            feed_ready=True,
            published_at=timezone.now(),
        )
        self.buyer = Buyer.objects.create(phone="+2348090000000", name="Adefemi Oseni")
        self.conversation = BuyerConversation.objects.create(
            buyer=self.buyer,
            dealer=self.dealer,
            vehicle=self.vehicle,
            last_message_at=timezone.now(),
        )
        BuyerMessage.objects.create(
            conversation=self.conversation,
            sender_type=BuyerMessage.SenderType.BUYER,
            body="Best price?",
        )
        self.staff = StaffUser.objects.create_user(
            email="owner@example.com",
            password="strong-pass-123",
            name="Owner User",
            role=StaffUser.Role.OWNER,
            dealer=self.dealer,
            preferred_location=self.location,
        )
        self.client.force_authenticate(user=self.staff)

    def test_mark_read_clears_unread_without_dealer_reply(self):
        response = self.client.post(f"/v1/dealers/me/chats/{self.conversation.id}/read")

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertIsNotNone(data["dealerLastReadAt"])
        self.conversation.refresh_from_db()
        self.assertIsNotNone(self.conversation.dealer_last_read_at)


class BuyerChatMarkReadTests(TestCase):
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
        self.vehicle = Vehicle.objects.create(
            dealer=self.dealer,
            location=self.location,
            slug="lexus-gx",
            make="Lexus",
            model="GX",
            year=2026,
            price_ngn=27000000,
            mileage_km=43000,
            transmission=Vehicle.Transmission.AUTOMATIC,
            fuel=Vehicle.Fuel.PETROL,
            colour="White",
            body_type=Vehicle.BodyType.SUV,
            drivetrain=Vehicle.Drivetrain.AWD,
            condition_grade=Vehicle.ConditionGrade.GOOD,
            status=Vehicle.Status.AVAILABLE,
            listing_verification_status=Vehicle.ListingVerificationStatus.APPROVED,
            feed_ready=True,
            published_at=timezone.now(),
        )
        self.buyer = Buyer.objects.create(phone="+2348090000000", name="Adefemi Oseni")
        self.conversation = BuyerConversation.objects.create(
            buyer=self.buyer,
            dealer=self.dealer,
            vehicle=self.vehicle,
            last_message_at=timezone.now(),
        )
        BuyerMessage.objects.create(
            conversation=self.conversation,
            sender_type=BuyerMessage.SenderType.DEALER,
            body="Best price?",
        )
        self.token = create_buyer_token(self.buyer)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")

    def test_mark_read_clears_unread_without_buyer_reply(self):
        response = self.client.post(
            f"/v1/buyers/chat/conversations/{self.conversation.id}/read"
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertIsNotNone(data["buyerLastReadAt"])
        self.conversation.refresh_from_db()
        self.assertIsNotNone(self.conversation.buyer_last_read_at)


class BuyerSignInTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def _start_and_verify(self, phone, name):
        start = self.client.post(
            "/v1/buyers/sign-in/start",
            {"phone": phone, "name": name},
            format="json",
        )
        self.assertEqual(start.status_code, 201)
        code = BuyerOtp.objects.filter(phone=phone).latest("created_at").code
        verify = self.client.post(
            "/v1/buyers/sign-in/verify",
            {"phone": phone, "code": code},
            format="json",
        )
        return verify

    def test_verify_persists_name_on_new_buyer(self):
        verify = self._start_and_verify("+2348090001111", "Chinedu Okafor")
        self.assertEqual(verify.status_code, 200)
        buyer = Buyer.objects.get(phone="+2348090001111")
        self.assertEqual(buyer.name, "Chinedu Okafor")
        self.assertEqual(verify.json()["data"]["buyer"]["name"], "Chinedu Okafor")

    def test_verify_does_not_overwrite_existing_name(self):
        Buyer.objects.create(phone="+2348090002222", name="Existing Name")
        verify = self._start_and_verify("+2348090002222", "Someone Else")
        self.assertEqual(verify.status_code, 200)
        buyer = Buyer.objects.get(phone="+2348090002222")
        self.assertEqual(buyer.name, "Existing Name")

    def test_verify_without_name_leaves_name_blank(self):
        verify = self._start_and_verify("+2348090003333", "")
        self.assertEqual(verify.status_code, 200)
        buyer = Buyer.objects.get(phone="+2348090003333")
        self.assertEqual(buyer.name, "")

    def test_start_sign_in_without_name_field(self):
        start = self.client.post(
            "/v1/buyers/sign-in/start",
            {"phone": "+2348090004444"},
            format="json",
        )
        self.assertEqual(start.status_code, 201)

    def test_start_sign_in_with_null_name(self):
        start = self.client.post(
            "/v1/buyers/sign-in/start",
            {"phone": "+2348090005555", "name": None},
            format="json",
        )
        self.assertEqual(start.status_code, 201)

    def test_session_refresh_returns_buyer_and_token(self):
        buyer = Buyer.objects.create(phone="+2348090006666", name="Restored Buyer")
        token = create_buyer_token(buyer)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        response = self.client.post("/v1/buyers/session/refresh", {}, format="json")

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertIn("token", data)
        self.assertEqual(data["buyer"]["phone"], "+2348090006666")
        self.assertEqual(data["buyer"]["name"], "Restored Buyer")


class BuyerProfileTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.buyer = Buyer.objects.create(
            phone="+2348090004444",
            name="Adefemi Oseni",
            email="adefemi.o@example.com",
        )
        self.token = create_buyer_token(self.buyer)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")

    def test_get_profile_returns_extra_fields(self):
        response = self.client.get("/v1/buyers/profile")
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["name"], "Adefemi Oseni")
        self.assertIn("bio", data)
        self.assertIn("location", data)
        self.assertIn("photoUrl", data)

    def test_patch_updates_name_email_bio_and_location(self):
        response = self.client.patch(
            "/v1/buyers/profile",
            {
                "name": "Adefemi O.",
                "email": "adefemi@updated.com",
                "bio": "Looking for a clean foreign-used SUV in Abuja.",
                "location": "Abuja, Nigeria",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["name"], "Adefemi O.")
        self.assertEqual(data["email"], "adefemi@updated.com")
        self.assertEqual(data["bio"], "Looking for a clean foreign-used SUV in Abuja.")
        self.assertEqual(data["location"], "Abuja, Nigeria")
        buyer = Buyer.objects.get(pk=self.buyer.pk)
        self.assertEqual(buyer.bio, "Looking for a clean foreign-used SUV in Abuja.")
        self.assertEqual(buyer.location, "Abuja, Nigeria")

    def test_patch_does_not_change_phone(self):
        response = self.client.patch(
            "/v1/buyers/profile",
            {"phone": "+2348090009999"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        buyer = Buyer.objects.get(pk=self.buyer.pk)
        self.assertEqual(buyer.phone, "+2348090004444")

    def test_photo_upload_session_requires_buyer_token(self):
        self.client.credentials()
        response = self.client.post(
            "/v1/buyers/profile/photo/upload-session",
            {"contentType": "image/jpeg", "fileName": "avatar.jpg"},
            format="json",
        )
        self.assertIn(response.status_code, (401, 403))

    def test_photo_upload_session_requires_image_content_type(self):
        response = self.client.post(
            "/v1/buyers/profile/photo/upload-session",
            {"contentType": "application/pdf", "fileName": "doc.pdf"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    @patch("apps.buyers.views.create_presigned_upload")
    def test_photo_upload_session_returns_presigned_urls(self, mock_presign):
        mock_presign.return_value = PresignedUpload(
            key="buyer-photos/some-id/abc.jpg",
            upload_url="https://s3.example/upload/abc.jpg",
            public_url="https://cdn.example/buyer-photos/some-id/abc.jpg",
        )

        response = self.client.post(
            "/v1/buyers/profile/photo/upload-session",
            {"contentType": "image/jpeg", "fileName": "avatar.jpg"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()["data"]
        self.assertEqual(data["uploadUrl"], "https://s3.example/upload/abc.jpg")
        self.assertEqual(data["publicUrl"], "https://cdn.example/buyer-photos/some-id/abc.jpg")
        self.assertIn("buyer-photos", data["s3Key"])
        self.assertIn("expiresAt", data)
        mock_presign.assert_called_once()
        args, _ = mock_presign.call_args
        self.assertTrue(args[0].startswith("buyer-photos/"))
        self.assertEqual(args[1], "image/jpeg")

    @patch("apps.buyers.views.create_presigned_upload")
    def test_photo_link_is_persisted_via_profile_patch(self, mock_presign):
        public_url = "https://cdn.example/buyer-photos/some-id/abc.jpg"
        mock_presign.return_value = PresignedUpload(
            key="buyer-photos/some-id/abc.jpg",
            upload_url="https://s3.example/upload/abc.jpg",
            public_url=public_url,
        )

        session = self.client.post(
            "/v1/buyers/profile/photo/upload-session",
            {"contentType": "image/jpeg", "fileName": "avatar.jpg"},
            format="json",
        )
        self.assertEqual(session.status_code, 201)

        # The client uploads directly to S3 at uploadUrl, then saves the link via PATCH.
        patch = self.client.patch(
            "/v1/buyers/profile",
            {"photoUrl": public_url},
            format="json",
        )
        self.assertEqual(patch.status_code, 200)
        self.assertEqual(patch.json()["data"]["photoUrl"], public_url)
        buyer = Buyer.objects.get(pk=self.buyer.pk)
        self.assertEqual(buyer.photo_url, public_url)
