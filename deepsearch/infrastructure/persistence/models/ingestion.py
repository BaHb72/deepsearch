"""数据源拉取作业与批次 ORM 模型。"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)

from .base import Base

JSONType = JSON


class IngestionJob(Base):
    """后台取数作业，用于跟踪持久化流程。"""

    __tablename__ = "ingestion_jobs"

    id = Column(String(64), primary_key=True)
    job_type = Column(String(64), nullable=False, index=True)
    data_source = Column(String(32), nullable=False, index=True)
    access_type = Column(String(32), nullable=False)
    status = Column(String(32), nullable=False, index=True)
    queued_at = Column(DateTime(timezone=True), nullable=False, index=True)
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True), index=True)
    expires_at = Column(DateTime(timezone=True))
    parameters = Column(JSONType)
    job_metadata = Column(JSONType)
    error_message = Column(Text)
    checksum = Column(String(64))
    record_count = Column(Integer)
    priority = Column(Integer)
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class IngestionBatch(Base):
    """作业内按批写库的元数据。"""

    __tablename__ = "ingestion_batches"
    __table_args__ = (
        UniqueConstraint("job_id", "batch_index", name="uq_ingestion_batches_job_idx"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(
        String(64),
        ForeignKey("ingestion_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    batch_index = Column(Integer, nullable=False)
    status = Column(String(32), nullable=False, index=True)
    record_count = Column(Integer, nullable=False)
    requested_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True))
    batch_metadata = Column(JSONType)
    checksum = Column(String(64))
    error_message = Column(Text)


class RawProviderPayload(Base):
    """按批保存 Provider 原始返回，便于后续追溯。"""

    __tablename__ = "raw_provider_payload"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(
        String(64),
        ForeignKey("ingestion_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    batch_id = Column(
        Integer,
        ForeignKey("ingestion_batches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    data_source = Column(String(32), nullable=False, index=True)
    access_type = Column(String(32), nullable=False)
    row_count = Column(Integer, nullable=False)
    payload = Column(JSONType, nullable=False)
    schema = Column(JSONType)
    collected_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


__all__ = ["IngestionJob", "IngestionBatch", "RawProviderPayload"]
