"""
Data Source Router

路由决策逻辑，基于延迟和可用性选择最佳数据源。
"""

from __future__ import annotations

import time
from collections import deque
from typing import TYPE_CHECKING, Sequence

from loguru import logger

if TYPE_CHECKING:
    from .interfaces import DataSourceAdapter


class LatencyTracker:
    """追踪每个数据源的实时延迟

    使用滑动窗口记录最近 N 次请求的延迟，用于动态选择最佳数据源。
    """

    def __init__(self, window_size: int = 10, default_latency_ms: float = 999.0):
        """初始化延迟追踪器

        Args:
            window_size: 滑动窗口大小
            default_latency_ms: 无数据时的默认延迟
        """
        self._latencies: dict[str, deque[float]] = {}
        self._window_size = window_size
        self._default_latency = default_latency_ms
        self._last_updated: dict[str, float] = {}

    def record(self, source: str, latency_ms: float) -> None:
        """记录一次请求的延迟

        Args:
            source: 数据源名称
            latency_ms: 延迟（毫秒）
        """
        if source not in self._latencies:
            self._latencies[source] = deque(maxlen=self._window_size)
        self._latencies[source].append(latency_ms)
        self._last_updated[source] = time.time()

    def get_avg_latency(self, source: str) -> float:
        """获取数据源的平均延迟

        Args:
            source: 数据源名称

        Returns:
            平均延迟（毫秒）
        """
        if source not in self._latencies or len(self._latencies[source]) == 0:
            return self._default_latency
        return sum(self._latencies[source]) / len(self._latencies[source])

    def get_best_source(self, sources: Sequence[str]) -> str | None:
        """返回平均延迟最低的数据源

        Args:
            sources: 候选数据源列表

        Returns:
            最佳数据源名称，如果没有候选则返回 None
        """
        if not sources:
            return None

        avg_latencies = {s: self.get_avg_latency(s) for s in sources}
        best = min(avg_latencies, key=lambda k: avg_latencies[k])
        logger.debug(
            "路由选择: {} (延迟 {:.1f}ms), 候选: {}",
            best,
            avg_latencies[best],
            {k: f"{v:.1f}ms" for k, v in avg_latencies.items()},
        )
        return best

    def get_statistics(self) -> dict[str, dict[str, float]]:
        """获取所有数据源的延迟统计

        Returns:
            {source: {avg_ms, min_ms, max_ms, count}}
        """
        stats = {}
        for source, latencies in self._latencies.items():
            if latencies:
                stats[source] = {
                    "avg_ms": sum(latencies) / len(latencies),
                    "min_ms": min(latencies),
                    "max_ms": max(latencies),
                    "count": len(latencies),
                    "last_updated": self._last_updated.get(source, 0),
                }
        return stats


class DataSourceRouter:
    """数据源路由决策

    根据能力、延迟和优先级选择最佳数据源。
    """

    def __init__(
        self,
        adapters: dict[str, "DataSourceAdapter"] | None = None,
        priority: Sequence[str] | None = None,
    ):
        """初始化路由器

        Args:
            adapters: 数据源适配器字典 {name: adapter}
            priority: 优先级列表 (用于 fallback)
        """
        self._adapters: dict[str, DataSourceAdapter] = adapters or {}
        self._priority = list(priority) if priority else []
        self._latency_tracker = LatencyTracker()
        self._availability: dict[str, bool] = {}

    def register_adapter(self, adapter: "DataSourceAdapter") -> None:
        """注册数据源适配器

        Args:
            adapter: 数据源适配器实例
        """
        self._adapters[adapter.name] = adapter
        if adapter.name not in self._priority:
            self._priority.append(adapter.name)
        logger.info("注册数据源适配器: {}", adapter.name)

    def unregister_adapter(self, name: str) -> None:
        """注销数据源适配器

        Args:
            name: 数据源名称
        """
        if name in self._adapters:
            del self._adapters[name]
        if name in self._priority:
            self._priority.remove(name)

    async def select_source(
        self,
        capability: str,
        preference: str = "latency",
        exclude: Sequence[str] | None = None,
    ) -> str | None:
        """根据能力和偏好选择数据源

        Args:
            capability: 需要的能力 (如 "kline", "realtime")
            preference: 选择策略 ("latency" | "priority")
            exclude: 排除的数据源列表

        Returns:
            选中的数据源名称，如果没有合适的返回 None
        """
        exclude_set = set(exclude or [])

        # 收集支持该能力的可用数据源
        candidates: list[str] = []
        for name, adapter in self._adapters.items():
            if name in exclude_set:
                continue
            if capability not in adapter.capabilities:
                continue
            # 检查可用性（使用缓存）
            if await self._check_availability(name):
                candidates.append(name)

        if not candidates:
            logger.warning("没有可用的数据源支持能力: {}", capability)
            return None

        # 根据偏好选择
        if preference == "latency":
            return self._latency_tracker.get_best_source(candidates)
        elif preference == "priority":
            # 按优先级排序
            for name in self._priority:
                if name in candidates:
                    return name
            return candidates[0] if candidates else None
        else:
            return candidates[0]

    async def _check_availability(self, name: str) -> bool:
        """检查数据源可用性（带缓存）

        Args:
            name: 数据源名称

        Returns:
            是否可用
        """
        # TODO: 实现可用性缓存和定期刷新
        if name not in self._adapters:
            return False
        try:
            return await self._adapters[name].is_available()
        except Exception as e:
            logger.warning("检查数据源 {} 可用性失败: {}", name, e)
            return False

    def record_latency(self, source: str, latency_ms: float) -> None:
        """记录请求延迟

        Args:
            source: 数据源名称
            latency_ms: 延迟（毫秒）
        """
        self._latency_tracker.record(source, latency_ms)

    def get_latency_stats(self) -> dict[str, dict[str, float]]:
        """获取延迟统计"""
        return self._latency_tracker.get_statistics()

    def get_adapter(self, name: str) -> "DataSourceAdapter | None":
        """获取指定的适配器

        Args:
            name: 数据源名称

        Returns:
            适配器实例或 None
        """
        return self._adapters.get(name)

    def list_adapters(self) -> list[str]:
        """列出所有注册的适配器名称"""
        return list(self._adapters.keys())
