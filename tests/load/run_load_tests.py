#!/usr/bin/env python3
"""Helper script to run load tests with predefined profiles.

Usage:
    python tests/load/run_load_tests.py --profile baseline
    python tests/load/run_load_tests.py --profile target --host https://www.instnews.net
    python tests/load/run_load_tests.py --profile stress --host http://localhost:8000
    python tests/load/run_load_tests.py --all --host https://www.instnews.net
"""

import argparse
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from config import PROFILES


def run_profile(
    profile_name: str,
    host: str,
    output_dir: Path,
) -> int:
    """Run a single load test profile and return the exit code."""
    profile = PROFILES[profile_name]
    print(f"\n{'=' * 60}")
    print(f"Running: {profile.description}")
    print(f"{'=' * 60}\n")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_prefix = output_dir / f"{profile_name}_{timestamp}"

    cmd = [
        sys.executable, "-m", "locust",
        "-f", str(Path(__file__).parent / "locustfile.py"),
        "--host", host,
        "--users", str(profile.users),
        "--spawn-rate", str(profile.spawn_rate),
        "--run-time", profile.run_time,
        "--headless",
        "--csv", str(csv_prefix),
        "--html", str(output_dir / f"{profile_name}_{timestamp}.html"),
    ]

    result = subprocess.run(cmd)
    return result.returncode


def main() -> None:
    parser = argparse.ArgumentParser(description="Run SIGNAL load tests")
    parser.add_argument(
        "--profile",
        choices=list(PROFILES.keys()),
        help="Load test profile to run",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all profiles sequentially (baseline -> target -> stress)",
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("LOAD_TEST_HOST", "http://localhost:8000"),
        help="Target host URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--output-dir",
        default="tests/load/results",
        help="Directory for CSV/HTML output (default: tests/load/results)",
    )
    args = parser.parse_args()

    if not args.profile and not args.all:
        parser.error("Specify --profile or --all")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.all:
        profiles_to_run = ["baseline", "target", "stress"]
    else:
        profiles_to_run = [args.profile]

    results = {}
    for profile_name in profiles_to_run:
        exit_code = run_profile(profile_name, args.host, output_dir)
        results[profile_name] = "PASS" if exit_code == 0 else "FAIL"

    print(f"\n{'=' * 60}")
    print("SUMMARY")
    print(f"{'=' * 60}")
    for name, status in results.items():
        profile = PROFILES[name]
        print(f"  {name:10s} ({profile.users:4d} users): {status}")
    print(f"{'=' * 60}\n")

    if any(s == "FAIL" for s in results.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()
