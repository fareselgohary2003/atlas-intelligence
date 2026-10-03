import json
import unittest

from app.agents.state import ConfigError
from app.tools.base import ToolError
from app.tools.search import BraveSearchProvider, SearchOptions, create_search_provider

# NOTE: this fixture encodes OUR ASSUMPTION of Brave's response shape. It is not a recorded live response.
BODY = json.dumps({"web": {"results": [
    {"title": "A &amp; B <b>Report</b>", "url": "https://stats.gov.sa/r", "description": "Size <strong>12</strong> &amp; growth",
     "page_age": "2024-05-01T10:00:00", "meta_url": {"hostname": "stats.gov.sa"}},
    {"title": "bad scheme", "url": "javascript:alert(1)"}, {"title": "no url"}, "garbage",
    {"title": "Second", "url": "http://example.com/x"}]}}).encode()


def getter(status=200, body=BODY, log=None):
    def g(url, headers, timeout):
        if log is not None:
            log.append((url, headers))
        return status, body
    return g


class SearchTests(unittest.TestCase):
    def test_parsing_sanitizing_and_request(self):
        log = []
        p = BraveSearchProvider("KEY", getter(log=log))
        res = p.search("saudi saas", SearchOptions(count=5, country="SA", freshness="year"))
        self.assertEqual([r.url for r in res], ["https://stats.gov.sa/r", "http://example.com/x"])
        self.assertEqual((res[0].title, res[0].snippet, res[0].publisher), ("A & B Report", "Size 12 & growth", "stats.gov.sa"))
        self.assertEqual((res[0].published_at.year, res[0].rank, res[1].rank), (2024, 1, 2))
        self.assertIn("count=5", log[0][0])
        self.assertIn("country=SA", log[0][0])
        self.assertEqual(log[0][1]["X-Subscription-Token"], "KEY")

    def test_provider_failures_are_categorized(self):
        cases = ((429, b"", "upstream_transient", True), (503, b"", "upstream_transient", True),
                 (400, b"", "upstream", False), (200, b"not json", "upstream", False), (200, b'{"web":{}}', "upstream", False))
        for status, body, cat, retry in cases:
            with self.assertRaises(ToolError) as cm:
                BraveSearchProvider("K", getter(status, body)).search("query", SearchOptions())
            self.assertEqual((cm.exception.category, cm.exception.retryable), (cat, retry), (status, body))
        with self.assertRaises(ConfigError):
            BraveSearchProvider("K", getter(401)).search("query", SearchOptions())

    def test_missing_configuration_fails_explicitly_with_no_fallback(self):
        for name, key in ((None, "k"), ("", "k"), ("nonexistent", "k"), ("brave", None), ("brave", "")):
            with self.assertRaises(ConfigError, msg=(name, key)):
                create_search_provider(name, key)
        self.assertEqual(create_search_provider("brave", "k").name, "brave")


if __name__ == "__main__":
    unittest.main()
