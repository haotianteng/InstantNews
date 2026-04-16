"""Locust load test suite for SIGNAL (InstantNews).

Covers all major endpoints:
- Landing page and static assets
- Authentication flow (token-based)
- News feed API with pagination, filtering, search
- Stats and sources endpoints
- Billing checkout session creation

Usage:
    # 100 users, ramp 10/s
    locust -f tests/load/locustfile.py --host https://www.instnews.net \
           --users 100 --spawn-rate 10 --run-time 5m --headless

    # 500 users (target threshold)
    locust -f tests/load/locustfile.py --host https://www.instnews.net \
           --users 500 --spawn-rate 50 --run-time 10m --headless

    # 1000 users (stress test)
    locust -f tests/load/locustfile.py --host https://www.instnews.net \
           --users 1000 --spawn-rate 100 --run-time 10m --headless

    # Web UI mode
    locust -f tests/load/locustfile.py --host https://www.instnews.net

Environment variables:
    LOAD_TEST_AUTH_TOKEN   - Firebase ID token for authenticated requests
    LOAD_TEST_HOST         - Override target host (default: https://www.instnews.net)
"""

import os
import random
import time
from typing import Optional

from locust import HttpUser, TaskSet, task, between, events
from locust.runners import MasterRunner


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
AUTH_TOKEN: Optional[str] = os.environ.get("LOAD_TEST_AUTH_TOKEN")

SOURCES = [
    "CNBC", "CNBC_World", "Reuters_Business", "MarketWatch",
    "MarketWatch_Markets", "Investing_com", "Yahoo_Finance",
    "Nasdaq", "SeekingAlpha", "Benzinga", "AP_News",
    "Bloomberg_Business", "Bloomberg_Markets", "BBC_Business",
    "Google_News_Business",
]

SEARCH_TERMS = [
    "stock", "market", "inflation", "fed", "earnings",
    "crypto", "oil", "rate", "GDP", "trade", "bank",
    "tech", "AI", "bond", "recession",
]

SENTIMENTS = ["positive", "negative", "neutral"]


def _auth_headers() -> dict:
    """Return Authorization header if a token is available."""
    if AUTH_TOKEN:
        return {"Authorization": f"Bearer {AUTH_TOKEN}"}
    return {}


# ---------------------------------------------------------------------------
# Task Sets
# ---------------------------------------------------------------------------
class LandingPageTasks(TaskSet):
    """Simulate visitors browsing the marketing site."""

    @task(5)
    def landing_page(self) -> None:
        self.client.get("/", name="GET / (landing)")

    @task(2)
    def pricing_page(self) -> None:
        self.client.get("/pricing", name="GET /pricing")

    @task(2)
    def docs_page(self) -> None:
        self.client.get("/docs", name="GET /docs")

    @task(1)
    def terminal_page(self) -> None:
        self.client.get("/terminal", name="GET /terminal")

    @task(1)
    def terms_page(self) -> None:
        self.client.get("/terms", name="GET /terms")

    @task(1)
    def privacy_page(self) -> None:
        self.client.get("/privacy", name="GET /privacy")


class NewsFeedTasks(TaskSet):
    """Simulate users interacting with the news feed API."""

    @task(10)
    def news_default(self) -> None:
        """Default news fetch (most common request)."""
        self.client.get("/api/news", name="GET /api/news (default)")

    @task(5)
    def news_paginated(self) -> None:
        """Paginated fetch with various limit values."""
        limit = random.choice([10, 25, 50, 100, 200])
        self.client.get(
            f"/api/news?limit={limit}",
            name="GET /api/news?limit=N",
        )

    @task(4)
    def news_by_source(self) -> None:
        """Filter by a specific source."""
        source = random.choice(SOURCES)
        self.client.get(
            f"/api/news?source={source}",
            name="GET /api/news?source=X",
        )

    @task(3)
    def news_search(self) -> None:
        """Keyword search in headlines."""
        q = random.choice(SEARCH_TERMS)
        self.client.get(
            f"/api/news?q={q}",
            name="GET /api/news?q=keyword",
        )

    @task(2)
    def news_by_sentiment(self) -> None:
        """Filter by sentiment label."""
        sentiment = random.choice(SENTIMENTS)
        self.client.get(
            f"/api/news?sentiment={sentiment}",
            name="GET /api/news?sentiment=X",
        )

    @task(2)
    def news_combined_filters(self) -> None:
        """Combined source + search + limit filters."""
        source = random.choice(SOURCES)
        q = random.choice(SEARCH_TERMS)
        limit = random.choice([25, 50])
        self.client.get(
            f"/api/news?source={source}&q={q}&limit={limit}",
            name="GET /api/news (combined filters)",
        )


class StatsAndSourcesTasks(TaskSet):
    """Simulate users viewing stats and sources."""

    @task(3)
    def stats(self) -> None:
        self.client.get("/api/stats", name="GET /api/stats")

    @task(3)
    def sources(self) -> None:
        self.client.get("/api/sources", name="GET /api/sources")

    @task(1)
    def docs_api(self) -> None:
        self.client.get("/api/docs", name="GET /api/docs")

    @task(1)
    def pricing_api(self) -> None:
        self.client.get("/api/pricing", name="GET /api/pricing")


