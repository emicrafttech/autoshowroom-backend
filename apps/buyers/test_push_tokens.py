from apps.buyers.models import BuyerPushDevice
from apps.buyers.tests import BuyerChatTests


class BuyerPushTokenTests(BuyerChatTests):
    def test_push_token_upsert_and_delete(self):
        upsert_response = self.client.put(
            "/v1/buyers/push-token",
            {"token": "fcm-test-token", "platform": "android"},
            format="json",
        )
        self.assertEqual(upsert_response.status_code, 200)
        self.assertEqual(BuyerPushDevice.objects.count(), 1)

        delete_response = self.client.delete(
            "/v1/buyers/push-token",
            {"token": "fcm-test-token"},
            format="json",
        )
        self.assertEqual(delete_response.status_code, 204)
        self.assertEqual(BuyerPushDevice.objects.count(), 0)
