"""数据源后台预取调度器。"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

from deepsearch.application.services.data_sources.ingestion_service import (
    DataSourceIngestionService,
    IngestionJobSummary,
)
from deepsearch.config import get_config
from deepsearch.config.models import DataSourcePrefetchConfig
from deepsearch.observability import get_logger
from deepsearch.utils.time.market_time import MarketTimeUtil


def _default_time_checker() -> bool:
    """封装 MarketTimeUtil.should_prefetch，便于注入测试桩。"""

    return MarketTimeUtil.should_prefetch()


class DataSourcePrefetchScheduler:
    """根据时间窗口自动触发 `prefetch_stock_basics` 作业的调度器。"""

    def __init__(
        self,
        ingestion_service: Optional[DataSourceIngestionService] = None,
        *,
        config: Optional[DataSourcePrefetchConfig] = None,
        time_checker: Optional[Callable[[], bool]] = None,
    ) -> None:
        settings = get_config()
        resolved_config = config or getattr(settings, "data_source_prefetch", None) or DataSourcePrefetchConfig()
        self._config = resolved_config

        expires = timedelta(minutes=self._config.max_job_age_minutes)
        self._ingestion = ingestion_service or DataSourceIngestionService(expires_in=expires)
        self._time_checker = time_checker or _default_time_checker
        self._logger = get_logger(__name__)

        self._task: asyncio.Task[None] | None = None
        self._stop_event: asyncio.Event | None = None
        self._last_job_id: str | None = None

    async def start(self, *, run_immediate: bool = True) -> bool:
        """启动调度循环。"""

        if not self._config.enabled:
            self._logger.info("data_source_prefetch scheduler disabled via config")
            return False

        if self._task and not self._task.done():
            return True

        self._stop_event = asyncio.Event()
        interval = max(1.0, float(self._config.interval_seconds))
        self._task = asyncio.create_task(self._run_loop(interval), name="data-source-prefetch-scheduler")
        if run_immediate:
            await self.run_once()
        self._logger.info(
            "data_source_prefetch scheduler started interval=%s job_type=%s",
            interval,
            self._config.job_type,
        )
        return True

    async def stop(self) -> None:
        """优雅地停止调度循环。"""

        stop_event = self._stop_event
        if stop_event is not None and not stop_event.is_set():
            stop_event.set()

        task = self._task
        self._task = None
        self._stop_event = None
        if task:
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._logger.info("data_source_prefetch scheduler stopped")

    async def run_once(self) -> bool:
        """执行一次判断与触发流程，返回是否新建了作业。"""

        if not self._config.enabled:
            return False
        return await self._maybe_trigger()

    async def _run_loop(self, interval: float) -> None:
        """周期性 tick 循环。"""

        if self._stop_event is None:
            return
        while True:
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=interval)
                break
            except asyncio.TimeoutError:
                await self._maybe_trigger()
            except asyncio.CancelledError:
                break
            except Exception:
                self._logger.exception("data_source_prefetch scheduler tick failed")
                # 等待下个周期，避免任务退出

    async def _maybe_trigger(self) -> bool:
        """根据时间窗口与作业状态决定是否触发后台预取。"""

        if not self._time_checker():
            self._log_event(action="skip", reason="outside_window")
            return False

        summary: IngestionJobSummary | None = None
        try:
            summary = await self._ingestion.ensure_stock_list_job(force=False)
        except Exception as exc:  # pragma: no cover - 异常主要依赖日志排查
            self._log_event(action="error", reason="ensure_failed", error=exc)
            return False

        if summary is None:
            self._log_event(action="skip", reason="empty_summary")
            return False

        action = "skip"
        reason = "recent_success"
        triggered = False

        if summary.status in {"queued", "running"}:
            if summary.job_id == self._last_job_id:
                reason = "job_active"
            else:
                reason = "existing_job_expired" if self._last_job_id else "initial_prefetch"
                action = "trigger"
                triggered = True
        elif summary.status == "succeeded":
            if summary.expires_at and summary.expires_at > self._now(summary.expires_at):
                reason = "recent_success"
            else:
                reason = "success_expired"
        else:
            reason = f"status_{summary.status}"

        self._last_job_id = summary.job_id
        self._log_event(action=action, reason=reason, summary=summary)
        return triggered

    @staticmethod
    def _now(tz_source: datetime | None = None) -> datetime:
        if tz_source and tz_source.tzinfo:
            return datetime.now(tz_source.tzinfo)
        return datetime.now(timezone.utc)

    def _log_event(
        self,
        *,
        action: str,
        reason: str,
        summary: IngestionJobSummary | None = None,
        error: Exception | None = None,
    ) -> None:
        payload = {
            "scheduler": "data_source_prefetch",
            "action": action,
            "reason": reason,
        }
        if summary is not None:
            payload.update(
                {
                    "job_id": summary.job_id,
                    "status": summary.status,
                    "expires_at": self._fmt_ts(summary.expires_at),
                    "completed_at": self._fmt_ts(summary.completed_at),
                    "record_count": summary.record_count,
                }
            )
        if error is not None:
            self._logger.error("%s", payload, exc_info=error)
        else:
            self._logger.info("%s", payload)

    @staticmethod
    def _fmt_ts(value: datetime | None) -> str | None:
        if value is None:
            return None
        return value.isoformat()


__all__ = ["DataSourcePrefetchScheduler"]

