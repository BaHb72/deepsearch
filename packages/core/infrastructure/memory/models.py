"""
内存管理数据模型

定义内存监控和GC相关的数据结构
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class MemoryStats(BaseModel):
    """内存统计信息"""

    process_id: int = Field(description="进程 ID")
    rss_mb: float = Field(description="常驻内存 (MB)")
    vms_mb: float = Field(description="虚拟内存 (MB)")
    threads: int = Field(description="线程数")
    open_files: int = Field(description="打开文件数")
    gc_counts: List[int] = Field(description="GC 计数 (0, 1, 2 代)")
    gc_thresholds: List[int] = Field(description="GC 阈值")
    python_objects: int = Field(description="Python 对象数")


class GCResult(BaseModel):
    """GC 执行结果"""

    collected: List[int] = Field(description="各代回收的对象数")
    uncollectable: int = Field(description="无法回收的对象数")
    duration_ms: float = Field(description="执行时间 (毫秒)")
    memory_before_mb: float = Field(description="GC 前内存 (MB)")
    memory_after_mb: float = Field(description="GC 后内存 (MB)")
    memory_freed_mb: float = Field(description="释放内存 (MB)")
    timestamp: Optional[str] = Field(default=None, description="执行时间戳")


class MemoryConfig(BaseModel):
    """内存管理配置"""

    gc_enabled: bool = Field(default=True, description="是否启用定时 GC")
    gc_interval_seconds: int = Field(default=300, description="GC 间隔 (秒)")
    gc_log_enabled: bool = Field(default=True, description="是否记录 GC 日志")


class ProcessMemoryInfo(BaseModel):
    """进程内存信息"""

    pid: int = Field(description="进程 ID")
    name: str = Field(description="进程名")
    rss_mb: float = Field(description="常驻内存 (MB)")
    threads: int = Field(description="线程数")


class TraceStatus(BaseModel):
    """内存追踪状态"""

    is_tracing: bool = Field(description="是否正在追踪")
    current_mb: float = Field(description="当前追踪内存 (MB)")
    peak_mb: float = Field(description="峰值追踪内存 (MB)")
    snapshots: List[str] = Field(description="可用快照列表")


class MemoryAllocation(BaseModel):
    """内存分配信息"""

    location: str = Field(description="代码位置")
    size_mb: float = Field(description="内存大小 (MB)")
    count: int = Field(description="对象数量")


class MemoryDiff(BaseModel):
    """内存差异信息"""

    location: str = Field(description="代码位置")
    size_diff_mb: float = Field(description="内存差异 (MB)")
    count_diff: int = Field(description="对象数量差异")
    size_mb: float = Field(description="当前内存大小 (MB)")
