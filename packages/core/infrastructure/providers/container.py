"""
Provider 容器

职责：
1. 管理 Provider 实例（单例模式，但不是全局单例）
2. 协调 Factory 和 LifecycleManager
3. 提供依赖注入接口

Note:
    此类不是全局单例，每个应用实例有自己的容器。
    测试时可以创建独立的容器实例。
"""

from typing import Any

from loguru import logger

from .exceptions import ProviderNotFoundError
from .factory.provider_factory import ProviderFactory
from .lifecycle.manager import ProviderLifecycleManager
from .protocols.lifecycle import HealthStatus


class ProviderContainer:
    """Provider 容器

    管理 Provider 的创建、初始化和生命周期。
    """

    def __init__(
        self,
        *,
        factory: ProviderFactory | None = None,
        lifecycle_manager: ProviderLifecycleManager | None = None,
    ):
        """初始化容器

        Args:
            factory: Provider 工厂（可选，默认创建新实例）
            lifecycle_manager: 生命周期管理器（可选，默认创建新实例）
        """
        self._factory = factory or ProviderFactory()
        self._lifecycle = lifecycle_manager or ProviderLifecycleManager()
        self._instances: dict[str, Any] = {}
        self._initialized: set[str] = set()

    async def get(self, name: str) -> Any:
        """获取已注册的 Provider

        Args:
            name: Provider 名称

        Returns:
            Provider 实例

        Raises:
            ProviderNotFoundError: Provider 不存在
        """
        if name not in self._instances:
            raise ProviderNotFoundError(
                provider=name, message=f"Provider '{name}' 未注册，请先调用 create_and_register()"
            )

        return self._instances[name]

    async def create_and_register(
        self,
        name: str,
        config: dict[str, Any],
        *,
        force_new: bool = False,
    ) -> Any:
        """创建、初始化并注册新 Provider

        Args:
            name: Provider 名称
            config: 配置字典
            force_new: 是否强制创建新实例（替换旧实例）

        Returns:
            Provider 实例

        Raises:
            UnknownProviderError: 未知的 Provider 类型
            ConfigValidationError: 配置验证失败
            ProviderCreationError: 创建失败
            ProviderInitializationError: 初始化失败
        """
        # 如果已存在且不强制创建，直接返回
        if not force_new and name in self._instances:
            logger.debug(f"Provider '{name}' 已存在，返回现有实例")
            return self._instances[name]

        # 如果强制创建，先停止旧实例
        if force_new and name in self._instances:
            logger.info(f"强制创建新实例，停止旧的 Provider: {name}")
            old_provider = self._instances[name]
            await self._lifecycle.stop(old_provider)
            del self._instances[name]
            self._initialized.discard(name)

        # 创建新实例
        logger.info(f"创建 Provider: {name}")
        provider = self._factory.create(name, config)

        # 初始化
        await self._lifecycle.initialize(provider)
        await self._lifecycle.start(provider)

        # 注册
        self._instances[name] = provider
        self._initialized.add(name)

        logger.info(f"Provider '{name}' 已创建并注册")
        return provider

    def register_external(self, name: str, provider: Any) -> None:
        """注册外部创建的 Provider 实例

        用于注册非通过 Factory 创建的 Provider（如 Dask 代理）。
        这些 Provider 需要自行管理初始化，此方法仅负责注册。

        Args:
            name: Provider 名称
            provider: Provider 实例（需实现 shutdown() 方法）
        """
        if name in self._instances:
            logger.warning(f"Provider '{name}' 已存在，将被覆盖")
        self._instances[name] = provider
        self._initialized.add(name)
        logger.info(f"外部 Provider '{name}' 已注册")

    def has(self, name: str) -> bool:
        """检查 Provider 是否存在

        Args:
            name: Provider 名称

        Returns:
            bool: 是否存在
        """
        return name in self._instances

    async def health_check(self, name: str) -> HealthStatus:
        """检查指定 Provider 的健康状态

        Args:
            name: Provider 名称

        Returns:
            HealthStatus: 健康状态

        Raises:
            ProviderNotFoundError: Provider 不存在
        """
        provider = await self.get(name)
        return await self._lifecycle.health_check(provider)

    async def health_check_all(self) -> dict[str, HealthStatus]:
        """检查所有 Provider 的健康状态

        Returns:
            dict[str, HealthStatus]: 健康状态字典
        """
        return await self._lifecycle.health_check_all(self._instances)

    async def shutdown(self) -> None:
        """关闭所有 Provider"""
        logger.info("开始关闭 ProviderContainer...")
        await self._lifecycle.shutdown_all(list(self._instances.values()))
        self._instances.clear()
        self._initialized.clear()
        logger.info("ProviderContainer 已关闭")

    def list_providers(self) -> list[str]:
        """列出所有已加载的 Provider"""
        return list(self._instances.keys())

    def list_available_types(self) -> list[str]:
        """列出所有可用的 Provider 类型"""
        return self._factory.list_providers()
