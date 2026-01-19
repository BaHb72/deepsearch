"""
统一 Provider 工厂

使用策略模式，将具体创建逻辑委托给各个数据源的专属工厂。
"""

from typing import Any

from loguru import logger

from ..exceptions import UnknownProviderError
from .akshare_factory import AkShareFactory
from .amazingdata_factory import AmazingDataFactory
from .base import ProviderFactoryStrategy
from .miniqmt_factory import MiniQMTFactory


class ProviderFactory:
    """统一 Provider 工厂

    使用策略模式，将具体创建逻辑委托给各个数据源的专属工厂。
    """

    def __init__(self):
        self._strategies: dict[str, ProviderFactoryStrategy] = {
            "amazingdata": AmazingDataFactory(),
            "miniqmt": MiniQMTFactory(),
            "akshare": AkShareFactory(),
        }

    def create(self, name: str, config: dict[str, Any]) -> Any:
        """创建 Provider 实例

        Args:
            name: Provider 名称
            config: 配置字典

        Returns:
            Provider 实例

        Raises:
            UnknownProviderError: 未知的 Provider
            ConfigValidationError: 配置验证失败
            ProviderCreationError: 创建失败
        """
        strategy = self._strategies.get(name)
        if strategy is None:
            raise UnknownProviderError(provider=name, available=list(self._strategies.keys()))

        logger.debug(f"使用 {strategy.__class__.__name__} 创建 Provider")
        return strategy.create(config)

    def register(self, name: str, factory: ProviderFactoryStrategy) -> None:
        """注册新的 Provider 工厂

        Args:
            name: Provider 名称
            factory: 工厂实例
        """
        self._strategies[name] = factory
        logger.info(f"注册 Provider 工厂: {name}")

    def list_providers(self) -> list[str]:
        """列出所有已注册的 Provider 类型"""
        return list(self._strategies.keys())

    def get_registered_providers(self) -> list[str]:
        """获取所有已注册的 Provider 名称（list_providers 的别名）"""
        return self.list_providers()

    def validate_config(self, name: str, config: dict[str, Any]) -> None:
        """验证 Provider 配置

        Args:
            name: Provider 名称
            config: 配置字典

        Raises:
            UnknownProviderError: 未知的 Provider
            ConfigValidationError: 配置验证失败
        """
        strategy = self._strategies.get(name)
        if strategy is None:
            raise UnknownProviderError(provider=name, available=list(self._strategies.keys()))

        strategy.validate_config(config)
