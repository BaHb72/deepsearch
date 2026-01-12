"""
聚合注册表。

提供 @register_aggregation 装饰器和全局注册表。
"""

from __future__ import annotations

from typing import Dict, Type

from .base import BaseAggregation

# 全局注册表: {name: aggregation_class}
_registry: Dict[str, Type[BaseAggregation]] = {}


def register_aggregation(name: str):
    """
    注册聚合类的装饰器。

    Usage:
        @register_aggregation("top_gainers")
        class TopGainersAggregation(BaseAggregation):
            ...
    """

    def decorator(cls: Type[BaseAggregation]) -> Type[BaseAggregation]:
        cls.name = name
        _registry[name] = cls
        return cls

    return decorator


def get_registry() -> Dict[str, Type[BaseAggregation]]:
    """获取所有已注册的聚合类。"""
    return _registry.copy()


def get_aggregation_class(name: str) -> Type[BaseAggregation] | None:
    """根据名称获取聚合类。"""
    return _registry.get(name)


__all__ = [
    "register_aggregation",
    "get_registry",
    "get_aggregation_class",
]
