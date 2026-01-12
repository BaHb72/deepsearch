"""
内存追踪器

使用 tracemalloc 检测内存泄漏
"""

from __future__ import annotations

import threading
import tracemalloc
from typing import Any, Dict, List, Optional

from loguru import logger


class MemoryTracer:
    """内存追踪器 - 使用 tracemalloc 检测泄漏"""

    _instance: Optional["MemoryTracer"] = None
    _lock = threading.Lock()
    _initialized: bool

    def __new__(cls) -> "MemoryTracer":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True

        self._snapshots: Dict[str, tracemalloc.Snapshot] = {}
        self._is_tracing = False

    def start_tracing(self, nframe: int = 25) -> Dict[str, Any]:
        """启动内存追踪"""
        if self._is_tracing:
            return {
                "success": False,
                "message": "追踪已在运行中",
                "is_tracing": True,
            }

        tracemalloc.start(nframe)
        self._is_tracing = True
        logger.info(f"tracemalloc 内存追踪已启动 (nframe={nframe})")

        return {
            "success": True,
            "message": f"内存追踪已启动，追踪深度 {nframe} 帧",
            "is_tracing": True,
        }

    def stop_tracing(self) -> Dict[str, Any]:
        """停止内存追踪"""
        if not self._is_tracing:
            return {
                "success": False,
                "message": "追踪未在运行",
                "is_tracing": False,
            }

        tracemalloc.stop()
        self._is_tracing = False
        self._snapshots.clear()
        logger.info("tracemalloc 内存追踪已停止")

        return {
            "success": True,
            "message": "内存追踪已停止",
            "is_tracing": False,
        }

    def take_snapshot(self, name: str = "default") -> Dict[str, Any]:
        """拍摄内存快照"""
        if not self._is_tracing:
            return {
                "success": False,
                "message": "请先启动追踪",
            }

        snapshot = tracemalloc.take_snapshot()
        self._snapshots[name] = snapshot

        current, peak = tracemalloc.get_traced_memory()

        logger.info(f"内存快照 '{name}' 已保存 (当前: {current / 1024 / 1024:.1f}MB)")

        return {
            "success": True,
            "message": f"快照 '{name}' 已保存",
            "snapshot_name": name,
            "current_mb": round(current / 1024 / 1024, 2),
            "peak_mb": round(peak / 1024 / 1024, 2),
            "available_snapshots": list(self._snapshots.keys()),
        }

    def get_top_allocations(
        self, snapshot_name: str = "default", limit: int = 20, key_type: str = "lineno"
    ) -> Dict[str, Any]:
        """获取内存分配 Top N"""
        if snapshot_name not in self._snapshots:
            return {
                "success": False,
                "message": f"快照 '{snapshot_name}' 不存在",
                "available_snapshots": list(self._snapshots.keys()),
            }

        snapshot = self._snapshots[snapshot_name]
        top_stats = snapshot.statistics(key_type)[:limit]

        allocations = []
        for stat in top_stats:
            allocations.append(
                {
                    "location": str(stat.traceback),
                    "size_mb": round(stat.size / 1024 / 1024, 3),
                    "count": stat.count,
                }
            )

        return {
            "success": True,
            "snapshot_name": snapshot_name,
            "key_type": key_type,
            "allocations": allocations,
        }

    def compare_snapshots(
        self, old_name: str = "baseline", new_name: str = "current", limit: int = 20
    ) -> Dict[str, Any]:
        """比较两个快照，检测内存增长"""
        if old_name not in self._snapshots:
            return {
                "success": False,
                "message": f"旧快照 '{old_name}' 不存在",
                "available_snapshots": list(self._snapshots.keys()),
            }
        if new_name not in self._snapshots:
            return {
                "success": False,
                "message": f"新快照 '{new_name}' 不存在",
                "available_snapshots": list(self._snapshots.keys()),
            }

        old_snapshot = self._snapshots[old_name]
        new_snapshot = self._snapshots[new_name]

        diff_stats = new_snapshot.compare_to(old_snapshot, "lineno")[:limit]

        increases: List[Dict[str, Any]] = []
        total_diff = 0
        for stat in diff_stats:
            if stat.size_diff > 0:
                increases.append(
                    {
                        "location": str(stat.traceback),
                        "size_diff_mb": round(stat.size_diff / 1024 / 1024, 3),
                        "count_diff": stat.count_diff,
                        "size_mb": round(stat.size / 1024 / 1024, 3),
                    }
                )
                total_diff += stat.size_diff

        return {
            "success": True,
            "old_snapshot": old_name,
            "new_snapshot": new_name,
            "total_increase_mb": round(total_diff / 1024 / 1024, 2),
            "increases": increases,
            "potential_leaks": len([i for i in increases if float(str(i["size_diff_mb"])) > 1]),
        }

    def get_status(self) -> Dict[str, Any]:
        """获取追踪状态"""
        if self._is_tracing:
            current, peak = tracemalloc.get_traced_memory()
            return {
                "is_tracing": True,
                "current_mb": round(current / 1024 / 1024, 2),
                "peak_mb": round(peak / 1024 / 1024, 2),
                "snapshots": list(self._snapshots.keys()),
            }
        return {
            "is_tracing": False,
            "current_mb": 0,
            "peak_mb": 0,
            "snapshots": [],
        }


# 全局实例
_memory_tracer: Optional[MemoryTracer] = None


def get_memory_tracer() -> MemoryTracer:
    """获取内存追踪器实例"""
    global _memory_tracer
    if _memory_tracer is None:
        _memory_tracer = MemoryTracer()
    return _memory_tracer
