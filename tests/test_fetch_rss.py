#!/usr/bin/env python3
"""Tests for fetch-rss.py parsing helpers."""

import importlib.util
import unittest
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
MODULE_PATH = SCRIPTS_DIR / "fetch-rss.py"

spec = importlib.util.spec_from_file_location("fetch_rss", MODULE_PATH)
fetch_rss = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetch_rss)


class TestFeedParsing(unittest.TestCase):
    def setUp(self):
        self.cutoff = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def test_parse_rss_with_pubdate(self):
        content = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
          <channel>
            <title>Example RSS</title>
            <item>
              <title><![CDATA[RSS Title]]></title>
              <link>/post-1</link>
              <pubDate>Fri, 27 Mar 2026 10:00:00 +0000</pubDate>
            </item>
          </channel>
        </rss>
        """
        articles = fetch_rss.parse_feed(content, self.cutoff, "https://example.com/feed.xml")
        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0]["title"], "RSS Title")
        self.assertEqual(articles[0]["link"], "https://example.com/post-1")

    def test_parse_atom_with_href_link(self):
        content = """<?xml version="1.0" encoding="utf-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
          <title>Example Atom</title>
          <entry>
            <title>Atom Title</title>
            <link rel="alternate" href="/entry-1" />
            <updated>2026-03-27T12:00:00Z</updated>
          </entry>
        </feed>
        """
        articles = fetch_rss.parse_feed(content, self.cutoff, "https://example.com/atom.xml")
        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0]["title"], "Atom Title")
        self.assertEqual(articles[0]["link"], "https://example.com/entry-1")

    def test_parse_rss_with_dc_date_namespace(self):
        content = """<?xml version="1.0" encoding="UTF-8"?>
        <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
                 xmlns:dc="http://purl.org/dc/elements/1.1/">
          <item>
            <title>DC Date Title</title>
            <link>https://example.com/dc-date</link>
            <dc:date>2026-03-27T09:30:00Z</dc:date>
          </item>
        </rdf:RDF>
        """
        articles = fetch_rss.parse_feed(content, self.cutoff, "https://example.com/rdf.xml")
        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0]["title"], "DC Date Title")
        self.assertEqual(articles[0]["link"], "https://example.com/dc-date")

    def test_non_feed_is_rejected(self):
        self.assertFalse(fetch_rss.is_probably_feed("<html><body>blocked</body></html>", "text/html"))


if __name__ == "__main__":
    unittest.main()
