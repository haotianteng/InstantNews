"""Tests for feed parsing utilities."""

from datetime import datetime, timezone

from app.services.feed_parser import strip_html, utc_iso, parse_date


class TestStripHtml:
    def test_removes_tags(self):
        assert strip_html("<p>Hello <b>World</b></p>") == "Hello World"

    def test_handles_none(self):
        assert strip_html(None) == ""

    def test_handles_empty(self):
        assert strip_html("") == ""

    def test_decodes_entities(self):
        result = strip_html("A&amp;B")
        assert "&" not in result or "A B" == result

    def test_truncates_to_500(self):
        long_text = "x" * 1000
        assert len(strip_html(long_text)) <= 500

    def test_adds_space_for_block_tags(self):
        result = strip_html("<p>First</p><p>Second</p>")
        assert "First" in result
        assert "Second" in result


class TestUtcIso:
    def test_naive_datetime(self):
        dt = datetime(2026, 3, 20, 14, 30, 0)
        result = utc_iso(dt)
        assert result == "2026-03-20T14:30:00+00:00"

    def test_aware_datetime(self):
        dt = datetime(2026, 3, 20, 14, 30, 0, tzinfo=timezone.utc)
        result = utc_iso(dt)
        assert result == "2026-03-20T14:30:00+00:00"


class TestParseDate:
    def test_rss_format(self):
        result = parse_date("Fri, 20 Mar 2026 14:30:00 +0000")
        assert result == "2026-03-20T14:30:00+00:00"

    def test_iso_format(self):
        result = parse_date("2026-03-20T14:30:00Z")
        assert result == "2026-03-20T14:30:00+00:00"

    def test_none_returns_now(self):
        result = parse_date(None)
        assert "T" in result
        assert "+00:00" in result

    def test_unparseable_returns_now(self):
        result = parse_date("not a date")
        assert "T" in result
        assert "+00:00" in result
