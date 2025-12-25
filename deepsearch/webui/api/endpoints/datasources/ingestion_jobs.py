"""数据源后台取数作业接口。

使用 FastAPI 依赖注入模式管理服务生命周期，
遵循最佳实践确保数据库连接在正确的事件循环中初始化。
"""

from __future__ import annotations

from typing import Optional, Sequence

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from deepsearch.application.services.data_sources import (
    DataSourceIngestionService,
    IngestionJobSummary,
)
from deepsearch.webui.api.deps import get_optional_ingestion_service

router = APIRouter(prefix="/api/data-sources/jobs", tags=["DataSource Jobs"])


class JobSummaryPayload(BaseModel):
    jobId: str = Field(..., description="作业 ID")
    jobType: str
    dataSource: str
    accessType: str
    status: str
    queuedAt: str | None = None
    startedAt: str | None = None
    completedAt: str | None = None
    expiresAt: str | None = None
    recordCount: int | None = None
    errorMessage: str | None = None

    @classmethod
    def from_summary(cls, summary: IngestionJobSummary) -> "JobSummaryPayload":
        def _ts(value: object | None) -> str | None:
            if value is None:
                return None
            if hasattr(value, "isoformat"):
                return value.isoformat()
            return str(value)

        return cls(
            jobId=summary.job_id,
            jobType=summary.job_type,
            dataSource=summary.data_source.value,
            accessType=summary.access_type.value,
            status=summary.status,
            queuedAt=_ts(summary.queued_at),
            startedAt=_ts(summary.started_at),
            completedAt=_ts(summary.completed_at),
            expiresAt=_ts(summary.expires_at),
            recordCount=summary.record_count,
            errorMessage=summary.error_message,
        )


class PrefetchRequest(BaseModel):
    force: bool = Field(False, description="是否无视缓存强制触发新的后台任务")


class JobListResponse(BaseModel):
    jobs: Sequence[JobSummaryPayload]


@router.get("/", response_model=JobListResponse)
async def list_ingestion_jobs(
    job_type: str = Query("prefetch_stock_basics", description="过滤的作业类型"),
    limit: int = Query(20, ge=1, le=100),
    service: Optional[DataSourceIngestionService] = Depends(get_optional_ingestion_service),
) -> JobListResponse:
    """
    列出数据源取数作业。
    
    使用可选的服务依赖，当数据库不可用时返回空列表。
    """
    if job_type != "prefetch_stock_basics":
        raise HTTPException(status_code=400, detail="暂不支持的作业类型")
    
    # 如果服务不可用（数据库未连接），返回空列表
    if service is None:
        return JobListResponse(jobs=[])
    
    try:
        jobs = await service.list_jobs(limit=limit)
        return JobListResponse(jobs=[JobSummaryPayload.from_summary(job) for job in jobs])
    except Exception as e:
        # 捕获事件循环或数据库连接相关错误，返回空列表
        error_msg = str(e)
        if "Event loop is closed" in error_msg or "connection" in error_msg.lower():
            return JobListResponse(jobs=[])
        raise


@router.post("/prefetch-stock-basics", response_model=JobSummaryPayload)
async def trigger_prefetch_job(
    payload: PrefetchRequest,
    service: Optional[DataSourceIngestionService] = Depends(get_optional_ingestion_service),
) -> JobSummaryPayload:
    """
    触发股票列表预取作业。
    """
    if service is None:
        raise HTTPException(status_code=503, detail="数据库服务不可用")
    
    summary = await service.ensure_stock_list_job(force=payload.force)
    return JobSummaryPayload.from_summary(summary)


@router.post("/{job_id}/cancel")
async def cancel_job(
    job_id: str,
    service: Optional[DataSourceIngestionService] = Depends(get_optional_ingestion_service),
) -> dict[str, bool]:
    """
    取消指定作业。
    """
    if service is None:
        raise HTTPException(status_code=503, detail="数据库服务不可用")
    
    success = await service.cancel_job(job_id)
    if not success:
        raise HTTPException(status_code=404, detail="作业不存在或已经完成")
    return {"success": True}
