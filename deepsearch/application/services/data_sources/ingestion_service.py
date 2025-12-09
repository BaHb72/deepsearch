"""数据源后台取数作业服务。"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Mapping, Sequence

from loguru import logger

from deepsearch.core.components.data_components import DatabaseComponent
from deepsearch.core.managers.component_manager import ComponentManager
from deepsearch.infrastructure.persistence.database import DatabaseService
from deepsearch.infrastructure.persistence.ingestion_records import DataSourceRecordPersistence
from deepsearch.infrastructure.providers.implementations.amazingdata.ports import build_board_source
from deepsearch.ports.data_sources import DataAccessType, DataSourceType
from deepsearch.utils.data_sources import DataSourceManager, get_data_source_manager


from deepsearch.core.runtime.context import get_context

def _get_database_service() -> DatabaseService:
    component = get_context().get_component("database")
    if not isinstance(component, DatabaseComponent):
        raise RuntimeError("数据库组件未初始化，无法创建持久化服务")
    return DatabaseService(component)


@dataclass(slots=True)
class IngestionJobSummary:
    job_id: str
    job_type: str
    data_source: DataSourceType
    access_type: DataAccessType
    status: str
    queued_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    expires_at: datetime | None
    record_count: int | None
    error_message: str | None
    metadata: Mapping[str, Any]

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> "IngestionJobSummary":
        return cls(
            job_id=str(row["id"]),
            job_type=str(row.get("job_type") or ""),
            data_source=DataSourceType(str(row.get("data_source") or DataSourceType.AMAZINGDATA.value)),
            access_type=DataAccessType(str(row.get("access_type") or DataAccessType.STOCK_LIST.value)),
            status=str(row.get("status") or "queued"),
            queued_at=row.get("queued_at"),
            started_at=row.get("started_at"),
            completed_at=row.get("completed_at"),
            expires_at=row.get("expires_at"),
            record_count=row.get("record_count"),
            error_message=row.get("error_message"),
            metadata=row.get("job_metadata") or {},
        )


class DataSourceIngestionService:
    """封装后台取数作业的生命周期管理与队列。"""

    _job_type = "prefetch_stock_basics"
    _job_access_type = DataAccessType.STOCK_LIST
    _job_data_source = DataSourceType.AMAZINGDATA

    def __init__(
        self,
        record_store: DataSourceRecordPersistence | None = None,
        manager: DataSourceManager | None = None,
        *,
        cache_ttl: timedelta = timedelta(minutes=30),
        expires_in: timedelta = timedelta(minutes=45),
    ) -> None:
        self._record_store = record_store
        self._manager = manager or get_data_source_manager()
        self._cache_ttl = cache_ttl
        self._job_expires = expires_in
        self._tasks: dict[str, asyncio.Task[Any]] = {}
        self._lock = asyncio.Lock()

    async def ensure_stock_list_job(self, *, force: bool = False) -> IngestionJobSummary:
        """确保存在一个执行中的股票列表预取作业。"""

        async with self._lock:
            existing = await self._latest_job()
            if existing and not force:
                if existing.status in {"queued", "running"}:
                    return existing
                if (
                    existing.status == "succeeded"
                    and existing.expires_at
                    and existing.expires_at > datetime.now(existing.expires_at.tzinfo or None)
                ):
                    return existing

            job_id = await self._store().create_job(
                job_type=self._job_type,
                data_source=self._job_data_source,
                access_type=self._job_access_type,
                expires_in=self._job_expires,
            )
            task = asyncio.create_task(
                self._run_prefetch_job(job_id),
                name=f"prefetch-stock-basics-{job_id}",
            )
            self._tasks[job_id] = task
            row = await self._store().fetch_job(job_id)
            return IngestionJobSummary.from_row(row or {"id": job_id, "status": "queued"})

    async def list_jobs(self, *, limit: int = 20) -> Sequence[IngestionJobSummary]:
        rows = await self._store().fetch_jobs(job_type=self._job_type, limit=limit)
        return [IngestionJobSummary.from_row(row) for row in rows]

    async def get_job(self, job_id: str) -> IngestionJobSummary | None:
        row = await self._store().fetch_job(job_id)
        return IngestionJobSummary.from_row(row) if row else None

    async def cancel_job(self, job_id: str) -> bool:
        task = self._tasks.get(job_id)
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            return True
        row = await self._store().fetch_job(job_id)
        if not row or str(row.get("status")) not in {"queued", "running"}:
            return False
        await self._store().update_job_status(
            job_id,
            status="cancelled",
            error_message="任务已取消",
            completed=True,
        )
        return True

    async def _latest_job(self) -> IngestionJobSummary | None:
        rows = await self._store().fetch_jobs(job_type=self._job_type, limit=1)
        if not rows:
            return None
        return IngestionJobSummary.from_row(rows[0])

    async def _run_prefetch_job(self, job_id: str) -> None:
        try:
            provider = self._manager.get_provider(self._job_data_source)
            if provider is None:
                raise RuntimeError("未找到可用的数据源适配器")
            board_source = build_board_source(
                provider,
                record_store=self._store(),
                cache_ttl=self._cache_ttl,
            )
            await board_source.fetch_records(use_cache=False, job_id=job_id)
        except asyncio.CancelledError:
            await self._store().update_job_status(
                job_id,
                status="cancelled",
                error_message="任务已被取消",
                completed=True,
            )
            raise
        except Exception as exc:  # pragma: no cover - 防御性日志
            logger.exception("后台预取股票列表失败 job_id=%s", job_id)
            await self._store().update_job_status(
                job_id,
                status="failed",
                error_message=str(exc),
                completed=True,
            )
        finally:
            self._tasks.pop(job_id, None)

    def _store(self) -> DataSourceRecordPersistence:
        if self._record_store is None:
            self._record_store = DataSourceRecordPersistence(_get_database_service())
        return self._record_store


__all__ = ["DataSourceIngestionService", "IngestionJobSummary"]
