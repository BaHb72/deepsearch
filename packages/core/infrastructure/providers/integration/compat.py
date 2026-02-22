"""
向后兼容层

提供从旧的 DataProviderFactory 到新的 ProviderContainer 的过渡支持。
允许旧代码逐步迁移到新架构。
"""

from typing import Any

from loguru import logger

from ..container import ProviderContainer


class ProviderFactoryCompat:
    """
    DataProviderFactory 兼容层

    提供与旧 DataProviderFactory 相同的接口，但使用新的 ProviderContainer 实现。
    用于渐进式迁移，允许旧代码在迁移期间继续工作。
    """

    @classmethod
    async def get_provider_async(
        cls, provider_type: str, container: ProviderContainer | None = None
    ) -> Any:
        """
        获取 Provider 实例（兼容旧接口）

        Args:
            provider_type: Provider 类型（如 "amazingdata", "akshare", "miniqmt"）
            container: 可选的 ProviderContainer 实例

        Returns:
            Provider 实例

        Raises:
            RuntimeError: 如果无法获取 Provider

        Examples:
            >>> # 使用新容器
            >>> container = ProviderContainer()
            >>> provider = await ProviderFactoryCompat.get_provider_async("akshare", container)
            >>>
            >>> # Fallback 到旧 Factory
            >>> provider = await ProviderFactoryCompat.get_provider_async("akshare")
        """
        # 规范化 Provider 类型
        normalized_type = cls._normalize_provider_type(provider_type)

        # 如果没有提供容器，尝试 fallback 到旧的 DataProviderFactory
        if container is None:
            logger.warning(
                f"ProviderFactoryCompat: 未提供容器，fallback 到旧的 DataProviderFactory（Provider: {normalized_type}）"
            )
            try:
                from apps.api.api.providers import DataProviderFactory as OldFactory

                return await OldFactory.get_provider_async(normalized_type)
            except Exception as e:
                logger.error(f"旧 DataProviderFactory 也失败: {e}")
                raise RuntimeError(f"无法获取 Provider '{normalized_type}': {e}") from e

        # 使用新容器
        logger.debug(f"ProviderFactoryCompat: 使用新容器获取 Provider: {normalized_type}")

        try:
            # 尝试从容器中获取已注册的 Provider
            return await container.get(normalized_type)
        except Exception as get_error:
            # 如果容器中没有，尝试创建并注册
            logger.debug(f"ProviderFactoryCompat: Provider '{normalized_type}' 未注册，尝试创建...")

            try:
                from core.config import get_config

                config = get_config()

                # 从配置中获取 Provider 配置
                data_sources = getattr(config, "data_sources", None)
                if data_sources is not None:
                    ds_config = data_sources.get_provider(normalized_type)

                    if ds_config:
                        # 如果是字典配置，直接使用
                        if isinstance(ds_config, dict):
                            provider_config = ds_config
                        # 如果是 Pydantic 模型，转换为字典
                        elif hasattr(ds_config, "model_dump"):
                            provider_config = ds_config.model_dump()
                        elif hasattr(ds_config, "dict"):
                            provider_config = ds_config.dict()
                        else:
                            provider_config = dict(ds_config)

                        # 创建并注册
                        logger.info(
                            f"ProviderFactoryCompat: 从配置创建 Provider: {normalized_type}"
                        )
                        return await container.create_and_register(normalized_type, provider_config)

                # 如果配置中也没有，抛出原始错误
                logger.error(f"ProviderFactoryCompat: 配置中未找到 Provider '{normalized_type}'")
                raise get_error

            except Exception as create_error:
                logger.error(f"ProviderFactoryCompat: 创建 Provider 失败: {create_error}")
                # 最后尝试 fallback 到旧 Factory
                try:
                    from apps.api.api.providers import DataProviderFactory as OldFactory

                    logger.warning(f"Fallback 到旧 DataProviderFactory: {normalized_type}")
                    return await OldFactory.get_provider_async(normalized_type)
                except Exception as fallback_error:
                    logger.error(f"Fallback 也失败: {fallback_error}")
                    raise RuntimeError(
                        f"无法获取 Provider '{normalized_type}': {create_error}"
                    ) from create_error

    @staticmethod
    def _normalize_provider_type(provider_type: str | Any) -> str:
        """
        规范化 Provider 类型名称

        Args:
            provider_type: Provider 类型（字符串或枚举）

        Returns:
            规范化的 Provider 类型名称（小写，去除空格）
        """
        if hasattr(provider_type, "value"):
            # 处理枚举类型
            return str(provider_type.value).strip().lower()
        return str(provider_type).strip().lower()


# 便捷函数
async def get_provider_compat(
    provider_type: str, container: ProviderContainer | None = None
) -> Any:
    """
    便捷函数：获取 Provider（兼容模式）

    Args:
        provider_type: Provider 类型
        container: 可选的容器实例

    Returns:
        Provider 实例
    """
    return await ProviderFactoryCompat.get_provider_async(provider_type, container)
