import unittest

from business_discovery.evidence import canonical_domain, capture_url, content_fingerprint, domain_matches, validate_fields


class EvidenceValidationTests(unittest.TestCase):
    def test_domain_is_normalized_and_subdomains_are_scoped(self):
        self.assertEqual(canonical_domain("HTTPS://Partners.Example.com/path"), "partners.example.com")
        self.assertTrue(domain_matches("example.com", "partners.example.com"))
        self.assertFalse(domain_matches("example.com", "example.com.attacker.test"))

    def test_capture_url_rejects_non_web_and_credentials(self):
        self.assertEqual(capture_url("https://example.com/a")[1], "example.com")
        with self.assertRaises(ValueError): capture_url("file:///tmp/company")
        with self.assertRaises(ValueError): capture_url("https://user:secret@example.com")

    def test_fields_respect_policy_and_require_name(self):
        fields = validate_fields({"name": "Acme", "city": "Pune"}, ["name", "city"])
        self.assertEqual(fields["name"], "Acme")
        with self.assertRaises(ValueError): validate_fields({"name": "Acme", "phone": "1"}, ["name"])
        with self.assertRaises(ValueError): validate_fields({"city": "Pune"}, ["name", "city"])

    def test_fingerprint_is_deterministic(self):
        first = content_fingerprint("https://example.com", {"name": "Acme", "city": "Pune"})
        second = content_fingerprint("https://example.com", {"city": "Pune", "name": "Acme"})
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
