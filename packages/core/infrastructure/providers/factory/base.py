"""
Provider 工厂基础接口

使用纯 Protocol，不混用 @abstractmethod。
"""

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ProviderFactoryStrategy(Protocol):
    """Provider 工厂策略接口

    每个数据源实现自己的工厂类，负责：
    1. 验证配置
    2. 创建 Provider 实例
    3. 处理特定数据源的初始化逻辑

    注意：这是纯 Protocol，不使用 @abstractmethod。
    """

    def validate_config(self, config: dict[str, Any]) -> None:
        """验证配置

        Args:
            config: 原始配置字典

        Raises:
            ConfigValidationError: 配置验证失败
        """
        ...

    def create(self, config: dict[str, Any]) -> Any:
        """创建 Provider 实例

        Args:
            config: 已验证的配置

        Returns:
            Provider 实例

        Raises:
            ProviderCreationError: 创建失败
        """
        ...
