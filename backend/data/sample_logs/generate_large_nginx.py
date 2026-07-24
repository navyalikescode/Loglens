#!/usr/bin/env python3
"""
Generate a large nginx combined access log for pipeline / anomaly / clustering stress tests.

Uses a ~40+ minute span with: baseline 200s, multi-minute 5xx burst, latency outliers,
and an 8-minute wall-clock gap between two dense regions to exercise silence detection.

Usage (from repo backend/):
  uv run python data/sample_logs/generate_large_nginx.py -o data/sample_logs/nginx_stress_large.log --lines 25000
"""

from __future__ import annotations

import argparse
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


UTC = timezone.utc


def format_nginx_access_ts(dt: datetime) -> str:
    return dt.strftime("%d/%b/%Y:%H:%M:%S +0000")


def line_at(
    ts: datetime,
    path: str,
    status: int,
    size: int,
    rt_s: float,
    ip: str | None = None,
) -> str:
    ip = ip or "127.0.0.1"
    ts_s = format_nginx_access_ts(ts.astimezone(UTC))
    return (
        f'{ip} - - [{ts_s}] "GET {path} HTTP/1.1" {status} {size} '
        f'"-" "Mozilla/5.0" rt={rt_s:.3f}'
    )


def generate(lines: int, seed: int) -> list[str]:
    rng = random.Random(seed)
    out: list[str] = []
    if lines < 200:
        # still produce a coherent mini-log
        start = datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC)
        for i in range(lines):
            t = start + timedelta(seconds=i % 120)
            out.append(line_at(t, "/api/ping", 200, 42, 0.01 + rng.random() * 0.05))
        return out

    start = datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC)
    # Allocate line budget across phases
    gap_marker = int(lines * 0.55)
    burst_end = int(lines * 0.72)

    ips = [f"203.0.113.{rng.randint(1, 250)}" for _ in range(40)]

    def pick_ts(i: int) -> datetime:
        if i < gap_marker:
            # Dense traffic over ~28 minutes before gap
            frac = i / max(gap_marker, 1)
            return start + timedelta(seconds=frac * (28 * 60))
        if i < gap_marker + int(lines * 0.02):
            # Silence bridge: advance wall clock by ~8 minutes in few lines
            bridge = i - gap_marker
            return start + timedelta(seconds=28 * 60 + 8 * 60 + bridge * 5)
        # Recovery + sustained region
        j = i - gap_marker - int(lines * 0.02)
        span_lines = lines - gap_marker - int(lines * 0.02)
        frac = j / max(span_lines, 1)
        return start + timedelta(seconds=28 * 60 + 8 * 60 + frac * (14 * 60))

    paths_catalog = [
        "/health",
        "/api/catalog",
        "/api/checkout",
        "/api/payments",
        "/static/app.js",
        "/api/report/export",
    ]

    for i in range(lines):
        t = pick_ts(i)
        path = rng.choice(paths_catalog)

        # Default mix
        status = 200
        size = rng.randint(200, 12000)

        # Error burst window (middle third after gap starts — indices in burst band)
        if gap_marker <= i < burst_end:
            r = rng.random()
            if r < 0.55:
                status = rng.choice([502, 503, 504])
                size = rng.randint(99, 220)
            elif r < 0.75:
                status = rng.choice([400, 404, 429])
                size = rng.randint(120, 400)
            else:
                status = 200

        elif i < gap_marker:
            if rng.random() < 0.03:
                status = rng.choice([404, 429])
            if rng.random() < 0.008:
                status = rng.choice([500, 502])

        # Latency: rare heavy tails + burst slow responses
        if status == 200 and path == "/api/report/export":
            rt = rng.choice([11.5, 12.0, 12.8]) + rng.random()
        elif status in (502, 503, 504):
            rt = 25.0 + rng.random() * 6.0
        elif rng.random() < 0.012:
            rt = 6.0 + rng.random() * 6.0
        else:
            rt = 0.008 + rng.random() * 0.12

        ip = rng.choice(ips)
        out.append(line_at(t, path, status, size, rt, ip=ip))

    return out


def main() -> None:
    p = argparse.ArgumentParser(description="Generate synthetic nginx access log.")
    p.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Write to file (default: stdout)",
    )
    p.add_argument("--lines", type=int, default=25000, help="Number of lines (default: 25000)")
    p.add_argument("--seed", type=int, default=42, help="RNG seed for reproducibility")
    args = p.parse_args()

    rows = generate(args.lines, args.seed)
    text = "\n".join(rows) + "\n"

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
        print(f"Wrote {len(rows)} lines to {args.output}", file=sys.stderr)
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
