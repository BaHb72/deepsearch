"""
AmazingData Provider 工厂
"""

from typing import Any

from loguru import logger

from ..exceptions import ConfigValidationError, ProviderCreationError
from ..implementations.amazingdata.amazingdata_optimized import OptimizedAmazingDataProvider
from ..implementations.amazingdata.config import (
    ensure_amazingdata_provider_config,
)
from .base import ProviderFactoryStrategy


class AmazingDataFactory:
    """AmazingData Provider 工厂

    负责创建和配置 AmazingDataProvider 实例
    """

    def validate_config(self, config: dict[str, Any]) -> None:
        """验证 AmazingData 配置"""
        try:
            # 使用 ensure_amazingdata_provider_config 来处理各种配置格式
            validated = ensure_amazingdata_provider_config(config)
            if not validated.username or not validated.password:
                raise ValueError("缺少必需字段: username, password")
        except Exception as e:
            raise ConfigValidationError(provider="amazingdata", message=f"配置验证失败: {e}") from e

    def create(self, config: dict[str, Any]) -> OptimizedAmazingDataProvider:
        """创建 AmazingData Provider"""
        try:
            # 1. 使用统一的配置解析函数处理各种格式
            validated_config = ensure_amazingdata_provider_config(config)

            # 2. 验证必需字段
            if not validated_config.username or not validated_config.password:
                raise ConfigValidationError(
                    provider="amazingdata", message="缺少必需字段: username, password"
                )

            # 3. 创建实例
            provider = OptimizedAmazingDataProvider(validated_config)

            logger.info(
                "AmazingData Provider 创建成功",
                extra={
                    "host": validated_config.host,
                    "port": validated_config.port,
                    "username": (
                        validated_config.username[:3] + "***"
                        if validated_config.username
                        else "N/A"
                    ),
                },
            )

            return provider

        except ConfigValidationError:
            raise
        except Exception as e:
            raise ProviderCreationError(provider="amazingdata", message=f"创建失败: {e}") from e


# 验证是否符合 ProviderFactoryStrategy 协议
if __name__ == "__main__":

    factory = AmazingDataFactory()
    assert isinstance(
        factory, ProviderFactoryStrategy
    ), "AmazingDataFactory 必须实现 ProviderFactoryStrategy 协议"
