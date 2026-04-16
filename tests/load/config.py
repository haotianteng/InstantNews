"""Load test configuration for three concurrency levels.

Usage:
    # Run a specific profile
    locust -f tests/load/locustfile.py --host https://www.instnews.net \
           --users 100 --spawn-rate 10 --run-time 5m --headless \
           --csv results/load-100

    # Or use the run_load_tests.py helper script
    python tests/load/run_load_tests.py --profile baseline
"""

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class LoadProfile:
    """Configuration for a load test run."""
    name: str
    users: int
    spawn_rate: int
    run_time: str
    description: str


# Three concurrency levels as specified
PROFILES: Dict[str, LoadProfile] = {
    "baseline": LoadProfile(
        name="baseline",
        users=100,
        spawn_rate=10,
        run_time="5m",
        description="Baseline: 100 concurrent users, ramp 10/s over 10s",
    ),
    "target": LoadProfile(
        name="target",
        users=500,
        spawn_rate=50,
        run_time="10m",
        description="Target: 500 concurrent users, ramp 50/s over 10s",
    ),
    "stress": LoadProfile(
        name="stress",
        users=1000,
        spawn_rate=100,
        run_time="10m",
        description="Stress: 1000 concurrent users, ramp 100/s over 10s",
    ),
}

# Pass/fail thresholds
THRESHOLDS = {
    "api_p95_ms": 500,          # API endpoints p95 < 500ms
    "page_p95_ms": 2000,        # Page loads p95 < 2s
    "error_rate_pct": 1.0,      # Error rate < 1% at 500 concurrent
    "min_rps": 50,              # Minimum requests/sec at baseline
}
