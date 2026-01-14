"""Dask Worker Plugin for AmazingData Actor management.

This plugin initializes and manages AmazingDataActor lifecycle on Dask Workers.
使用 Dask 原生 setup/teardown 作为唯一的生命周期管理入口。

架构设计:
- Plugin.setup(): 创建并初始化 Actor，注册到 worker.actors
- Plugin.teardown(): 清理 Actor 资源
- Actor 保持 SDK 登录状态

Usage:
    from distributed import Client
    from core.infrastructure.providers.implementations.amazingdata.dask_plugin import (
        AmazingDataWorkerPlugin,
    )
    from core.compute.plugins.config import AmazingDataPluginConfig

    client = Client("tcp://scheduler:8786")
    config = AmazingDataPluginConfig(redis_url="redis://localhost:6379")
    plugin = AmazingDataWorkerPlugin(config)
    client.register_plugin(plugin)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from core.compute.plugins.base_plugin import BaseWorkerPlugin
from core.compute.plugins.config import AmazingDataPluginConfig
from loguru import logger

if TYPE_CHECKING:
    pass


class AmazingDataWorkerPlugin(BaseWorkerPlugin):
    """Dask Worker Plugin for AmazingData Actor.

    继承 BaseWorkerPlugin，只需实现三个钩子方法:
    - _load_dependencies: 加载依赖（AmazingData 无需加载 SDK）
    - _create_actor: 创建 AmazingDataActor 实例
    - _get_actor_name: 返回 Actor 注册名称

    Attributes:
        name: Plugin 名称
        config: AmazingDataPluginConfig 配置对象
    """

    name = "amazingdata-actor"

    def __init__(self, config: AmazingDataPluginConfig) -> None:
        """初始化 Plugin

        Args:
            config: AmazingDataPluginConfig 配置对象
        """
        super().__init__(config)

    async def _load_dependencies(self) -> None:
        """加载依赖

        AmazingData 使用 HTTP API，无需加载 SDK。
        """
        pass

    async def _create_actor(self) -> Any:
        """创建 AmazingDataActor 实例

        关键修复: 只提取 connection 内层字段，避免外层占位符污染。

        Returns:
            AmazingDataActor 实例，失败时返回 None
        """
        from core.compute.actors.amazingdata_actor import AmazingDataActor
        from core.config import get_config

        app_config = get_config()
        data_sources = getattr(app_config, "data_sources", None)

        # 构建 Actor 配置
        actor_config: dict[str, Any] = {
            "redis_url": self.config.redis_url,
            "distributed_session_enabled": True,
        }

        # 提取 AmazingData 配置
        if data_sources:
            providers = getattr(data_sources, "providers", {})
            if hasattr(providers, "model_dump"):
                providers = providers.model_dump()

            amazingdata_config = providers.get("amazingdata", {})
            if hasattr(amazingdata_config, "model_dump"):
                amazingdata_config = amazingdata_config.model_dump()

            config_data = amazingdata_config.get("config", {})

            # 关键修复: 只取 connection 内层，不取外层占位符
            if "connection" in config_data:
                connection = config_data["connection"]
                for key in ("host", "port", "username", "password", "timeout"):
                    if key in connection:
                        actor_config[key] = connection[key]

                # 其他 connection 配置
                for key in (
                    "auto_reconnect",
                    "heartbeat_interval",
                    "max_retries",
                    "reconnect_interval",
                ):
                    if key in connection:
                        actor_config[key] = connection[key]

            # 其他非敏感配置可以直接合并
            for key in ("cache", "subscription", "implementation_mode"):
                if key in config_data:
                    actor_config[key] = config_data[key]

        # 脱敏日志
        safe_config = {k: v for k, v in actor_config.items() if k != "password"}
        logger.info(f"[AmazingData] Actor 配置: {safe_config}")

        return AmazingDataActor(actor_config)

    def _get_actor_name(self) -> str:
        """获取 Actor 名称

        Returns:
            Actor 在 worker.actors 中的注册名称
        """
        return "amazingdata"


def register_amazingdata_plugin(
    client: Any,
    redis_url: str = "redis://localhost:6379",
    only_on_windows: bool = True,
) -> AmazingDataWorkerPlugin:
    """便捷函数：注册 AmazingData Plugin

    Args:
        client: Dask distributed Client
        redis_url: Redis URL for session coordination
        only_on_windows: Only activate on Windows workers

    Returns:
        已注册的 Plugin 实例
    """
    config = AmazingDataPluginConfig(
        redis_url=redis_url,
        only_on_windows=only_on_windows,
    )
    plugin = AmazingDataWorkerPlugin(config)
    client.register_plugin(plugin)
    logger.info(f"AmazingData worker plugin registered | redis_url={redis_url}")
    return plugin
