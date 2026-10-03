import unittest

from app.tools.base import ToolError
from app.tools.ssrf import parse_legacy_ipv4, validate_url

PUBLIC = "93.184.216.34"
resolver = lambda host, port: {"example.com": [PUBLIC], "mixed.example": [PUBLIC, "10.0.0.5"],
                               "internal.example": ["192.168.1.10"], "v6.example": ["2606:2800:220:1::1"],
                               "mapped.example": ["::ffff:10.0.0.1"], "empty.example": []}.get(host, [PUBLIC])


class SSRFTests(unittest.TestCase):
    def blocked(self, url):
        with self.assertRaises(ToolError, msg=url) as cm:
            validate_url(url, resolver)
        return cm.exception

    def test_allows_public_targets_and_pins_ips(self):
        t = validate_url("https://example.com/a?b=c", resolver)
        self.assertEqual((t.host, t.port, t.ips, t.path), ("example.com", 443, (PUBLIC,), "/a?b=c"))
        self.assertEqual(validate_url("http://93.184.216.34:8080/x", resolver).port, 8080)
        self.assertEqual(validate_url("https://example.com./", resolver).host, "example.com")
        self.assertTrue(validate_url("https://[2606:2800:220:1::1]/", resolver))
        self.assertTrue(validate_url("https://v6.example/", resolver))

    def test_localhost_and_internal_names(self):
        for u in ("http://localhost/", "http://LOCALHOST./", "http://foo.localhost/", "http://db.internal/", "http://printer.local/"):
            self.assertEqual(self.blocked(u).category, "security")

    def test_ipv4_private_loopback_linklocal_reserved(self):
        for u in ("http://127.0.0.1/", "http://127.9.9.9/", "http://10.1.2.3/", "http://172.16.0.1/", "http://172.31.255.255/",
                  "http://192.168.0.1/", "http://169.254.169.254/", "http://100.100.100.200/", "http://100.64.0.1/",
                  "http://0.0.0.0/", "http://224.0.0.1/", "http://240.0.0.1/", "http://255.255.255.255/"):
            self.assertEqual(self.blocked(u).category, "security", u)

    def test_ipv6_loopback_private_linklocal_and_embedded_v4(self):
        for u in ("http://[::1]/", "http://[::]/", "http://[fe80::1]/", "http://[fd00:ec2::254]/", "http://[fc00::1]/",
                  "http://[ff02::1]/", "http://[::ffff:127.0.0.1]/", "http://[::ffff:7f00:1]/", "http://[::ffff:10.0.0.1]/",
                  "http://[::7f00:1]/", "http://[2002:7f00:1::]/", "http://[64:ff9b::7f00:1]/", "http://[2001::1]/"):
            self.assertEqual(self.blocked(u).category, "security", u)

    def test_unusual_ip_representations(self):
        for u in ("http://2130706433/", "http://0x7f000001/", "http://0x7f.0.0.1/", "http://0177.0.0.1/", "http://127.1/",
                  "http://017700000001/", "http://0/", "http://3232235777/"):
            self.assertEqual(self.blocked(u).category, "security", u)
        self.assertEqual(parse_legacy_ipv4("127.1"), "127.0.0.1")
        self.assertEqual(parse_legacy_ipv4("0x7f.1"), "127.0.0.1")
        self.assertIsNone(parse_legacy_ipv4("example.com"))
        self.assertIsNone(parse_legacy_ipv4("256.1.1.1"))

    def test_all_resolved_addresses_are_checked(self):
        for u in ("http://mixed.example/", "http://internal.example/", "http://mapped.example/"):
            self.assertEqual(self.blocked(u).category, "security")
        self.assertEqual(self.blocked("http://empty.example/").category, "network")

    def test_schemes(self):
        for u in ("ftp://example.com/", "file:///etc/passwd", "gopher://example.com/", "data:text/html,<b>x</b>",
                  "javascript:alert(1)", "ws://example.com/", "//example.com/"):
            self.assertEqual(self.blocked(u).category, "security", u)

    def test_malformed_credentials_ports_and_control_chars(self):
        for u in ("", "http://", "http:///path", "http://exa mple.com/", "http://example.com:99999/", "http://example.com:abc/",
                  "http://example.com:22/", "http://example.com:6379/", "http://exa\x00mple.com/", "http://example.com\\@evil/",
                  "http://user:pw@example.com/", "http://user@example.com/", "http://example.com@127.0.0.1/",
                  "http://[::1/", "http://x" + "a" * 3000, None, 123, "http://exa%mple.com/"):
            self.blocked(u)

    def test_error_messages_do_not_echo_the_url(self):
        e = self.blocked("http://user:topsecret@example.com/")
        self.assertNotIn("topsecret", e.message)


if __name__ == "__main__":
    unittest.main()
