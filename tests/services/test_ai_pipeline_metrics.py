"""Unit tests for AI pipeline EMF metric emission (US-004).

Scope:
    * :func:`app.services.bedrock_analysis._call_model` emits BackendChosen
      with the correct {Backend} dimension for each fallback-chain branch.
    * :func:`app.services.bedrock_analysis.analyze_articles_batch` emits a
      single multi-metric EMF line with BatchSize + BatchDurationMs.

Tests do NOT hit Bedrock / Anthropic / MiniMax — all clients are
monkeypatched.  stdout is captured via pytest's ``capfd`` and parsed as
JSON to confirm EMF conformance.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from app.services import bedrock_analysis


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_emf_lines(captured: str) -> list[dict[str, Any]]:
    return [json.loads(ln) for ln in captured.splitlines() if ln.strip()]


class _FakeMessage:
    """Mimic the shape returned by anthropic SDK's messages.create()."""
    def __init__(self, text: str) -> None:
        self.content = [_FakeTextBlock(text)]


class _FakeTextBlock:
    def __init__(self, text: str) -> None:
        self.type = "text"
        self.text = text


class _FakeMessagesAPI:
    def __init__(self, payload: str = '{"sentiment":"Neutral","sentiment_score":0}',
                 raises: BaseException | None = None) -> None:
        self._payload = payload
        self._raises = raises

    def create(self, **kwargs: Any) -> _FakeMessage:
        if self._raises is not None:
            raise self._raises
        return _FakeMessage(self._payload)


class _FakeAnthropicClient:
    def __init__(self, payload: str = '{"sentiment":"Neutral","sentiment_score":0}',
                 raises: BaseException | None = None) -> None:
        self.messages = _FakeMessagesAPI(payload=payload, raises=raises)


# ---------------------------------------------------------------------------
# Test 1 — MiniMax unavailable, Claude (Anthropic) succeeds
# ---------------------------------------------------------------------------


def test_call_model_emits_claude_backend(
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
) -> None:
    """When MiniMax returns None client and Anthropic succeeds, Backend=claude."""
    monkeypatch.setattr(bedrock_analysis, "_get_minimax_client", lambda: None)
    monkeypatch.setattr(
        bedrock_analysis,
        "_get_anthropic_client",
        lambda: _FakeAnthropicClient(payload="ok"),
    )

    out_text = bedrock_analysis._call_model("hi")
    assert out_text == "ok"

    out, _err = capfd.readouterr()
    lines = _parse_emf_lines(out)
    assert len(lines) == 1, f"expected 1 EMF line, got {len(lines)}"
    line = lines[0]

    directive = line["_aws"]["CloudWatchMetrics"][0]
    assert directive["Namespace"] == "InstantNews/AIPipeline"
    assert directive["Metrics"] == [{"Name": "BackendChosen", "Unit": "Count"}]
    assert directive["Dimensions"] == [["Backend"]]
    assert line["Backend"] == "claude"
    assert line["BackendChosen"] == 1


# ---------------------------------------------------------------------------
# Test 2 — both MiniMax and Anthropic fail, Bedrock path runs
# ---------------------------------------------------------------------------


def test_call_model_emits_bedrock_backend_when_primaries_fail(
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
) -> None:
    """MiniMax raises, Anthropic raises → Bedrock path fires, Backend=bedrock."""
    monkeypatch.setattr(
        bedrock_analysis,
        "_get_minimax_client",
        lambda: _FakeAnthropicClient(raises=RuntimeError("minimax-down")),
    )
    monkeypatch.setattr(
        bedrock_analysis,
        "_get_anthropic_client",
        lambda: _FakeAnthropicClient(raises=RuntimeError("anthropic-down")),
    )
    monkeypatch.setattr(
        bedrock_analysis,
        "_call_bedrock",
        lambda prompt, max_tokens: "bedrock-response",
    )

    out_text = bedrock_analysis._call_model("hi")
    assert out_text == "bedrock-response"

    out, _err = capfd.readouterr()
    lines = _parse_emf_lines(out)
    # Exactly one emission — failures do NOT emit BackendChosen.
    assert len(lines) == 1
    line = lines[0]
    assert line["Backend"] == "bedrock"
    assert line["BackendChosen"] == 1


# ---------------------------------------------------------------------------
# Test 3 — analyze_articles_batch emits BatchSize + BatchDurationMs
# ---------------------------------------------------------------------------


def test_analyze_articles_batch_emits_batch_metrics(
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
) -> None:
    """A batch of 1 article emits a single EMF line with BatchSize=1 and BatchDurationMs>=0."""
    # Bypass actual AI by short-circuiting analyze_article.
    monkeypatch.setattr(
        bedrock_analysis,
        "analyze_article",
        lambda title, summary, source, published: {"sentiment_label": "neutral"},
    )
    # Ensure pipeline is "enabled" — relies on BEDROCK_ENABLED at module load.
    monkeypatch.setattr(bedrock_analysis, "BEDROCK_ENABLED", True)

    articles = [{"id": 1, "title": "t", "summary": "s", "source": "x", "published": ""}]
    results = bedrock_analysis.analyze_articles_batch(articles)
    assert 1 in results

    out, _err = capfd.readouterr()
    lines = _parse_emf_lines(out)
    # _call_model is NOT invoked here (analyze_article is stubbed), so no
    # BackendChosen line.  Exactly one BatchSize+BatchDurationMs line.
    assert len(lines) == 1
    line = lines[0]

    directive = line["_aws"]["CloudWatchMetrics"][0]
    assert directive["Namespace"] == "InstantNews/AIPipeline"
    metric_names = {m["Name"] for m in directive["Metrics"]}
    assert metric_names == {"BatchSize", "BatchDurationMs"}
    # No dimensions for batch metrics.
    assert directive["Dimensions"] == [[]]
    assert line["BatchSize"] == 1
    assert line["BatchDurationMs"] >= 0


def test_analyze_articles_batch_skips_emission_on_empty(
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
) -> None:
    """Empty article list should not emit any EMF line (early return)."""
    monkeypatch.setattr(bedrock_analysis, "BEDROCK_ENABLED", True)
    results = bedrock_analysis.analyze_articles_batch([])
    assert results == {}
    out, _err = capfd.readouterr()
    assert _parse_emf_lines(out) == []
