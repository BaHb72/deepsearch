"""
数据源后台预取调度配置。

该模块定义 ``data_source_prefetch`` 配置块的结构，用于控制
prefetch_stock_basics 调度器的开关与节奏。
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class DataSourcePrefetchConfig(BaseModel):
    """数据源后台预取调度器配置。"""

    enabled: bool = Field(
        default=True,
        description="是否启用调度器；关闭后仅允许手动触发预取。",
    )
    interval_seconds: int = Field(
        default=300,
        ge=30,
        description="调度器 tick 周期（秒），建议不低于 30s。",
    )
    job_type: str = Field(
        default="prefetch_stock_basics",
        description="目标作业类型，当前仅支持股票基础信息预取。",
    )
    max_job_age_minutes: int = Field(
        default=45,
        ge=1,
        description="多少分钟内已成功的作业可复用，超时则重新触发。",
    )


__all__ = ["DataSourcePrefetchConfig"]
