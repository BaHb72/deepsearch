"""
DataFeed 工厂模块

提供统一的数据源获取入口，支持多 Provider 注册和懒加载。
"""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any, Awaitable, Callable, TypeVar, Union

from loguru import logger

from .idatafeed import IDataFeed

if TYPE_CHECKING:
    pass

# 工厂函数类型：同步或异步
FactoryFunc = Union[
    Callable[[], IDataFeed],
    Callable[[], Awaitable[IDataFeed]],
]

_T = TypeVar("_T", bound=IDataFeed)


class DataFeedFactory:
    """统一数据源工厂

    提供跨供应商（AmazingData, MiniQMT, AkShare）的统一数据源获取接口。

    Example:
        >>> from core.interfaces import DataFeedFactory
        >>> feed = await DataFeedFactory.get("miniqmt")
        >>> calendar = await feed.get_calendar()

    注册自定义数据源:
        >>> DataFeedFactory.register("custom", lambda: MyCustomProvider())
    """

    # 注册表：名称 -> 工厂函数
    _registry: dict[str, FactoryFunc] = {}

    # 实例缓存：名称 -> 已创建实例
    _instances: dict[str, IDataFeed] = {}

    @classmethod
    def register(
        cls,
        name: str,
        factory: FactoryFunc,
        *,
        override: bool = False,
    ) -> None:
        """注册数据源工厂函数

        Args:
            name: 数据源名称（如 "amazingdata", "miniqmt", "akshare"）
            factory: 工厂函数，可以是同步或异步函数
            override: 是否覆盖已存在的注册
        """
        if name in cls._registry and not override:
            logger.warning(f"DataFeed '{name}' 已注册，跳过重复注册")
            return

        cls._registry[name] = factory
        logger.debug(f"已注册 DataFeed: {name}")

    @classmethod
    async def get(
        cls,
        name: str,
        *,
        new: bool = False,
    ) -> IDataFeed:
        """获取数据源实例

        Args:
            name: 数据源名称
            new: 是否强制创建新实例（默认使用缓存）

        Returns:
            IDataFeed 实例

        Raises:
            KeyError: 未注册的数据源名称
        """
        # 检查缓存
        if not new and name in cls._instances:
            instance = cls._instances[name]
            logger.debug(f"返回缓存的 DataFeed: {name}")
            return instance

        # 获取工厂函数
        factory = cls._registry.get(name)
        if factory is None:
            available = ", ".join(cls._registry.keys()) or "(无)"
            raise KeyError(f"未知的数据源: '{name}'。可用数据源: {available}")

        # 创建实例
        logger.debug(f"创建 DataFeed 实例: {name}")
        if inspect.iscoroutinefunction(factory):
            instance = await factory()
        else:
            instance = factory()  # type: ignore[assignment]

        # 缓存实例
        cls._instances[name] = instance
        return instance

    @classmethod
    def get_sync(cls, name: str) -> IDataFeed | None:
        """同步获取已缓存的数据源实例

        仅返回已创建的实例，不会触发新实例创建。

        Args:
            name: 数据源名称

        Returns:
            已缓存的实例，或 None
        """
        return cls._instances.get(name)

    @classmethod
    def list_feeds(cls) -> list[str]:
        """列出所有已注册的数据源名称"""
        return list(cls._registry.keys())

    @classmethod
    def list_active(cls) -> list[str]:
        """列出所有已创建实例的数据源名称"""
        return list(cls._instances.keys())

    @classmethod
    def is_registered(cls, name: str) -> bool:
        """检查数据源是否已注册"""
        return name in cls._registry

    @classmethod
    def clear_cache(cls, name: str | None = None) -> None:
        """清除实例缓存

        Args:
            name: 指定数据源名称，或 None 清除全部
        """
        if name is None:
            cls._instances.clear()
            logger.debug("已清除所有 DataFeed 缓存")
        elif name in cls._instances:
            del cls._instances[name]
            logger.debug(f"已清除 DataFeed 缓存: {name}")

    @classmethod
    def unregister(cls, name: str) -> bool:
        """取消注册数据源

        Args:
            name: 数据源名称

        Returns:
            是否成功取消
        """
        if name in cls._registry:
            del cls._registry[name]
            cls._instances.pop(name, None)
            logger.debug(f"已取消注册 DataFeed: {name}")
            return True
        return False


# ==================== 默认 Provider 注册 ====================


def _register_default_providers() -> None:
    """注册默认的数据源 Provider

    在模块加载时自动调用，注册以下 Provider：
    - miniqmt: MiniQMT 量化终端
    - akshare: AkShare 代理服务
    - amazingdata: 需要通过 register_amazingdata_provider 单独注册
    """

    def _create_miniqmt() -> Any:
        """延迟导入并创建 MiniQMT Provider"""
        from core.infrastructure.providers.implementations.qmt.miniqmt import MiniQMTProvider

        return MiniQMTProvider()

    def _create_akshare() -> Any:
        """延迟导入并创建 AkShare Provider"""
        from core.infrastructure.providers.implementations.akshare.akshare_refactored import (
            AkShareProxyProvider,
        )

        return AkShareProxyProvider()

    # 注册本地 Provider
    DataFeedFactory.register("miniqmt", _create_miniqmt)
    DataFeedFactory.register("akshare", _create_akshare)

    logger.debug("默认 DataFeed Provider 已注册: miniqmt, akshare")


def register_amazingdata_provider(actor_factory: FactoryFunc) -> None:
    """注册 AmazingData Provider

    由于 AmazingData 需要通过 Dask Actor 获取，需要在 Dask Client 可用后单独注册。

    Args:
        actor_factory: 返回 AmazingData Actor Proxy 的工厂函数

    Example:
        >>> async def get_amazingdata_actor():
        ...     from core.compute.actors import get_amazingdata_actor
        ...     return await get_amazingdata_actor()
        >>> register_amazingdata_provider(get_amazingdata_actor)
    """
    DataFeedFactory.register("amazingdata", actor_factory, override=True)
    logger.info("AmazingData DataFeed Provider 已注册")


# 模块加载时注册默认 Provider
_register_default_providers()
