"""
AkShare Provider 工厂
"""

from typing import Any

from loguru import logger

from ..exceptions import ConfigValidationError, ProviderCreationError
from .base import ProviderFactoryStrategy


class AkShareFactory:
    """AkShare Provider 工厂

    负责创建和配置 AkShareProvider 实例
    """

    def validate_config(self, config: dict[str, Any]) -> None:
        """验证 AkShare 配置"""
        try:
            # AkShare 配置较简单，基础验证即可
            pass
        except Exception as e:
            raise ConfigValidationError(provider="akshare", message=f"配置验证失败: {e}") from e

    def create(self, config: dict[str, Any]) -> Any:
        """创建 AkShare Provider

        使用 AkShareProvider，支持两种访问模式：
        - mode: worker - 通过 Cloudflare Worker 代理（使用 proxy_client.py）
        - mode: direct - 直接调用 akshare 库
        """
        try:
            # 1. 验证配置
            self.validate_config(config)

            # 2. 动态导入 AkShareProvider
            from ..implementations.akshare.akshare_direct import AkShareProvider

            # 3. 提取嵌套的 config 字段
            nested_config = config.get("config", {})
            if not isinstance(nested_config, dict):
                nested_config = {}

            # 4. 创建实例，传入配置
            provider = AkShareProvider(config=nested_config)

            logger.info("AkShare Provider 创建成功")

            return provider

        except ConfigValidationError:
            raise
        except Exception as e:
            raise ProviderCreationError(provider="akshare", message=f"创建失败: {e}") from e


# 验证是否符合 ProviderFactoryStrategy 协议
if __name__ == "__main__":
    factory = AkShareFactory()
    assert isinstance(
        factory, ProviderFactoryStrategy
    ), "AkShareFactory 必须实现 ProviderFactoryStrategy 协议"
