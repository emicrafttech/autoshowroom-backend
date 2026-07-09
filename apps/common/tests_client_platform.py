from django.test import RequestFactory, SimpleTestCase, override_settings

from apps.common.client_platform import (
    buyer_token_ttl_seconds,
    dealer_refresh_lifetime,
    is_mobile_client,
)


class ClientPlatformTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_is_mobile_client_detects_header(self):
        request = self.factory.get("/", HTTP_X_CLIENT_PLATFORM="mobile")
        self.assertTrue(is_mobile_client(request))

        desktop = self.factory.get("/")
        self.assertFalse(is_mobile_client(desktop))

    @override_settings(
        JWT_MOBILE_REFRESH_TOKEN_DAYS=365,
        SIMPLE_JWT={"REFRESH_TOKEN_LIFETIME": __import__("datetime").timedelta(days=7)},
        BUYER_TOKEN_TTL_SECONDS=604800,
        BUYER_MOBILE_TOKEN_TTL_SECONDS=31536000,
    )
    def test_ttl_helpers_split_mobile_and_desktop(self):
        self.assertEqual(dealer_refresh_lifetime(mobile=False).days, 7)
        self.assertEqual(dealer_refresh_lifetime(mobile=True).days, 365)
        self.assertEqual(buyer_token_ttl_seconds(mobile=False), 604800)
        self.assertEqual(buyer_token_ttl_seconds(mobile=True), 31536000)
