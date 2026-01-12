from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Sequence

import pytest
from core.application.services.data_sources import DataSourcePrefetchScheduler, IngestionJobSummary
from core.config.models import DataSourcePrefetchConfig
from core.ports.data_sources import DataAccessType, DataSourceType


class StubIngestionService:
    """在测试中模拟 DataSourceIngestionService 行为。"""

    def __init__(self, summaries: Sequence[IngestionJobSummary | None]) -> None:
        self._queue: List[IngestionJobSummary | None] = list(summaries)
        self.calls = 0

    async def ensure_stock_list_job(self, force: bool = False) -> IngestionJobSummary | None:
        self.calls += 1
        if not self._queue:
            return None
        if len(self._queue) == 1:
            return self._queue[0]
        return self._queue.pop(0)


def _make_summary(
    job_id: str,
    status: str,
    *,
    expires_minutes: int = 30,
    completed: bool = False,
) -> IngestionJobSummary:
    now = datetime.now(timezone.utc)
    completed_at = now if completed else None
    expires_at = now + timedelta(minutes=expires_minutes)
    return IngestionJobSummary(
        job_id=job_id,
        job_type="prefetch_stock_basics",
        data_source=DataSourceType.AMAZINGDATA,
        access_type=DataAccessType.STOCK_LIST,
        status=status,
        queued_at=now,
        started_at=None,
        completed_at=completed_at,
        expires_at=expires_at,
        record_count=None,
        error_message=None,
        metadata={},
    )


@pytest.mark.asyncio
async def test_run_once_skips_outside_window() -> None:
    service = StubIngestionService([])
    cfg = DataSourcePrefetchConfig(enabled=True, interval_seconds=60)
    scheduler = DataSourcePrefetchScheduler(
        ingestion_service=service, config=cfg, time_checker=lambda: False
    )

    triggered = await scheduler.run_once()

    assert triggered is False
    assert service.calls == 0


@pytest.mark.asyncio
async def test_run_once_triggers_new_job() -> None:
    summary = _make_summary("job-1", "queued")
    service = StubIngestionService([summary])
    cfg = DataSourcePrefetchConfig(enabled=True, interval_seconds=60)
    scheduler = DataSourcePrefetchScheduler(
        ingestion_service=service, config=cfg, time_checker=lambda: True
    )

    triggered = await scheduler.run_once()

    assert triggered is True
    assert service.calls == 1


@pytest.mark.asyncio
async def test_run_once_detects_active_job() -> None:
    first = _make_summary("job-1", "queued")
    second = _make_summary("job-1", "queued")
    service = StubIngestionService([first, second])
    cfg = DataSourcePrefetchConfig(enabled=True, interval_seconds=60)
    scheduler = DataSourcePrefetchScheduler(
        ingestion_service=service, config=cfg, time_checker=lambda: True
    )

    assert await scheduler.run_once() is True  # 第一次创建新作业
    assert await scheduler.run_once() is False  # 第二次复用正在运行的作业
    assert service.calls == 2


@pytest.mark.asyncio
async def test_start_respects_disabled_config() -> None:
    service = StubIngestionService([])
    cfg = DataSourcePrefetchConfig(enabled=False)
    scheduler = DataSourcePrefetchScheduler(
        ingestion_service=service, config=cfg, time_checker=lambda: True
    )

    started = await scheduler.start()

    assert started is False
