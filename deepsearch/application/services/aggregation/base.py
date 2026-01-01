"""
聚合框架基础模块。

提供 BaseAggregation 抽象类和相关类型定义。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from deepsearch.infrastructure.providers.binder import UnifiedDataFeed


class BaseAggregation(ABC):
    """
    聚合计算基类。

    子类需实现 compute 方法，返回聚合结果。
    """

    # 刷新间隔（秒），子类可覆盖
    interval: int = 60

    # 聚合名称，由 registry 自动设置
    name: str = ""

    @abstractmethod
    async def compute(self, feed: "UnifiedDataFeed") -> Any:
        """
        执行聚合计算。

        Args:
            feed: UnifiedDataFeed 实例，用于获取原始数据

        Returns:
            聚合结果，类型由子类定义
        """
        ...


__all__ = ["BaseAggregation"]
