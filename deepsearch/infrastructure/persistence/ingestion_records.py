"""数据源快照持久化/读取工具。"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from typing import Any, Iterable, Mapping, MutableMapping, Sequence

from sqlalchemy import insert, update

from deepsearch.domain.market_data import StockListRecord
from deepsearch.infrastructure.persistence.models.ingestion import (
    IngestionBatch,
    IngestionJob,
    RawProviderPayload,
)
from deepsearch.infrastructure.persistence.models.market import MarketSnapshot
from deepsearch.infrastructure.persistence.types import DatabaseServiceProtocol
from deepsearch.ports.data_sources import (
    DataAccessType,
    DataSourceType,
    PersistedRecordSet,
    PersistedRecordSetEnvelope,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _chunk_records(records: Sequence[Mapping[str, Any]], chunk_size: int) -> Iterable[list[dict[str, Any]]]:
    bucket: list[dict[str, Any]] = []
    for record in records:
        bucket.append(dict(record))
        if len(bucket) >= chunk_size:
            yield bucket
            bucket = []
    if bucket:
        yield bucket


def _record_checksum(records: Sequence[Mapping[str, Any]]) -> str:
    digest = hashlib.sha256()
    for record in records:
        serialized = json.dumps(record, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        digest.update(serialized)
    return digest.hexdigest()


def _ensure_mapping(record: StockListRecord | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(record, StockListRecord):
        return dict(record.as_mapping())
    return dict(record)


class DataSourceRecordPersistence:
    """管理数据源取数落库与快照读取。"""

    def __init__(self, db: DatabaseServiceProtocol) -> None:
        self._db = db

    async def load_latest_record_set(
        self,
        *,
        job_type: str,
        data_source: DataSourceType,
        access_type: DataAccessType,
        max_age: timedelta | None = None,
    ) -> PersistedRecordSet | None:
        """加载最新的成功记录。"""

        params: dict[str, object] = {
            "job_type": job_type,
            "data_source": data_source.value,
            "access_type": access_type.value,
            "status": "succeeded",
        }
        clauses = [
            "job_type = :job_type",
            "data_source = :data_source",
            "access_type = :access_type",
            "status = :status",
        ]

        now_value = _utcnow()
        params["now_ts"] = now_value
        clauses.append("(expires_at IS NULL OR expires_at > :now_ts)")

        if max_age is not None:
            params["age_threshold"] = now_value - max_age
            clauses.append("completed_at >= :age_threshold")

        job_query = f"""
            SELECT id, queued_at AS requested_at, completed_at, expires_at, checksum, record_count, job_metadata
            FROM ingestion_jobs
            WHERE {' AND '.join(clauses)}
            ORDER BY completed_at DESC NULLS LAST, queued_at DESC
            LIMIT 1
        """
        job_row = await self._db.fetch_one(job_query, params)
        if not job_row:
            return None

        records_query = """
            SELECT payload
            FROM market_snapshots
            WHERE job_id = :job_id
            ORDER BY symbol
        """
        payload_rows = await self._db.fetch_all(records_query, {"job_id": job_row["id"]})
        normalized_records: list[dict[str, Any]] = []
        for row in payload_rows:
            payload = row.get("payload")
            payload_obj: dict[str, Any] | None = None
            if isinstance(payload, Mapping):
                payload_obj = dict(payload)
            elif isinstance(payload, str):
                try:
                    parsed = json.loads(payload)
                    if isinstance(parsed, Mapping):
                        payload_obj = dict(parsed)
                except json.JSONDecodeError:
                    payload_obj = None
            if payload_obj is not None:
                normalized_records.append(payload_obj)

        return PersistedRecordSetEnvelope(
            id=str(job_row.get("id")),
            source=data_source,
            access_type=access_type,
            requested_at=self._coerce_dt(job_row.get("requested_at")) or now_value,
            completed_at=self._coerce_dt(job_row.get("completed_at")),
            expires_at=self._coerce_dt(job_row.get("expires_at")),
            checksum=str(job_row.get("checksum")) if job_row.get("checksum") else None,
            record_count=int(job_row.get("record_count") or len(normalized_records)),
            metadata=self._coerce_mapping(job_row.get("job_metadata")),
            records=tuple(normalized_records),
        )

    async def persist_stock_list(
        self,
        records: Sequence[StockListRecord | Mapping[str, object]],
        *,
        job_type: str,
        data_source: DataSourceType,
        access_type: DataAccessType = DataAccessType.STOCK_LIST,
        chunk_size: int = 500,
        metadata: Mapping[str, object] | None = None,
        parameters: Mapping[str, object] | None = None,
        expires_in: timedelta | None = None,
        priority: int | None = None,
        job_id: str | None = None,
        requested_at: datetime | None = None,
    ) -> PersistedRecordSet:
        """按批将股票列表写入数据库。"""

        normalized: list[dict[str, Any]] = [_ensure_mapping(record) for record in records]
        requested_at = requested_at or _utcnow()
        checksum = _record_checksum(normalized) if normalized else None
        expires_at = requested_at + expires_in if expires_in else None
        job_metadata: MutableMapping[str, object] = dict(metadata or {})
        job_metadata.setdefault("chunk_size", chunk_size)
        provided_job_id = job_id

        try:
            async with self._db.transaction() as session:
                if job_id:
                    await session.execute(
                        update(IngestionJob)
                        .where(IngestionJob.id == job_id)
                        .values(
                            status="running",
                            started_at=requested_at,
                            expires_at=expires_at,
                            checksum=checksum,
                            job_metadata=job_metadata,
                            parameters=dict(parameters or {}),
                            priority=priority,
                        )
                    )
                else:
                    job_id = uuid4().hex
                    await session.execute(
                        insert(IngestionJob).values(
                            id=job_id,
                            job_type=job_type,
                            data_source=data_source.value,
                            access_type=access_type.value,
                            status="running",
                            queued_at=requested_at,
                            started_at=requested_at,
                            job_metadata=job_metadata,
                            parameters=dict(parameters or {}),
                            checksum=checksum,
                            record_count=len(normalized),
                            expires_at=expires_at,
                            priority=priority,
                        )
                    )

                for index, chunk in enumerate(_chunk_records(normalized, max(1, chunk_size))):
                    batch_stmt = (
                        insert(IngestionBatch)
                        .values(
                            job_id=job_id,
                            batch_index=index,
                            status="writing",
                            record_count=len(chunk),
                            requested_at=requested_at,
                            batch_metadata={
                                "start_symbol": chunk[0].get("symbol"),
                                "end_symbol": chunk[-1].get("symbol"),
                            },
                        )
                        .returning(IngestionBatch.id)
                    )
                    batch_id_result = await session.execute(batch_stmt)
                    batch_id = batch_id_result.scalar_one()

                    await session.execute(
                        insert(RawProviderPayload).values(
                            job_id=job_id,
                            batch_id=batch_id,
                            data_source=data_source.value,
                            access_type=access_type.value,
                            row_count=len(chunk),
                            payload=chunk,
                            schema=list(chunk[0].keys()) if chunk else [],
                            collected_at=requested_at,
                        )
                    )

                    snapshot_rows: list[dict[str, object]] = []
                    for record in chunk:
                        boards = record.get("boards") or record.get("board")
                        board_value = None
                        if isinstance(boards, Sequence):
                            board_value = boards[0] if boards else None
                        elif isinstance(boards, str):
                            board_value = boards

                        as_of_raw = record.get("as_of")
                        as_of_value = self._coerce_dt(as_of_raw) if as_of_raw is not None else requested_at

                        snapshot_rows.append(
                            {
                                "job_id": job_id,
                                "batch_id": batch_id,
                                "symbol": record.get("symbol"),
                                "name": record.get("name") or record.get("symbol"),
                                "board": board_value,
                                "boards": record.get("boards"),
                                "exchange": record.get("exchange"),
                                "market": record.get("market"),
                                "security_type": record.get("security_type"),
                                "status": record.get("status"),
                                "list_date": record.get("list_date"),
                                "delist_date": record.get("delist_date"),
                                "payload": record,
                                "snapshot_metadata": {"job_type": job_type},
                                "data_source": data_source.value,
                                "access_type": access_type.value,
                                "as_of": as_of_value,
                                "ingested_at": requested_at,
                                "record_hash": _record_checksum([record]),
                                "tags": record.get("tags"),
                            }
                        )

                    if snapshot_rows:
                        await session.execute(insert(MarketSnapshot), snapshot_rows)

                    await session.execute(
                        update(IngestionBatch)
                        .where(IngestionBatch.id == batch_id)
                        .values(status="succeeded", completed_at=_utcnow())
                    )

                await session.execute(
                    update(IngestionJob)
                    .where(IngestionJob.id == job_id)
                    .values(
                        status="succeeded",
                        completed_at=_utcnow(),
                        error_message=None,
                        record_count=len(normalized),
                    )
                )
        except Exception as exc:
            if provided_job_id:
                await self.update_job_status(
                    provided_job_id,
                    status="failed",
                    error_message=str(exc),
                    record_count=len(normalized) or None,
                )
            raise

        return PersistedRecordSetEnvelope(
            id=job_id,
            source=data_source,
            access_type=access_type,
            requested_at=requested_at,
            completed_at=_utcnow(),
            expires_at=expires_at,
            checksum=checksum,
            record_count=len(normalized),
            records=tuple(normalized),
            metadata=job_metadata,
        )

    async def create_job(
        self,
        *,
        job_type: str,
        data_source: DataSourceType,
        access_type: DataAccessType,
        expires_in: timedelta | None = None,
        parameters: Mapping[str, Any] | None = None,
        metadata: Mapping[str, Any] | None = None,
        priority: int | None = None,
    ) -> str:
        """创建排队中的取数作业。"""

        job_id = uuid4().hex
        queued_at = _utcnow()
        expires_at = queued_at + expires_in if expires_in else None
        async with self._db.transaction() as session:
            await session.execute(
                insert(IngestionJob).values(
                    id=job_id,
                    job_type=job_type,
                    data_source=data_source.value,
                    access_type=access_type.value,
                    status="queued",
                    queued_at=queued_at,
                    expires_at=expires_at,
                    job_metadata=dict(metadata or {}),
                    parameters=dict(parameters or {}),
                    priority=priority,
                )
            )
        return job_id

    async def update_job_status(
        self,
        job_id: str,
        *,
        status: str,
        error_message: str | None = None,
        record_count: int | None = None,
        metadata: Mapping[str, Any] | None = None,
        completed: bool = False,
    ) -> None:
        """更新作业状态。"""

        values: dict[str, Any] = {"status": status}
        if error_message is not None:
            values["error_message"] = error_message
        if record_count is not None:
            values["record_count"] = record_count
        if metadata is not None:
            values["job_metadata"] = dict(metadata)
        if completed:
            values["completed_at"] = _utcnow()
        async with self._db.transaction() as session:
            await session.execute(update(IngestionJob).where(IngestionJob.id == job_id).values(values))

    async def fetch_jobs(self, *, job_type: str | None = None, limit: int = 20) -> list[Mapping[str, Any]]:
        """查询最近的作业记录。"""

        clauses: list[str] = []
        params: dict[str, Any] = {"limit": limit}
        if job_type:
            clauses.append("job_type = :job_type")
            params["job_type"] = job_type
        where_clause = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        query = f"""
            SELECT id, job_type, data_source, access_type, status, queued_at, started_at,
                   completed_at, expires_at, record_count, error_message, job_metadata
            FROM ingestion_jobs
            {where_clause}
            ORDER BY queued_at DESC
            LIMIT :limit
        """
        return await self._db.fetch_all(query, params)

    async def fetch_job(self, job_id: str) -> Mapping[str, Any] | None:
        """根据 ID 获取作业详情。"""

        query = """
            SELECT id, job_type, data_source, access_type, status, queued_at, started_at,
                   completed_at, expires_at, record_count, error_message, job_metadata
            FROM ingestion_jobs
            WHERE id = :job_id
        """
        return await self._db.fetch_one(query, {"job_id": job_id})

    @staticmethod
    def _coerce_dt(value: Any | None) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        try:
            parsed = datetime.fromisoformat(str(value))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed

    @staticmethod
    def _coerce_mapping(value: Any | None) -> Mapping[str, Any]:
        if isinstance(value, Mapping):
            return value
        return {}


__all__ = ["DataSourceRecordPersistence"]
