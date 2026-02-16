"""Measure database health-check latency profile (cold start + warm path).

Usage:
    uv run --python ./.venv/Scripts/python.exe python tools/validate_database_health_latency.py
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from core.config import get_config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


@dataclass
class Sample:
    index: int
    total_ms: float
    query_ms: float
    acquire_ms: float


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    if pct <= 0:
        return min(values)
    if pct >= 100:
        return max(values)
    ordered = sorted(values)
    k = (len(ordered) - 1) * (pct / 100.0)
    lower = int(k)
    upper = min(lower + 1, len(ordered) - 1)
    if lower == upper:
        return ordered[lower]
    weight = k - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def summarize(samples: list[Sample]) -> dict[str, Any]:
    total = [s.total_ms for s in samples]
    query = [s.query_ms for s in samples]
    acquire = [s.acquire_ms for s in samples]
    return {
        "sample_count": len(samples),
        "total_ms": {
            "min": min(total) if total else 0.0,
            "p50": percentile(total, 50),
            "p95": percentile(total, 95),
            "max": max(total) if total else 0.0,
            "avg": statistics.fmean(total) if total else 0.0,
        },
        "query_ms": {
            "min": min(query) if query else 0.0,
            "p50": percentile(query, 50),
            "p95": percentile(query, 95),
            "max": max(query) if query else 0.0,
            "avg": statistics.fmean(query) if query else 0.0,
        },
        "acquire_ms": {
            "min": min(acquire) if acquire else 0.0,
            "p50": percentile(acquire, 50),
            "p95": percentile(acquire, 95),
            "max": max(acquire) if acquire else 0.0,
            "avg": statistics.fmean(acquire) if acquire else 0.0,
        },
    }


async def run_measurement(
    db_url: str,
    samples: int,
    threshold_ms: float,
    connect_timeout_s: float,
    sleep_ms: int,
) -> dict[str, Any]:
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    engine = create_async_engine(
        db_url,
        echo=False,
        pool_pre_ping=True,
        pool_recycle=3600,
        pool_size=10,
        max_overflow=5,
        connect_args={
            "timeout": connect_timeout_s,
            "command_timeout": connect_timeout_s,
            "server_settings": {
                "application_name": "db_latency_diagnose",
            },
        },
    )

    sample_rows: list[Sample] = []
    error: str | None = None
    try:
        for i in range(samples):
            total_start = time.perf_counter()
            async with engine.begin() as conn:
                query_start = time.perf_counter()
                await conn.execute(text("SELECT 1"))
                query_end = time.perf_counter()
            total_end = time.perf_counter()

            total_ms = (total_end - total_start) * 1000.0
            query_ms = (query_end - query_start) * 1000.0
            acquire_ms = max(total_ms - query_ms, 0.0)

            sample_rows.append(
                Sample(
                    index=i + 1,
                    total_ms=total_ms,
                    query_ms=query_ms,
                    acquire_ms=acquire_ms,
                )
            )

            if sleep_ms > 0:
                await asyncio.sleep(sleep_ms / 1000.0)
    except Exception as exc:
        error = str(exc)
    finally:
        await engine.dispose()

    summary = summarize(sample_rows)
    first_query_ms = sample_rows[0].query_ms if sample_rows else None
    warm_p50_query_ms = (
        percentile([s.query_ms for s in sample_rows[1:]], 50) if len(sample_rows) > 1 else None
    )
    first_total_ms = sample_rows[0].total_ms if sample_rows else None
    warm_p50_total_ms = (
        percentile([s.total_ms for s in sample_rows[1:]], 50) if len(sample_rows) > 1 else None
    )

    classification = "error"
    if error is None and sample_rows:
        query_p95 = summary["query_ms"]["p95"]
        if query_p95 > threshold_ms:
            classification = "degraded"
        else:
            classification = "healthy"

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "threshold_ms": threshold_ms,
        "status": classification,
        "error": error,
        "first_query_ms": first_query_ms,
        "warm_p50_query_ms": warm_p50_query_ms,
        "first_total_ms": first_total_ms,
        "warm_p50_total_ms": warm_p50_total_ms,
        "samples": [asdict(item) for item in sample_rows],
        "summary": summary,
    }


def resolve_db_url() -> tuple[str | None, dict[str, Any]]:
    cfg = get_config()
    if cfg is None or cfg.database is None:
        return None, {"reason": "missing database config"}
    main = cfg.database.main
    db_url = main.get_url()
    details = {
        "type": main.type,
        "host": main.host,
        "port": main.port,
        "database": main.database,
    }
    return db_url, details


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=int, default=8, help="Sample count")
    parser.add_argument("--threshold-ms", type=float, default=1500.0, help="Degraded threshold")
    parser.add_argument(
        "--connect-timeout-s",
        type=float,
        default=5.0,
        help="Database connect/query timeout",
    )
    parser.add_argument("--sleep-ms", type=int, default=0, help="Sleep between samples")
    parser.add_argument("--strict", action="store_true", help="Return non-zero for degraded/error")
    args = parser.parse_args()

    db_url, db_info = resolve_db_url()
    if not db_url:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "error",
            "error": "database url unavailable",
            "database": db_info,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 2 if args.strict else 0

    payload = asyncio.run(
        run_measurement(
            db_url=db_url,
            samples=max(args.samples, 1),
            threshold_ms=args.threshold_ms,
            connect_timeout_s=max(args.connect_timeout_s, 1.0),
            sleep_ms=max(args.sleep_ms, 0),
        )
    )
    payload["database"] = db_info
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    if args.strict and payload["status"] != "healthy":
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
