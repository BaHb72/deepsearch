"""
GC 历史持久化服务

提供 GC 执行记录的持久化存储和查询
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from loguru import logger


class GCPersistence:
    """GC 历史持久化服务（占位符实现）"""

    _instance: Optional["GCPersistence"] = None

    def __new__(cls) -> "GCPersistence":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        self._history: List[Dict[str, Any]] = []

    def record(
        self,
        result: Dict[str, Any],
        trigger_type: str = "manual",
    ) -> None:
        """记录 GC 执行结果"""
        record = {
            **result,
            "trigger_type": trigger_type,
            "recorded_at": datetime.now().isoformat(),
        }
        self._history.append(record)

        # 限制历史记录数量
        if len(self._history) > 1000:
            self._history = self._history[-1000:]

        logger.debug(f"GC 记录已保存: {trigger_type}")

    def get_recent(self, limit: int = 20) -> List[Dict[str, Any]]:
        """获取最近的 GC 记录"""
        return self._history[-limit:]

    def query(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        trigger_type: Optional[Literal["manual", "periodic", "threshold", "shutdown"]] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """按条件查询 GC 记录"""
        results = self._history.copy()

        if trigger_type:
            results = [r for r in results if r.get("trigger_type") == trigger_type]

        if start:
            results = [
                r
                for r in results
                if datetime.fromisoformat(r.get("recorded_at", "1970-01-01")) >= start
            ]

        if end:
            results = [
                r
                for r in results
                if datetime.fromisoformat(r.get("recorded_at", "2099-12-31")) <= end
            ]

        return results[offset : offset + limit]

    def get_stats(
        self,
        period: Literal["hour", "day", "week", "month"] = "day",
    ) -> Dict[str, Any]:
        """获取统计摘要"""
        if not self._history:
            return {
                "period": period,
                "total_gc_count": 0,
                "total_freed_mb": 0,
                "avg_freed_mb": 0,
                "avg_duration_ms": 0,
            }

        total_freed = sum(r.get("memory_freed_mb", 0) for r in self._history)
        total_duration = sum(r.get("duration_ms", 0) for r in self._history)
        count = len(self._history)

        return {
            "period": period,
            "total_gc_count": count,
            "total_freed_mb": round(total_freed, 2),
            "avg_freed_mb": round(total_freed / count, 2) if count > 0 else 0,
            "avg_duration_ms": round(total_duration / count, 2) if count > 0 else 0,
        }


# 全局实例
_gc_persistence: Optional[GCPersistence] = None


def get_gc_persistence() -> GCPersistence:
    """获取 GC 持久化服务实例"""
    global _gc_persistence
    if _gc_persistence is None:
        _gc_persistence = GCPersistence()
    return _gc_persistence
