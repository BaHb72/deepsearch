"""
统一数据服务入口。

提供工厂函数和全局访问点。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Optional

from core.config.models.capability_routing import CapabilityRoutingConfig
from core.infrastructure.providers.adapters.base import BaseProviderAdapter
from core.infrastructure.providers.binder import UnifiedDataFeed
from core.infrastructure.providers.capability_router import CapabilityRouter
from loguru import logger

if TYPE_CHECKING:
    pass


# 全局单例
_unified_feed: Optional[UnifiedDataFeed] = None
_router: Optional[CapabilityRouter] = None


def get_unified_feed() -> UnifiedDataFeed:
    """
    获取全局 UnifiedDataFeed 实例。

    Returns:
        UnifiedDataFeed 单例

    Raises:
        RuntimeError: 未初始化
    """
    global _unified_feed
    if _unified_feed is None:
        raise RuntimeError("UnifiedDataFeed not initialized. Call initialize_unified_feed() first.")
    return _unified_feed


def get_capability_router() -> CapabilityRouter:
    """
    获取全局 CapabilityRouter 实例。

    Returns:
        CapabilityRouter 单例

    Raises:
        RuntimeError: 未初始化
    """
    global _router
    if _router is None:
        raise RuntimeError(
            "CapabilityRouter not initialized. Call initialize_unified_feed() first."
        )
    return _router


def initialize_unified_feed(
    config: Optional[CapabilityRoutingConfig] = None,
    adapters: Optional[Dict[str, BaseProviderAdapter]] = None,
) -> UnifiedDataFeed:
    """
    初始化统一数据服务。

    Args:
        config: 能力路由配置，可选（默认从配置文件加载）
        adapters: 预注册的适配器，可选

    Returns:
        初始化后的 UnifiedDataFeed 实例
    """
    global _unified_feed, _router

    # 加载配置
    if config is None:
        config = _load_default_config()

    # 创建路由器
    _router = CapabilityRouter(config, adapters or {})

    # 自动注册默认适配器
    if not adapters:
        _register_default_adapters(_router, config)

    # 创建 ReferenceDataCapability
    from core.infrastructure.providers.reference_capability import (
        IStockListProvider,
        ReferenceDataCapability,
    )

    reference = ReferenceDataCapability()

    # 从路由器收集支持股票列表的适配器
    for adapter in _router._adapters.values():
        if isinstance(adapter, IStockListProvider):
            reference.register_provider(adapter)

    # 创建统一入口（组合模式）
    _unified_feed = UnifiedDataFeed(_router, reference)

    logger.info("UnifiedDataFeed 初始化完成（含 ReferenceDataCapability）")
    return _unified_feed


def _load_default_config() -> CapabilityRoutingConfig:
    """从配置文件加载默认配置"""
    try:
        from core.config import get_config

        app_config = get_config()
        capability_routing = getattr(app_config, "capability_routing", None)
        if capability_routing and isinstance(capability_routing, dict):
            return CapabilityRoutingConfig.model_validate(capability_routing)
    except Exception as e:
        logger.warning(f"加载 capability_routing 配置失败: {e}，使用默认配置")

    return CapabilityRoutingConfig()


def _register_default_adapters(
    router: CapabilityRouter,
    config: CapabilityRoutingConfig,
) -> None:
    """注册默认适配器"""
    try:
        # 尝试注册 MiniQMT 适配器
        from core.infrastructure.providers.adapters.miniqmt import MiniQMTAdapter
        from core.infrastructure.providers.registry import get_registry

        registry = get_registry()
        miniqmt_provider = registry.get_provider_instance("miniqmt")

        if miniqmt_provider:
            # 获取能力声明
            capabilities = config.capabilities.get("miniqmt")
            adapter = MiniQMTAdapter(miniqmt_provider, capabilities)
            router.register_adapter("miniqmt", adapter)

    except Exception as e:
        logger.warning(f"注册 MiniQMT 适配器失败: {e}")

    # 可以继续注册其他适配器...


def reset_unified_feed() -> None:
    """重置全局实例（主要用于测试）"""
    global _unified_feed, _router
    # 先停止聚合引擎
    stop_aggregation_engine()
    _unified_feed = None
    _router = None


# ========== 聚合引擎管理 ==========

_aggregation_engine_started = False


def start_aggregation_engine() -> None:
    """
    启动聚合引擎。

    需要在 asyncio 事件循环中调用。
    引擎启动后会定时计算已注册的聚合并缓存结果。
    """
    global _aggregation_engine_started

    if _aggregation_engine_started:
        logger.warning("聚合引擎已启动")
        return

    # 如果 UnifiedDataFeed 未初始化，自动初始化
    global _unified_feed
    if _unified_feed is None:
        logger.info("自动初始化 UnifiedDataFeed...")
        initialize_unified_feed()

    # 导入聚合模块（触发注册）
    from core.application.services.aggregation import get_engine
    from core.application.services.aggregation import impl as _  # noqa: F401

    engine = get_engine()
    if _unified_feed is not None:
        engine.set_feed(_unified_feed)
    engine.start()
    _aggregation_engine_started = True
    logger.info("聚合引擎已启动")


def stop_aggregation_engine() -> None:
    """停止聚合引擎。"""
    global _aggregation_engine_started

    if not _aggregation_engine_started:
        return

    from core.application.services.aggregation import get_engine

    get_engine().stop()
    _aggregation_engine_started = False
    logger.info("聚合引擎已停止")


__all__ = [
    "get_unified_feed",
    "get_capability_router",
    "initialize_unified_feed",
    "reset_unified_feed",
    "start_aggregation_engine",
    "stop_aggregation_engine",
]
