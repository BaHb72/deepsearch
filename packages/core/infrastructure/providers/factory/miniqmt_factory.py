"""
MiniQMT Provider 工厂
"""

from typing import Any

from loguru import logger

from ..exceptions import ConfigValidationError, ProviderCreationError
from ..interfaces.base import DataProviderConfig, DataSourceType
from .base import ProviderFactoryStrategy


class MiniQMTFactory:
    """MiniQMT Provider 工厂

    负责创建和配置 MiniQMTProvider 实例
    """

    def _build_config(self, config: dict[str, Any]) -> DataProviderConfig:
        """从字典构建 DataProviderConfig"""
        # 提取嵌套的 config 字段（如果存在）
        nested_config = config.get("config", {})
        if not isinstance(nested_config, dict):
            nested_config = {}

        return DataProviderConfig(
            name="miniqmt",
            source_type=DataSourceType.QMT,
            enabled=config.get("enabled", True),
            priority=config.get("priority", 100),
            timeout=config.get("timeout", 10.0),
            retry_count=config.get("retry_count", 3),
            config=nested_config,
        )

    def validate_config(self, config: dict[str, Any]) -> None:
        """验证 MiniQMT 配置"""
        try:
            # 尝试构建配置来验证
            self._build_config(config)
        except Exception as e:
            raise ConfigValidationError(provider="miniqmt", message=f"配置验证失败: {e}") from e

    def create(self, config: dict[str, Any]) -> Any:
        """创建 MiniQMT Provider"""
        try:
            # 1. 构建 DataProviderConfig
            provider_config = self._build_config(config)

            # 2. 动态导入（避免循环依赖）
            from ..implementations.qmt.miniqmt import MiniQMTProvider

            # 3. 创建实例
            provider = MiniQMTProvider(provider_config)

            logger.info("MiniQMT Provider 创建成功")

            return provider

        except ConfigValidationError:
            raise
        except Exception as e:
            raise ProviderCreationError(provider="miniqmt", message=f"创建失败: {e}") from e


# 验证是否符合 ProviderFactoryStrategy 协议
if __name__ == "__main__":
    factory = MiniQMTFactory()
    assert isinstance(
        factory, ProviderFactoryStrategy
    ), "MiniQMTFactory 必须实现 ProviderFactoryStrategy 协议"
