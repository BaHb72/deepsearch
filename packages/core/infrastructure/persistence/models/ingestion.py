"""数据源拉取作业与批次 ORM 模型。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from core.utils.time.market_time import now
from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class IngestionJob(Base):
    """后台取数作业，用于跟踪持久化流程。"""

    __tablename__ = "ingestion_jobs"

    # 必填字段
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    job_type: Mapped[str] = mapped_column(String(64), index=True)
    data_source: Mapped[str] = mapped_column(String(32), index=True)
    access_type: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), index=True)
    queued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    # 可选字段
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), default=None)
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), index=True, default=None
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), default=None)
    parameters: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, default=None)
    job_metadata: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, default=None)
    error_message: Mapped[Optional[str]] = mapped_column(Text, default=None)
    checksum: Mapped[Optional[str]] = mapped_column(String(64), default=None)
    record_count: Mapped[Optional[int]] = mapped_column(default=None)
    priority: Mapped[Optional[int]] = mapped_column(default=None)

    # 自动生成字段
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        init=False,
    )


class IngestionBatch(Base):
    """作业内按批写库的元数据。"""

    __tablename__ = "ingestion_batches"
    __table_args__ = (
        UniqueConstraint("job_id", "batch_index", name="uq_ingestion_batches_job_idx"),
    )

    # 必填字段
    job_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("ingestion_jobs.id", ondelete="CASCADE"),
        index=True,
    )
    batch_index: Mapped[int] = mapped_column()
    status: Mapped[str] = mapped_column(String(32), index=True)
    record_count: Mapped[int] = mapped_column()
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    # 可选字段
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), default=None)
    batch_metadata: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, default=None)
    checksum: Mapped[Optional[str]] = mapped_column(String(64), default=None)
    error_message: Mapped[Optional[str]] = mapped_column(Text, default=None)

    # 自动生成字段
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, init=False)


class RawProviderPayload(Base):
    """按批保存 Provider 原始返回，便于后续追溯。"""

    __tablename__ = "raw_provider_payload"

    # 必填字段
    job_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("ingestion_jobs.id", ondelete="CASCADE"),
    )
    batch_id: Mapped[int] = mapped_column(
        ForeignKey("ingestion_batches.id", ondelete="CASCADE"),
        index=True,
    )
    data_source: Mapped[str] = mapped_column(String(32), index=True)
    access_type: Mapped[str] = mapped_column(String(32))
    row_count: Mapped[int] = mapped_column()
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)

    # 可选字段
    schema: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, default=None)

    # 自动生成字段
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, init=False)
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default_factory=lambda: now(),
        init=False,
    )


__all__ = ["IngestionJob", "IngestionBatch", "RawProviderPayload"]
