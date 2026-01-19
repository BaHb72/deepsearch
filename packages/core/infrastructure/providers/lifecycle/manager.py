"""
Provider 生命周期管理器
"""

import asyncio
from typing import Any, Sequence

from loguru import logger

from ..protocols.lifecycle import HealthStatus, ILifecycleProvider


class ProviderLifecycleManager:
    """Provider 生命周期管理器

    统一管理所有 Provider 的启动、停止和健康检查。
    """

    def __init__(self, *, shutdown_timeout: float = 10.0):
        """初始化生命周期管理器

        Args:
            shutdown_timeout: 停止超时时间（秒）
        """
        self.shutdown_timeout = shutdown_timeout

    async def initialize(self, provider: Any) -> None:
        """初始化 Provider

        Args:
            provider: Provider 实例

        Raises:
            ProviderInitializationError: 初始化失败
        """
        if not isinstance(provider, ILifecycleProvider):
            logger.warning(
                f"Provider {provider.__class__.__name__} "
                "未实现 ILifecycleProvider 协议，跳过初始化"
            )
            return

        try:
            logger.info(f"初始化 Provider: {provider.__class__.__name__}")
            await provider.initialize()
            logger.info(f"Provider 初始化成功: {provider.__class__.__name__}")
        except Exception as e:
            logger.error(f"Provider 初始化失败: {provider.__class__.__name__}", exc_info=e)
            raise

    async def start(self, provider: Any) -> None:
        """启动 Provider

        Args:
            provider: Provider 实例

        Raises:
            ProviderStateError: 启动失败
        """
        if not isinstance(provider, ILifecycleProvider):
            return

        try:
            logger.info(f"启动 Provider: {provider.__class__.__name__}")
            await provider.start()
            logger.info(f"Provider 启动成功: {provider.__class__.__name__}")
        except Exception as e:
            logger.error(f"Provider 启动失败: {provider.__class__.__name__}", exc_info=e)
            raise

    async def stop(self, provider: Any) -> None:
        """停止 Provider（带超时保护）

        Args:
            provider: Provider 实例
        """
        if not isinstance(provider, ILifecycleProvider):
            return

        try:
            logger.info(f"停止 Provider: {provider.__class__.__name__}")
            await asyncio.wait_for(provider.stop(), timeout=self.shutdown_timeout)
            logger.info(f"Provider 停止成功: {provider.__class__.__name__}")
        except asyncio.TimeoutError:
            logger.warning(
                f"Provider 停止超时（{self.shutdown_timeout}s）: " f"{provider.__class__.__name__}"
            )
        except Exception as e:
            logger.error(f"Provider 停止失败: {provider.__class__.__name__}", exc_info=e)

    async def shutdown_all(self, providers: Sequence[Any]) -> None:
        """批量停止所有 Provider

        Args:
            providers: Provider 列表
        """
        if not providers:
            logger.info("没有 Provider 需要停止")
            return

        logger.info(f"开始停止 {len(providers)} 个 Provider...")

        # 并发停止，收集异常
        tasks = [self.stop(p) for p in providers]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 统计结果
        errors = [r for r in results if isinstance(r, Exception)]
        if errors:
            logger.warning(f"停止 Provider 时发生 {len(errors)} 个错误")
            for error in errors:
                logger.error(f"  - {error}")

        logger.info("所有 Provider 已停止")

    async def health_check(self, provider: Any) -> HealthStatus:
        """检查 Provider 健康状态

        Args:
            provider: Provider 实例

        Returns:
            HealthStatus: 健康状态枚举
        """
        if not isinstance(provider, ILifecycleProvider):
            return HealthStatus.UNKNOWN

        try:
            result = await asyncio.wait_for(provider.health_check(), timeout=5.0)
            return result.status
        except asyncio.TimeoutError:
            logger.warning(f"Provider 健康检查超时: {provider.__class__.__name__}")
            return HealthStatus.UNHEALTHY
        except Exception as e:
            logger.error(f"Provider 健康检查失败: {provider.__class__.__name__}", exc_info=e)
            return HealthStatus.UNHEALTHY

    async def health_check_all(self, providers: dict[str, Any]) -> dict[str, HealthStatus]:
        """批量健康检查

        Args:
            providers: Provider 字典 {name: instance}

        Returns:
            dict[str, HealthStatus]: 健康状态字典
        """
        tasks = {name: self.health_check(provider) for name, provider in providers.items()}
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)

        return {
            name: result if isinstance(result, HealthStatus) else HealthStatus.UNKNOWN
            for name, result in zip(tasks.keys(), results)
        }
