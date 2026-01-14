"""
Dask 分布式计算配置模型。

支持 Windows Worker 自启动和任务路由配置。
"""

from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class WindowsWorkersConfig(BaseModel):
    """Windows Dask Workers 配置"""

    enabled: bool = Field(default=False, description="是否启用 Windows Workers")
    auto_start: bool = Field(default=False, description="后端启动时自动启动")
    num_workers: int = Field(default=2, description="Worker 数量")
    threads_per_worker: int = Field(default=2, description="每个 Worker 的线程数")
    memory_limit: str = Field(default="4GB", description="内存限制")
    name_prefix: str = Field(default="windows-worker", description="Worker 名称前缀")
    resources: Dict[str, float] = Field(
        default_factory=lambda: {"WIN": 1.0},
        description="Worker 资源标签（必须为浮点数，符合 Dask 内部要求）",
    )
    port_range_start: int = Field(default=58200, description="Worker 端口范围起始值")


class TaskRoutingConfig(BaseModel):
    """任务路由配置"""

    windows_tasks: List[str] = Field(
        default_factory=list,
        description="路由到 Windows Workers 的任务模式",
    )
    linux_tasks: List[str] = Field(
        default_factory=list,
        description="路由到 Linux Workers 的任务模式",
    )


class DaskConfig(BaseModel):
    """Dask 分布式计算配置"""

    scheduler_address: str = Field(
        default="localhost:8786",
        description="Dask Scheduler 地址",
    )
    windows_workers: Optional[WindowsWorkersConfig] = Field(
        default=None,
        description="Windows Workers 配置",
    )
    task_routing: Optional[TaskRoutingConfig] = Field(
        default=None,
        description="任务路由配置",
    )
