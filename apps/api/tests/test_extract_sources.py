import unittest
from datetime import timezone

from app.tools.base import ToolError
from app.tools.extract import extract_content, parse_date
from app.tools.sources import SourceDeduper, classify_source_type, content_hash, make_candidate, normalize_url

ARTICLE = """<!doctype html><html lang="en"><head><title> Saudi SaaS Report </title>
<meta property="og:site_name" content="Example Research"><meta name="author" content="A. Writer">
<meta property="article:published_time" content="2024-03-05T10:00:00Z">
<link rel="canonical" href="https://www.example.com/reports/saas?utm_source=x"></head>
<body><nav>Home About MENU-JUNK</nav><header><h1>Saudi SaaS Report</h1></header>
<article><p>%s</p><p>Second   paragraph
with   spaces.</p><a href="/next">next</a><a href="javascript:void(0)">x</a><a href="mailto:a@b.c">m</a>
<a href="https://other.org/x#frag">o</a></article><script>var junk=1;</script><footer>FOOTER-JUNK</footer></body></html>""" % ("Market data. " * 30)


class ExtractTests(unittest.TestCase):
    def test_article_extraction(self):
        c = extract_content(ARTICLE, "text/html", "https://example.com/reports/saas")
        self.assertEqual((c.title, c.language, c.metadata["author"]), ("Saudi SaaS Report", "en", "A. Writer"))
        self.assertNotIn("JUNK", c.text)
        self.assertNotIn("var junk", c.text)
        self.assertIn("Second paragraph with spaces.", c.text)
        self.assertEqual(c.published_at.year, 2024)
        self.assertEqual(c.canonical_url, "https://www.example.com/reports/saas?utm_source=x")
        self.assertEqual(c.links, ["https://example.com/next", "https://other.org/x"])
        self.assertFalse(c.is_empty)

    def test_cross_host_canonical_is_rejected(self):
        html = '<html><head><link rel="canonical" href="https://bank.com/"></head><body>' + "text " * 30 + "</body></html>"
        c = extract_content(html, "text/html", "https://evil.example/page")
        self.assertIsNone(c.canonical_url)
        self.assertTrue(c.metadata["canonical_rejected"])

    def test_json_ld_date_and_title_fallbacks(self):
        html = ('<html><head><meta property="og:title" content="OG Title"><script type="application/ld+json">'
                '{"@graph":[{"@type":"Article","datePublished":"2023-07-01"}]}</script></head><body>' + "word " * 30 + "</body></html>")
        c = extract_content(html, "text/html", "https://a.com/")
        self.assertEqual((c.title, c.published_at.month), ("OG Title", 7))
        c = extract_content("<body><h1>Only H1</h1>" + "x " * 40, "text/html", "https://a.com/")
        self.assertEqual(c.title, "Only H1")

    def test_degenerate_inputs(self):
        for html in ("", "   ", "<html></html>", "<script>only()</script>"):
            self.assertTrue(extract_content(html, "text/html", "https://a.com/").is_empty)
        c = extract_content("<div><p>unclosed <b>bold <i>nest<table><td>cell" + " filler" * 20, "text/html", "https://a.com/")
        self.assertIn("cell", c.text)  # malformed markup still yields text
        big = extract_content("<p>" + "a " * 2_500_000, "text/html", "https://a.com/")
        self.assertLessEqual(len(big.text), 200_000)

    def test_unsupported_and_binary(self):
        for ct in ("application/pdf", "image/png", ""):
            with self.assertRaises(ToolError):
                extract_content("x", ct, "https://a.com/")
        with self.assertRaises(ToolError):
            extract_content("\x00\x01binary", "text/html", "https://a.com/")

    def test_plain_text_and_link_cap(self):
        self.assertEqual(extract_content("a\n\n\n\nb", "text/plain", "https://a.com/").text, "a\n\nb")
        html = "<body>" + "".join(f'<a href="/p{i}">l</a>' for i in range(200)) + "</body>"
        self.assertEqual(len(extract_content(html, "text/html", "https://a.com/").links), 50)

    def test_parse_date(self):
        self.assertEqual(parse_date("2024-03-05").tzinfo, timezone.utc)
        self.assertEqual(parse_date("Tue, 05 Mar 2024 10:00:00 GMT").day, 5)
        for bad in (None, "", "yesterday", "0001-01-01", "9999-01-01", 5):
            self.assertIsNone(parse_date(bad))


class SourceTests(unittest.TestCase):
    def test_normalize_url(self):
        n = normalize_url
        self.assertEqual(n("HTTP://Example.COM:80/a/../b/?utm_source=x&b=2&a=1#frag"), "http://example.com/b?a=1&b=2")
        self.assertEqual(n("https://example.com:443"), "https://example.com/")
        self.assertEqual(n("https://example.com:8443/x/"), "https://example.com:8443/x")
        self.assertEqual(n("https://example.com/p?gclid=1&fbclid=2"), "https://example.com/p")
        self.assertEqual(n("https://münchen.de/"), "https://xn--mnchen-3ya.de/")
        self.assertEqual(n("https://example.com/x?q=a b"), n("https://example.com/x?q=a+b"))

    def test_hash_and_type_heuristics(self):
        self.assertEqual(content_hash("Hello   World\n"), content_hash("hello world"))
        self.assertNotEqual(content_hash("a"), content_hash("b"))
        for d, t in (("stats.gov.sa", "government"), ("data.gov", "government"), ("mit.edu", "academic"),
                     ("ox.ac.uk", "academic"), ("reddit.com", "forum"), ("old.reddit.com", "forum"), ("acme.com", "other")):
            self.assertEqual(classify_source_type(d), t, d)

    def test_candidate_and_dedup(self):
        a = make_candidate(url="https://www.Example.com/r?utm_x=1#s", text="Alpha beta gamma", published_at=parse_date("2024-01-01"))
        b = make_candidate(url="https://example.com/r", text="different words")
        c = make_candidate(url="https://mirror.org/copy", text="alpha   BETA gamma", is_demo=True)
        d = SourceDeduper()
        self.assertEqual((a.domain, a.publisher, a.url), ("example.com", "example.com", "https://www.example.com/r"))
        self.assertIsNone(d.register(a))
        self.assertEqual(d.register(make_candidate(url="https://www.example.com/r", text="zzz"))[0], "url")
        self.assertEqual(d.register(c)[0], "content")
        self.assertTrue(c.is_demo and not a.is_demo)
        self.assertIsNone(d.register(make_candidate(url="https://other.com/x", text="unique text")))
        self.assertIsNotNone(a.retrieved_at.tzinfo)
        with self.assertRaises(ValueError):
            make_candidate(url="https://a.com/", text="x", source_type="blog")
        self.assertIsNotNone(b)


if __name__ == "__main__":
    unittest.main()
