"""AI-powered sentiment analysis and ticker recommendations.

Supports three backends (configured via env vars):
1. AWS Bedrock with bearer token (AWS_BEARER_TOKEN_BEDROCK)
2. AWS Bedrock with IAM credentials (default boto3 auth)
3. Anthropic API direct (ANTHROPIC_API_KEY)

Backend selection priority: ANTHROPIC_API_KEY > AWS_BEARER_TOKEN_BEDROCK > boto3 default
"""

import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.services.bedrock_config import (
    BEDROCK_REGION,
    BEDROCK_MODEL_ID,
    BEDROCK_MAX_CONCURRENT,
    BEDROCK_TIMEOUT,
    BEDROCK_ENABLED,
    SYSTEM_PROMPT,
    ARTICLE_PROMPT_TEMPLATE,
    MINIMAX_API_KEY,
    MINIMAX_BASE_URL,
    MINIMAX_MODEL_ID,
    MINIMAX_MAX_TOKENS,
    ANTHROPIC_API_KEY,
    ANTHROPIC_MODEL_ID,
    ANTHROPIC_MAX_TOKENS,
    BEDROCK_MAX_TOKENS,
)
from app.services.metrics import emit_metric, emit_metrics

logger = logging.getLogger("signal.ai")

_AI_NAMESPACE = "InstantNews/AIPipeline"


def _emit_backend_chosen(backend: str) -> None:
    """Emit a BackendChosen=1 EMF metric with the {Backend} dimension."""
    emit_metric(
        namespace=_AI_NAMESPACE,
        metric_name="BackendChosen",
        value=1,
        unit="Count",
        dimensions={"Backend": backend},
    )

_minimax_client = None
_anthropic_client = None


def _get_backend():
    """Determine which backend will be tried first."""
    if MINIMAX_API_KEY:
        return "minimax"
    if ANTHROPIC_API_KEY:
        return "anthropic"
    return "bedrock"


def _get_minimax_client():
    """Lazy-init MiniMax client (Anthropic-compatible SDK)."""
    global _minimax_client
    if _minimax_client is None and MINIMAX_API_KEY:
        import anthropic
        kwargs = {"api_key": MINIMAX_API_KEY}
        if MINIMAX_BASE_URL:
            kwargs["base_url"] = MINIMAX_BASE_URL
        _minimax_client = anthropic.Anthropic(**kwargs)
    return _minimax_client


def _get_anthropic_client():
    """Lazy-init Anthropic Claude client."""
    global _anthropic_client
    if _anthropic_client is None and ANTHROPIC_API_KEY:
        import anthropic
        _anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    return _anthropic_client


