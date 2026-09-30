import unittest

from business_discovery.alerts import AlertWebhook
from business_discovery.auth import TokenService, hash_password, verify_password


class SecurityTests(unittest.TestCase):
    def test_password_hash_and_verification(self):
        stored = hash_password("a-long-unique-test-password")
        self.assertTrue(verify_password("a-long-unique-test-password", stored))
        self.assertFalse(verify_password("incorrect-password", stored))

    def test_tokens_expire_and_tampering_fails(self):
        service = TokenService("x" * 32)
        token = service.issue("user", "workspace", "viewer", ttl_seconds=60)
        self.assertEqual(service.verify(token)["role"], "viewer")
        self.assertIsNone(service.verify(token + "x"))
        self.assertIsNone(service.verify(service.issue("user", "workspace", "viewer", ttl_seconds=-1)))

    def test_webhook_is_opt_in_and_requires_safe_url(self):
        self.assertFalse(AlertWebhook("").enabled)
        with self.assertRaises(ValueError): AlertWebhook("http://alerts.example")
        with self.assertRaises(ValueError): AlertWebhook("https://secret@example.test/hook")
        self.assertTrue(AlertWebhook("https://alerts.example/hook").enabled)


if __name__ == "__main__":
    unittest.main()
