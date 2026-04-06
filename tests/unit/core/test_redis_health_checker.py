from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from core.core.health.checkers import RedisHealthChecker
from core.core.health.interfaces import HealthStatus


class _FakeRedisComponent:
    def __init__(self) -> None:
        self._redis_client = AsyncMock()
        self._redis_client.info = AsyncMock(
            return_value={
                "redis_version": "7.0.0",
                "connected_clients": 10,
                "used_memory": 1024 * 1024,
                "used_memory_human": "1M",
                "maxmemory": 64 * 1024 * 1024,
            }
        )

    def is_connected(self) -> bool:
        return True


class _InfoFailureRedisComponent:
    def __init__(self) -> None:
        self._redis_client = AsyncMock()
        self._redis_client.info = AsyncMock(side_effect=RuntimeError("info failed"))

    def is_connected(self) -> bool:
        return True


@pytest.mark.asyncio
async def test_redis_health_checker_requires_consecutive_high_latency(monkeypatch):
    checker = RedisHealthChecker(
        latency_threshold_ms=500.0,
        latency_samples=1,
        consecutive_degraded=2,
    )
    checker.component = _FakeRedisComponent()

    probe = AsyncMock(side_effect=[522.0, 531.0, 420.0])
    monkeypatch.setattr(checker, "_measure_ping_latency", probe)

    first = await checker.check()
    second = await checker.check()
    third = await checker.check()

    assert first.status == HealthStatus.HEALTHY
    assert "latency spike observed" in first.message.lower()

    assert second.status == HealthStatus.DEGRADED
    assert "streak=2" in second.message

    assert third.status == HealthStatus.HEALTHY
    assert third.message == "Redis is healthy"


@pytest.mark.asyncio
async def test_redis_health_checker_can_degrade_immediately_with_threshold_one(monkeypatch):
    checker = RedisHealthChecker(
        latency_threshold_ms=500.0,
        latency_samples=1,
        consecutive_degraded=1,
    )
    checker.component = _FakeRedisComponent()

    monkeypatch.setattr(checker, "_measure_ping_latency", AsyncMock(return_value=522.0))
    result = await checker.check()

    assert result.status == HealthStatus.DEGRADED
    assert "streak=1" in result.message


@pytest.mark.asyncio
async def test_redis_health_checker_metrics_streak_matches_status(monkeypatch):
    checker = RedisHealthChecker(
        latency_threshold_ms=500.0,
        latency_samples=1,
        consecutive_degraded=2,
    )
    checker.component = _FakeRedisComponent()

    probe = AsyncMock(side_effect=[520.0, 530.0, 420.0])
    monkeypatch.setattr(checker, "_measure_ping_latency", probe)

    first = await checker.check()
    second = await checker.check()
    third = await checker.check()

    assert first.status == HealthStatus.HEALTHY
    assert first.metrics is not None
    assert first.metrics.custom_metrics["high_latency_streak"] == 1

    assert second.status == HealthStatus.DEGRADED
    assert second.metrics is not None
    assert second.metrics.custom_metrics["high_latency_streak"] == 2

    assert third.status == HealthStatus.HEALTHY
    assert third.metrics is not None
    assert third.metrics.custom_metrics["high_latency_streak"] == 0


@pytest.mark.asyncio
async def test_redis_health_checker_info_failure_keeps_check_result_available(monkeypatch):
    checker = RedisHealthChecker(
        latency_threshold_ms=500.0,
        latency_samples=1,
        consecutive_degraded=2,
    )
    checker.component = _InfoFailureRedisComponent()

    monkeypatch.setattr(checker, "_measure_ping_latency", AsyncMock(return_value=120.0))
    result = await checker.check()

    assert result.status == HealthStatus.HEALTHY
    assert result.metrics is not None
    assert result.metrics.memory_usage_mb is None
    assert result.details["used_memory"] == "unknown"
    assert result.metrics.custom_metrics["high_latency_streak"] == 0
