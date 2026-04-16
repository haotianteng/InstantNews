"""Tests for sentiment scoring."""

from app.services.sentiment import score_sentiment


class TestScoreSentiment:
    def test_empty_input(self):
        score, label = score_sentiment("")
        assert score == 0.0
        assert label == "neutral"

    def test_none_input(self):
        score, label = score_sentiment(None)
        assert score == 0.0
        assert label == "neutral"

    def test_bullish_text(self):
        score, label = score_sentiment("Stock surges to record high on strong growth")
        assert score > 0.1
        assert label == "bullish"

    def test_bearish_text(self):
        score, label = score_sentiment("Market crash amid recession fears and layoffs")
        assert score < -0.1
        assert label == "bearish"

    def test_neutral_text(self):
        score, label = score_sentiment("Company announces quarterly meeting schedule")
        assert score == 0.0
        assert label == "neutral"

    def test_mixed_text(self):
        score, label = score_sentiment("Gains offset by decline in other sectors")
        assert -0.5 <= score <= 0.5

    def test_score_clamped(self):
        score, label = score_sentiment("surge surge surge surge surge")
        assert score <= 1.0
        assert score >= -1.0

    def test_score_rounded(self):
        score, _ = score_sentiment("surge decline")
        assert score == round(score, 3)
