"""Keyword-based sentiment scoring for financial headlines."""

BULLISH_WORDS = [
    "surge", "soar", "rally", "gain", "jump", "rise", "bull", "record high",
    "upgrade", "beat", "exceed", "profit", "growth", "boom", "breakout",
    "outperform", "buy", "accelerate", "expand", "bullish", "uptick", "climb",
    "recover", "rebound", "strong", "positive", "upbeat", "optimis",
]

BEARISH_WORDS = [
    "crash", "plunge", "drop", "fall", "decline", "bear", "loss", "downgrade",
    "miss", "deficit", "recession", "layoff", "bankruptcy", "sell-off",
    "warning", "cut", "sink", "tumble", "slump", "bearish", "downturn",
    "weak", "negative", "pessimis", "fear", "risk", "volatil", "concern",
]


def score_sentiment(text):
    """Score text sentiment. Returns (score, label) tuple.

    Score is in [-1.0, 1.0]. Label is 'bullish', 'bearish', or 'neutral'.
    """
    if not text:
        return 0.0, "neutral"
    text_lower = text.lower()
    bullish = sum(1 for w in BULLISH_WORDS if w in text_lower)
    bearish = sum(1 for w in BEARISH_WORDS if w in text_lower)
    total = bullish + bearish
    if total == 0:
        return 0.0, "neutral"
    raw = (bullish - bearish) / total
    score = max(-1.0, min(1.0, raw))
    if score > 0.1:
        label = "bullish"
    elif score < -0.1:
        label = "bearish"
    else:
        label = "neutral"
    return round(score, 3), label
