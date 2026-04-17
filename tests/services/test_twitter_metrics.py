"""Unit tests for X API EMF metric emission (US-005).

These tests mock the HTTP layer (``requests.Session.get``) so they do
NOT hit X's API.  They exercise :class:`TwitterClient.search_recent`
end-to-end and assert the shape of the emitted EMF line.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from app.services import twitter_source
from app.services.twitter_source import TwitterClient


# ---------------------------------------------------------------------------
# Helpers / fakes
# ---------------------------------------------------------------------------


def _parse_emf_lines(captured: str) -> list[dict[str, Any]]:
    return [json.loads(ln) for ln in captured.splitlines() if ln.strip()]


class _FakeResponse:
    """Minimal stand-in for ``requests.Response`` with the fields search_recent touches."""
    def __init__(
        self,
        status_code: int,
        json_payload: dict | None = None,
        headers: dict[str, str] | None = None,
        text: str = "",
    ) -> None:
        self.status_code = status_code
        self._payload = json_payload or {}
        self.headers = headers or {}
        self.text = text

    def json(self) -> dict:
        return self._payload


# ---------------------------------------------------------------------------
# Test 1 — 200 response emits multi-metric line with counts + rate limit
# ---------------------------------------------------------------------------


def test_search_recent_emits_metrics_on_200(
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
) -> None:
    """A 200 response emits one EMF line with TweetsBilled, UsersBilled, RateLimit*."""
    payload = {
        "data": [{"id": "1", "text": "hello", "author_id": "42"}],
        "includes": {"users": [{"id": "42", "username": "alice"}]},
        "meta": {"newest_id": "1"},
    }
    fake_resp = _FakeResponse(
        status_code=200,
        json_payload=payload,
        headers={
            "x-rate-limit-remaining": "449",
            "x-rate-limit-limit": "450",
        },
    )

    # Intercept the Session.get call at the instance level.
    def fake_get(url: str, params: dict | None = None, timeout: int = 0) -> _FakeResponse:
        assert "/tweets/search/recent" in url
        return fake_resp

    client = TwitterClient(bearer_token="test-bearer")
    monkeypatch.setattr(client._session, "get", fake_get)

    tweets = client.search_recent(["alice"])
    assert len(tweets) == 1
    assert tweets[0].id == "1"
    assert tweets[0].author_username == "alice"

    out, _err = capfd.readouterr()
    lines = _parse_emf_lines(out)
    assert len(lines) == 1, f"expected 1 EMF line, got {len(lines)}: {lines!r}"
    line = lines[0]

    directive = line["_aws"]["CloudWatchMetrics"][0]
    assert directive["Namespace"] == "InstantNews/Twitter"
    metric_names = {m["Name"] for m in directive["Metrics"]}
    assert metric_names == {
        "TweetsBilled",
        "UsersBilled",
        "RateLimitRemaining",
        "RateLimitLimit",
    }
    assert directive["Dimensions"] == [["Endpoint"]]
    assert line["Endpoint"] == "search_recent"
    assert line["TweetsBilled"] == 1
    assert line["UsersBilled"] == 1
    assert line["RateLimitRemaining"] == 449
    assert line["RateLimitLimit"] == 450


# ---------------------------------------------------------------------------
# Test 2 — 429 response emits RateLimited=1
# ---------------------------------------------------------------------------


def test_search_recent_emits_rate_limited_on_429(
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
) -> None:
    """A 429 response emits exactly one RateLimited=1 EMF line and stops iteration."""
    fake_resp = _FakeResponse(status_code=429, json_payload={}, headers={}, text="over")

    def fake_get(url: str, params: dict | None = None, timeout: int = 0) -> _FakeResponse:
        return fake_resp

    client = TwitterClient(bearer_token="test-bearer")
    monkeypatch.setattr(client._session, "get", fake_get)

    tweets = client.search_recent(["alice", "bob"])
    assert tweets == []

    out, _err = capfd.readouterr()
    lines = _parse_emf_lines(out)
    # Should emit only the 429 line and break out of the chunk loop.
    assert len(lines) == 1
    line = lines[0]
    directive = line["_aws"]["CloudWatchMetrics"][0]
    assert directive["Namespace"] == "InstantNews/Twitter"
    assert directive["Metrics"] == [{"Name": "RateLimited", "Unit": "Count"}]
    assert directive["Dimensions"] == [["Endpoint"]]
    assert line["Endpoint"] == "search_recent"
    assert line["RateLimited"] == 1


# ---------------------------------------------------------------------------
# Test 3 — missing rate-limit headers: metrics omitted, no crash
# ---------------------------------------------------------------------------


def test_search_recent_tolerates_missing_headers(
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
) -> None:
    """If rate-limit headers are absent the EMF line omits them but still emits counts."""
    payload = {
        "data": [
            {"id": "1", "text": "a", "author_id": "42"},
            {"id": "2", "text": "b", "author_id": "42"},
        ],
        "includes": {"users": [{"id": "42", "username": "alice"}]},
        "meta": {"newest_id": "2"},
    }
    fake_resp = _FakeResponse(status_code=200, json_payload=payload, headers={})

    def fake_get(url: str, params: dict | None = None, timeout: int = 0) -> _FakeResponse:
        return fake_resp

    client = TwitterClient(bearer_token="test-bearer")
    monkeypatch.setattr(client._session, "get", fake_get)

    tweets = client.search_recent(["alice"])
    assert len(tweets) == 2

    out, _err = capfd.readouterr()
    lines = _parse_emf_lines(out)
    assert len(lines) == 1
    line = lines[0]
    metric_names = {m["Name"] for m in line["_aws"]["CloudWatchMetrics"][0]["Metrics"]}
    # Only the billed counters — no rate-limit keys.
    assert metric_names == {"TweetsBilled", "UsersBilled"}
    assert line["TweetsBilled"] == 2
    assert line["UsersBilled"] == 1
