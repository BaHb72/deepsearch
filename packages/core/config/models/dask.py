"""
Dask 分布式计算配置模型。

支持 Windows Worker 自启动和任务路由配置。
"""

from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class MemoryThresholdsConfig(BaseModel):
    """Dask Worker 内存管理阈值配置

    Dask 使用分层阈值管理内存，各阈值触发不同行为：
    - target: 超过此值开始 spill 最少使用的数据到磁盘
    - spill: 超过此值强制激进 spill，直到降到 target 以下
    - pause: 超过此值暂停接收新任务，等待 spill 完成
    - terminate: 超过此值 Nanny 进程终止 Worker 并重新调度任务

    参考: https://distributed.dask.org/en/stable/worker-memory.html
    """

    target: float = Field(
        default=0.60, ge=0.0, le=1.0, description="开始 spill 到磁盘的阈值（默认 60%）"
    )
    spill: float = Field(
        default=0.70, ge=0.0, le=1.0, description="强制激进 spill 的阈值（默认 70%）"
    )
    pause: float = Field(
        default=0.80, ge=0.0, le=1.0, description="暂停接收新任务的阈值（默认 80%）"
    )
    terminate: float = Field(
        default=0.95, ge=0.0, le=1.0, description="Nanny 终止 Worker 的阈值（默认 95%）"
    )


class SchedulerConfig(BaseModel):
    """Dask Scheduler 配置

    支持本地自动启动或连接外部 Scheduler（如 Docker 中运行的）。
    当 prefer_external=True 时，优先检测并使用外部 Scheduler，
    仅在外部不可用且 auto_start=True 时启动本地 Scheduler。
    """

    enabled: bool = Field(default=True, description="是否启用 Scheduler 管理")
    auto_start: bool = Field(
        default=True, description="外部 Scheduler 不可用时自动启动本地 Scheduler"
    )
    host: str = Field(default="localhost", description="Scheduler 监听地址")
    port: int = Field(default=8786, description="Scheduler 监听端口")
    dashboard_port: int = Field(default=8787, description="Dashboard 端口")
    dashboard_enabled: bool = Field(default=True, description="是否启用 Dashboard")
    startup_timeout: float = Field(default=30.0, description="启动超时时间（秒）")
    prefer_external: bool = Field(
        default=True, description="优先使用外部 Scheduler（如 Docker 中的）"
    )


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
    contact_host: Optional[str] = Field(
        default=None,
        description="Worker 对外公布地址（覆盖自动判定；例如 host.docker.internal 或宿主机 IP）",
    )
    local_directory: Optional[str] = Field(
        default=None, description="Worker 本地临时目录（用于 spill to disk），建议使用 SSD"
    )
    use_nanny: bool = Field(
        default=True, description="是否使用 Nanny 进程监管 Worker（启用后 terminate 阈值才生效）"
    )


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
    scheduler: Optional[SchedulerConfig] = Field(
        default=None,
        description="Scheduler 管理配置（自动启动等）",
    )
    windows_workers: Optional[WindowsWorkersConfig] = Field(
        default=None,
        description="Windows Workers 配置",
    )
    task_routing: Optional[TaskRoutingConfig] = Field(
        default=None,
        description="任务路由配置",
    )
    memory_thresholds: MemoryThresholdsConfig = Field(
        default_factory=MemoryThresholdsConfig,
        description="Worker 内存管理阈值配置",
    )
