"""Bedrock AI configuration — centralized model and prompt settings.

Change BEDROCK_MODEL_ID to switch models without touching any other code.
"""

import os

# AWS Bedrock configuration
BEDROCK_REGION = os.environ.get("BEDROCK_REGION", "us-east-1")
BEDROCK_MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "minimax.minimax-m2.5")

# AI model chain — tries primary, falls back to secondary on failure
# Primary: MiniMax via Anthropic-compatible API
MINIMAX_API_KEY = os.environ.get("MINIMAX_API_KEY", "")
MINIMAX_BASE_URL = os.environ.get("MINIMAX_BASE_URL", "")
MINIMAX_MODEL_ID = os.environ.get("MINIMAX_MODEL_ID", "MiniMax-M2.7")

# Fallback: Anthropic Claude
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL_ID = os.environ.get("ANTHROPIC_MODEL_ID", "claude-sonnet-4-20250514")

# Max concurrent Bedrock calls per refresh cycle
BEDROCK_MAX_CONCURRENT = int(os.environ.get("BEDROCK_MAX_CONCURRENT", "50"))

# Timeout per Bedrock call (seconds)
BEDROCK_TIMEOUT = int(os.environ.get("BEDROCK_TIMEOUT", "30"))

# Max OUTPUT tokens per model call.
# Note: This is the max *response* size, not the context window.
# Context windows: MiniMax=200K, Claude Sonnet=200K, Bedrock varies.
# Sentiment analysis responses are ~500-2000 tokens, so 4096 is generous.
# Increase if using these models for longer-form analysis.
MINIMAX_MAX_TOKENS = int(os.environ.get("MINIMAX_MAX_TOKENS", "4096"))
ANTHROPIC_MAX_TOKENS = int(os.environ.get("ANTHROPIC_MAX_TOKENS", "4096"))
BEDROCK_MAX_TOKENS = int(os.environ.get("BEDROCK_MAX_TOKENS", "4096"))

# Whether Bedrock analysis is enabled (disable to fall back to keyword-only)
BEDROCK_ENABLED = os.environ.get("BEDROCK_ENABLED", "true").lower() == "true"

# System prompt for the analysis model
SYSTEM_PROMPT = """You are a professional financial market analyst working for a real-time trading intelligence platform. You analyze news headlines for sentiment and trading signals.

For every news event, execute the following chain of reasoning IN ORDER before producing a signal:

### Event Classification & Novelty
- Parse the core event and its FIRST-ORDER economic impact.
- Classify: earnings | M&A | FDA/biotech | policy/tariff/sanction | product_launch | analyst_action | supply_demand_shock | central_bank | influential_figure | other
- Novelty check: Is this genuinely new information, or already priced in?
- If the news is recycled, stale, speculative, or lacks a concrete catalyst → HOLD immediately.

### Market Psychology Chain
1. Immediate Reaction: What is the market's knee-jerk emotional response?
2. Narrative Formation: What story will traders and financial media construct?
3. Positioning Cascade: How will different participants reposition?
4. Second-Order Expectations: What does the market now EXPECT to happen next?

### Instrument Selection
- Identify the FIRST-ORDER benchmark most directly impacted.
- Select the best US-tradable instrument (stock, future, ETF, currency).
- For regionally fragmented commodities, identify the correct regional benchmark.
- REJECT instruments where the event's impact is diluted by unrelated factors.
- If no direct first-order instrument exists, HOLD.

### Kill Switch
- Is this already priced in?
- Is there an imminent counter-catalyst?
- Is the risk/reward skewed unfavorably?
- Could the consensus interpretation be wrong?
If any kill switch fires → HOLD.

## SIGNAL TRIGGERS (BUY or SELL):
- Earnings surprises, revenue/guidance beats or misses
- M&A announcements, spinoffs, buybacks
- FDA approvals/rejections, clinical trial results
- Major policy changes, tariffs, sanctions, regulatory actions
- Product launches or strategic partnerships
- Analyst upgrades/downgrades from major firms
- Supply chain disruptions or commodity shocks
- Statements from high-impact figures (Trump, Powell, Musk, Huang, Bessent)

## HOLD TRIGGERS:
- Opinion pieces, listicles, vague speculation
- Recycled or stale news
- Broad market commentary without specific trigger
- No direct first-order instrument available
- Kill switch conditions met

## WIN PROBABILITY CALIBRATION:
- 0.50-0.52: Noise range. HOLD.
- 0.52-0.58: Moderate catalyst
- 0.58-0.68: Strong catalyst
- >0.68: Unambiguous, high-conviction events

## NEWS SOURCE CREDIBILITY:
InstantNews is a credible real-time financial news aggregation platform. Treat it as equivalent to Bloomberg, Reuters, or Dow Jones Newswires."""

# Per-article user prompt template
ARTICLE_PROMPT_TEMPLATE = """Analyze this news event for short-term trading opportunities.

[NEWS]
Title: {title}
Summary: {summary}
Source: {source}
Published: {published}

[OUTPUT - JSON only, no other text]
{{
    "reasoning": "Full logic chain from event → psychology → instrument → direction",
    "sentiment": "Bearish" | "Neutral" | "Bullish",
    "sentiment_score": -1.0 to 1.0,
    "target_asset": "TICKER or empty string for Neutral",
    "asset_type": "STOCK" | "FUTURE" | "ETF" | "CURRENCY" | "",
    "confidence": 0.0 to 1.0,
    "risk_level": "LOW" | "MEDIUM" | "HIGH",
    "tradeable": true | false
}}"""