def _call_with_client(client, model_id, prompt, max_tokens=1024, temperature=0.1):
    """Call any Anthropic-compatible API."""
    message = client.messages.create(
        model=model_id,
        max_tokens=max_tokens,
        temperature=temperature,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    text = ""
    for block in message.content:
        if block.type == "text":
            text += block.text
        # Skip thinking blocks, tool_use blocks, etc.
    return text


def _call_bedrock(prompt, max_tokens=1024, temperature=0.1):
    """Call AWS Bedrock using boto3."""
    import boto3
    client = boto3.client("bedrock-runtime", region_name=BEDROCK_REGION)
    response = client.converse(
        modelId=BEDROCK_MODEL_ID,
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        system=[{"text": SYSTEM_PROMPT}],
        inferenceConfig={"maxTokens": max_tokens, "temperature": temperature},
    )
    text = ""
    for block in response.get("output", {}).get("message", {}).get("content", []):
        if "text" in block:
            text += block["text"]
    return text


def _call_model(prompt):
    """Call AI model with fallback chain: MiniMax → Claude → Bedrock.

    Tries each configured backend in order. Falls back on any error.
    Emits one EMF `BackendChosen=1` metric (dimension ``Backend``) after the
    call succeeds, so the dashboard can chart fallback-chain distribution.
    Emission happens only on success — a failure that falls through to the
    next backend does NOT emit (the signal is WHICH backend served, not
    which backend was tried).
    """
    # 1. Try MiniMax (primary — 160K max tokens)
    minimax = _get_minimax_client()
    if minimax:
        try:
            result = _call_with_client(minimax, MINIMAX_MODEL_ID, prompt, max_tokens=MINIMAX_MAX_TOKENS)
            if result:
                logger.debug("AI call succeeded", extra={"backend": "minimax"})
                _emit_backend_chosen("minimax")
                return result
        except Exception as e:
            logger.warning("MiniMax failed, falling back to Claude", extra={
                "event": "ai_fallback",
                "from": "minimax",
                "to": "anthropic",
                "error": str(e)[:200],
            })

    # 2. Try Anthropic Claude (fallback)
    anthropic = _get_anthropic_client()
    if anthropic:
        try:
            result = _call_with_client(anthropic, ANTHROPIC_MODEL_ID, prompt, max_tokens=ANTHROPIC_MAX_TOKENS)
            if result:
                logger.debug("AI call succeeded", extra={"backend": "anthropic"})
                _emit_backend_chosen("claude")
                return result
        except Exception as e:
            logger.warning("Anthropic failed, falling back to Bedrock", extra={
                "event": "ai_fallback",
                "from": "anthropic",
                "to": "bedrock",
                "error": str(e)[:200],
            })

    # 3. Try Bedrock (last resort)
    result = _call_bedrock(prompt, max_tokens=BEDROCK_MAX_TOKENS)
    _emit_backend_chosen("bedrock")
    return result


def _parse_response(output_text):
    """Parse JSON from model response, handling markdown code blocks."""
    if not output_text:
        return None

    text = output_text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        text = text.rsplit("```", 1)[0]
    text = text.strip()

    result = json.loads(text)

    # Normalize sentiment label
    sentiment = result.get("sentiment", "Neutral")
    label_map = {"Bullish": "bullish", "Bearish": "bearish", "Neutral": "neutral"}
    sentiment_label = label_map.get(sentiment, "neutral")

    # Normalize score
    score = float(result.get("sentiment_score", 0.0))
    score = max(-1.0, min(1.0, score))

    return {
        "sentiment_label": sentiment_label,
        "sentiment_score": round(score, 3),
        "target_asset": result.get("target_asset", "") or "",
        "asset_type": result.get("asset_type", "") or "",
        "confidence": round(float(result.get("confidence", 0.0)), 3),
        "risk_level": result.get("risk_level", "") or "",
        "tradeable": bool(result.get("tradeable", False)),
        "reasoning": result.get("reasoning", "") or "",
    }


def analyze_article(title, summary, source, published):
    """Analyze a single article via AI.

    Returns a dict with sentiment, ticker recommendation, etc.
    Returns None on failure.
    """
    if not BEDROCK_ENABLED:
        return None

    prompt = ARTICLE_PROMPT_TEMPLATE.format(
        title=title,
        summary=summary or "",
        source=source or "",
        published=published or "",
    )

    try:
        output_text = _call_model(prompt)
        return _parse_response(output_text)

    except json.JSONDecodeError as e:
        logger.warning("AI JSON parse error", extra={
            "event": "ai_parse_error",
            "title": title[:100],
            "error": str(e),
        })
        return None
    except Exception as e:
        logger.warning("AI analysis failed", extra={
            "event": "ai_error",
            "backend": _get_backend(),
            "title": title[:100],
            "error": str(e),
        })
        return None


def analyze_articles_batch(articles):
    """Analyze multiple articles concurrently.

    Args:
        articles: list of dicts with keys: id, title, summary, source, published

    Returns:
        dict mapping article id -> analysis result (or None on failure)

    Emits one EMF line on completion with BatchSize + BatchDurationMs
    (namespace InstantNews/AIPipeline, no dimensions) so the dashboard can
    plot batch throughput over time.
    """
    if not BEDROCK_ENABLED or not articles:
        return {}

    results = {}

    batch_start = time.monotonic()
    with ThreadPoolExecutor(max_workers=BEDROCK_MAX_CONCURRENT) as pool:
        futures = {}
        for article in articles:
            future = pool.submit(
                analyze_article,
                article["title"],
                article.get("summary", ""),
                article.get("source", ""),
                article.get("published", ""),
            )
            futures[future] = article["id"]

        for future in as_completed(futures, timeout=BEDROCK_TIMEOUT * 2):
            article_id = futures[future]
            try:
                results[article_id] = future.result()
            except Exception as e:
                logger.warning("AI batch item failed", extra={
                    "article_id": article_id,
                    "error": str(e),
                })
                results[article_id] = None
    elapsed_ms = (time.monotonic() - batch_start) * 1000.0

    emit_metrics(
        namespace=_AI_NAMESPACE,
        metrics=[
            {"name": "BatchSize", "value": len(articles), "unit": "Count"},
            {"name": "BatchDurationMs", "value": elapsed_ms, "unit": "Milliseconds"},
        ],
        dimensions=None,
    )

    return results