class AuthenticatedTasks(TaskSet):
    """Simulate authenticated user actions (requires LOAD_TEST_AUTH_TOKEN)."""

    def on_start(self) -> None:
        if not AUTH_TOKEN:
            # Skip auth tasks when no token is configured
            self.interrupt()

    @task(5)
    def get_me(self) -> None:
        self.client.get(
            "/api/auth/me",
            headers=_auth_headers(),
            name="GET /api/auth/me",
        )

    @task(3)
    def get_tier(self) -> None:
        self.client.get(
            "/api/auth/tier",
            headers=_auth_headers(),
            name="GET /api/auth/tier",
        )

    @task(3)
    def news_authenticated(self) -> None:
        """Authenticated news fetch (gets full data based on tier)."""
        self.client.get(
            "/api/news?limit=50",
            headers=_auth_headers(),
            name="GET /api/news (authed)",
        )

    @task(1)
    def billing_status(self) -> None:
        self.client.get(
            "/api/billing/status",
            headers=_auth_headers(),
            name="GET /api/billing/status",
        )


class CheckoutTasks(TaskSet):
    """Simulate checkout session creation (requires LOAD_TEST_AUTH_TOKEN).

    NOTE: These hit Stripe API and should be used sparingly.
    Use low weight or run separately.
    """

    def on_start(self) -> None:
        if not AUTH_TOKEN:
            self.interrupt()

    @task(1)
    def create_checkout_plus(self) -> None:
        self.client.post(
            "/api/billing/checkout",
            json={"tier": "plus"},
            headers=_auth_headers(),
            name="POST /api/billing/checkout (plus)",
        )

    @task(1)
    def create_checkout_max(self) -> None:
        self.client.post(
            "/api/billing/checkout",
            json={"tier": "max"},
            headers=_auth_headers(),
            name="POST /api/billing/checkout (max)",
        )


# ---------------------------------------------------------------------------
# User Classes (weight controls user distribution)
# ---------------------------------------------------------------------------
class AnonymousVisitor(HttpUser):
    """Unauthenticated visitor browsing landing pages and public API.

    Represents ~60% of traffic.
    """
    weight = 6
    wait_time = between(1, 5)
    tasks = {
        LandingPageTasks: 3,
        NewsFeedTasks: 4,
        StatsAndSourcesTasks: 2,
    }


class AuthenticatedUser(HttpUser):
    """Authenticated user using the terminal and API.

    Represents ~30% of traffic.
    """
    weight = 3
    wait_time = between(0.5, 3)
    tasks = {
        NewsFeedTasks: 5,
        StatsAndSourcesTasks: 2,
        AuthenticatedTasks: 3,
    }


class PayingCustomer(HttpUser):
    """Paying user who may trigger checkout or portal.

    Represents ~10% of traffic. Checkout tasks have low weight
    to avoid hammering Stripe API.
    """
    weight = 1
    wait_time = between(2, 8)
    tasks = {
        NewsFeedTasks: 5,
        AuthenticatedTasks: 3,
        CheckoutTasks: 1,
    }


# ---------------------------------------------------------------------------
# Event hooks for custom metrics reporting
# ---------------------------------------------------------------------------
@events.test_start.add_listener
def on_test_start(environment, **kwargs) -> None:
    """Log test configuration at start."""
    if isinstance(environment.runner, MasterRunner):
        print("Load test starting on master node")
    print(f"Target host: {environment.host}")
    print(f"Auth token configured: {bool(AUTH_TOKEN)}")


@events.quitting.add_listener
def on_quitting(environment, **kwargs) -> None:
    """Check pass/fail thresholds on test completion."""
    stats = environment.runner.stats
    total = stats.total

    failures = []

    # Check error rate
    if total.num_requests > 0:
        error_rate = (total.num_failures / total.num_requests) * 100
        if error_rate > 1.0:
            failures.append(
                f"FAIL: Error rate {error_rate:.2f}% exceeds 1% threshold"
            )

    # Check p95 for API endpoints
    for entry in stats.entries.values():
        name = entry.name
        if name.startswith("GET /api/") or name.startswith("POST /api/"):
            p95 = entry.get_response_time_percentile(0.95) or 0
            if p95 > 500:
                failures.append(
                    f"FAIL: {name} p95={p95:.0f}ms exceeds 500ms threshold"
                )
        elif name.startswith("GET /"):
            p95 = entry.get_response_time_percentile(0.95) or 0
            if p95 > 2000:
                failures.append(
                    f"FAIL: {name} p95={p95:.0f}ms exceeds 2s threshold"
                )

    if failures:
        print("\n" + "=" * 60)
        print("THRESHOLD VIOLATIONS:")
        for f in failures:
            print(f"  {f}")
        print("=" * 60)
        environment.process_exit_code = 1
    else:
        print("\nAll thresholds PASSED")
