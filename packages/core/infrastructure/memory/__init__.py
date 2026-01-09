"""
内存管理基础设施模块

提供:
- MemoryManager: 内存监控和GC管理
- MemoryTracer: tracemalloc 内存追踪
- 数据模型和持久化服务
"""

from core.infrastructure.memory.manager import MemoryManager, get_memory_manager
from core.infrastructure.memory.models import (
    GCResult,
    MemoryAllocation,
    MemoryConfig,
    MemoryDiff,
    MemoryStats,
    ProcessMemoryInfo,
    TraceStatus,
)
from core.infrastructure.memory.tracer import MemoryTracer, get_memory_tracer

__all__ = [
    # 管理器
    "MemoryManager",
    "get_memory_manager",
    # 追踪器
    "MemoryTracer",
    "get_memory_tracer",
    # 数据模型
    "GCResult",
    "MemoryAllocation",
    "MemoryConfig",
    "MemoryDiff",
    "MemoryStats",
    "ProcessMemoryInfo",
    "TraceStatus",
]
