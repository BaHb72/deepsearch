"""Dask Worker Plugin for MiniQMT Actor management.

This plugin initializes and manages MiniQMT SDK lifecycle on Dask Workers.
使用 Dask 原生 setup/teardown 作为唯一的生命周期管理入口。

架构设计:
- Plugin.setup(): 初始化 MiniQMT SDK 连接，创建 Actor（如果存在）
- Plugin.teardown(): 清理 MiniQMT SDK 连接和 Actor 资源
- Actor 保持 MiniQMT 客户端登录状态

Usage:
    from distributed import Client
    from core.infrastructure.providers.implementations.qmt.dask_plugin import (
        MiniQMTWorkerPlugin,
    )
    from core.compute.plugins.config import MiniQMTPluginConfig

    client = Client("tcp://scheduler:8786")
    config = MiniQMTPluginConfig(
        redis_url="redis://localhost:6379",
        cache_ttl=300,
        failure_threshold=5,
        recovery_timeout=60,
    )
    plugin = MiniQMTWorkerPlugin(config)
    client.register_plugin(plugin)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from core.compute.plugins.base_plugin import BaseWorkerPlugin
from core.compute.plugins.config import MiniQMTPluginConfig
from loguru import logger

if TYPE_CHECKING:
    from distributed import Worker


class MiniQMTWorkerPlugin(BaseWorkerPlugin):
    """Dask Worker Plugin for MiniQMT SDK.

    继承 BaseWorkerPlugin，只需实现三个钩子方法:
    - _load_dependencies: 导入并连接 xtquant SDK
    - _create_actor: 创建 MiniQMTActor 实例（可选）
    - _get_actor_name: 返回 Actor 注册名称

    Attributes:
        name: Plugin 名称
        config: MiniQMTPluginConfig 配置对象
        _xtdata: xtquant.xtdata SDK 模块
    """

    name = "miniqmt-actor"

    def __init__(self, config: MiniQMTPluginConfig) -> None:
        """初始化 Plugin

        Args:
            config: MiniQMTPluginConfig 配置对象
        """
        super().__init__(config)
        self._xtdata: Any = None

    async def _load_dependencies(self) -> None:
        """加载依赖：导入 xtquant SDK 并连接

        Raises:
            ImportError: xtquant 未安装
            Exception: SDK 连接失败
        """
        try:
            from xtquant import xtdata

            self._xtdata = xtdata
            # MiniQMT connect() 是同步方法
            self._xtdata.connect()
            logger.info("[MiniQMT] SDK 连接成功")
        except ImportError as e:
            logger.error(f"[MiniQMT] SDK 未安装: {e}")
            raise

    async def _create_actor(self) -> Any:
        """创建 MiniQMTActor 实例

        如果 MiniQMTActor 不存在，返回 xtdata SDK 作为回退。

        Returns:
            MiniQMTActor 实例或 xtdata SDK
        """
        # 尝试导入 MiniQMTActor（可选）
        try:
            from core.compute.actors.miniqmt_actor import MiniQMTActor
        except ImportError:
            logger.info("[MiniQMT] MiniQMTActor 不存在，使用 SDK 直连模式")
            return self._xtdata

        # 读取配置
        from core.config import get_config

        app_config = get_config()
        data_sources = getattr(app_config, "data_sources", None)

        # 构建 Actor 配置
        actor_config: dict[str, Any] = {
            "cache_ttl": self.config.cache_ttl,
            "failure_threshold": self.config.failure_threshold,
            "recovery_timeout": self.config.recovery_timeout,
        }

        # 提取 MiniQMT 配置
        if data_sources:
            providers = getattr(data_sources, "providers", {})
            if hasattr(providers, "model_dump"):
                providers = providers.model_dump()

            miniqmt_config = providers.get("miniqmt", {})
            if hasattr(miniqmt_config, "model_dump"):
                miniqmt_config = miniqmt_config.model_dump()

            config_data = miniqmt_config.get("config", {})
            if config_data:
                actor_config.update(config_data)

        logger.info(f"[MiniQMT] Actor 配置: {actor_config}")

        try:
            return MiniQMTActor(actor_config)
        except Exception as e:
            logger.error(f"[MiniQMT] Actor 创建失败: {e}, 使用 SDK 直连模式")
            return self._xtdata

    def _get_actor_name(self) -> str:
        """获取 Actor 名称

        Returns:
            Actor 在 worker.actors 中的注册名称
        """
        return "miniqmt"

    async def teardown(self, worker: Worker) -> None:
        """Plugin 清理流程（重写以支持 SDK 断开）

        Args:
            worker: Dask Worker 实例
        """
        # 调用父类清理 Actor
        await super().teardown(worker)

        # 额外清理：断开 MiniQMT SDK 连接
        if self._xtdata is not None:
            try:
                self._xtdata.disconnect()
                logger.info(f"MiniQMT SDK disconnected | worker={worker.address}")
            except Exception as disc_error:
                logger.warning(
                    f"MiniQMT SDK disconnect warning | "
                    f"worker={worker.address}, error={disc_error}"
                )
            finally:
                self._xtdata = None


def register_miniqmt_plugin(
    client: Any,
    config: dict[str, Any] | None = None,
    only_on_windows: bool = True,
) -> MiniQMTWorkerPlugin:
    """便捷函数：注册 MiniQMT Plugin

    Args:
        client: Dask distributed Client
        config: 配置字典（旧接口兼容）
        only_on_windows: Only activate on Windows workers

    Returns:
        已注册的 Plugin 实例
    """
    # 从 config dict 构建 Pydantic 配置
    plugin_config = MiniQMTPluginConfig(
        redis_url=(
            config.get("redis_url", "redis://localhost:6379")
            if config
            else "redis://localhost:6379"
        ),
        only_on_windows=only_on_windows,
        cache_ttl=config.get("cache_ttl", 300) if config else 300,
        failure_threshold=config.get("failure_threshold", 5) if config else 5,
        recovery_timeout=config.get("recovery_timeout", 60) if config else 60,
    )
    plugin = MiniQMTWorkerPlugin(plugin_config)
    client.register_plugin(plugin)
    logger.info(f"MiniQMT worker plugin registered | config={config}")
    return plugin
