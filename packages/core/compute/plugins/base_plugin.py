"""Dask Worker Plugin 基类

使用模板方法模式统一 Plugin 生命周期管理，消除代码重复。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from core.compute.plugins.config import BasePluginConfig
from distributed import WorkerPlugin
from loguru import logger

if TYPE_CHECKING:
    from distributed import Worker


class BaseWorkerPlugin(WorkerPlugin, ABC):
    """Dask Worker Plugin 基类

    提供标准的 setup/teardown 流程，子类只需实现钩子方法。

    模板方法模式:
    - setup(): 标准流程（资源验证 → 加载依赖 → 创建 Actor → 初始化 → 注册）
    - teardown(): 标准流程（移除注册 → 清理 Actor）
    - 子类实现: _load_dependencies, _create_actor, _get_actor_name

    Attributes:
        name: Plugin 名称
        idempotent: 防止重复注册
        config: Pydantic 配置对象
    """

    idempotent = True

    def __init__(self, config: BasePluginConfig) -> None:
        """初始化 Plugin

        Args:
            config: Pydantic 配置对象
        """
        self.config = config
        self._actor: Any = None
        self._initialized = False
        self._worker_address = ""

    async def setup(self, worker: Worker) -> None:
        """Plugin 启动流程（模板方法）

        标准流程:
        1. 资源验证（Windows 资源标签检查）
        2. 加载依赖（子类实现）
        3. 创建 Actor 实例（子类实现）
        4. 初始化 Actor
        5. 注册到 Worker

        Args:
            worker: Dask Worker 实例
        """
        self._worker_address = worker.address

        # 步骤 1: 资源验证
        if not self._check_resources(worker):
            return

        logger.info(f"[PLUGIN_SETUP] === {self.name} Setup 开始 === | worker={worker.address}")

        try:
            import time

            setup_start = time.time()

            # 步骤 2: 加载依赖（子类实现）
            step_start = time.time()
            logger.info("[PLUGIN_SETUP] [步骤1/4] 加载依赖...")
            await self._load_dependencies()
            logger.info(
                f"[PLUGIN_SETUP] [步骤1/4] 依赖加载完成 | 耗时={time.time() - step_start:.3f}s"
            )

            # 步骤 3: 创建 Actor 实例（子类实现）
            step_start = time.time()
            logger.info("[PLUGIN_SETUP] [步骤2/4] 创建 Actor 实例...")
            self._actor = await self._create_actor()
            if self._actor is None:
                logger.warning("[PLUGIN_SETUP] Actor 创建失败，终止 setup")
                return
            logger.info(
                f"[PLUGIN_SETUP] [步骤2/4] Actor 创建完成 | 耗时={time.time() - step_start:.3f}s"
            )

            # 步骤 4: 初始化 Actor
            step_start = time.time()
            logger.info("[PLUGIN_SETUP] [步骤3/4] 调用 Actor.initialize()...")
            try:
                result = await self._actor.initialize()
                logger.info(
                    f"[PLUGIN_SETUP] [步骤3/4] Actor.initialize() 完成 | 结果={result} | 耗时={time.time() - step_start:.3f}s"
                )
                if not result:
                    logger.error("[PLUGIN_SETUP] Actor.initialize() 返回 False")
                    self._actor = None
                    return
            except Exception as init_error:
                logger.error(
                    f"[PLUGIN_SETUP] [步骤3/4] Actor.initialize() 失败 | 耗时={time.time() - step_start:.3f}s | 错误={init_error}",
                    exc_info=True,
                )
                self._actor = None
                return

            # 步骤 5: 注册到 Worker
            step_start = time.time()
            logger.info("[PLUGIN_SETUP] [步骤4/4] 注册 Actor 到 Worker...")
            self._register_actor(worker)
            self._initialized = True
            logger.info(f"[PLUGIN_SETUP] [步骤4/4] 注册完成 | 耗时={time.time() - step_start:.3f}s")

            total_elapsed = time.time() - setup_start
            logger.info(
                f"[PLUGIN_SETUP] === Setup 成功完成 === | "
                f"worker={worker.address} | 总耗时={total_elapsed:.3f}s"
            )

        except Exception as e:
            total_elapsed = time.time() - setup_start if "setup_start" in locals() else 0
            logger.error(
                f"[PLUGIN_SETUP] === Setup 失败 === | "
                f"worker={worker.address} | 错误={e} | 总耗时={total_elapsed:.3f}s",
                exc_info=True,
            )

    async def teardown(self, worker: Worker) -> None:
        """Plugin 清理流程（模板方法）

        标准流程:
        1. 从 Worker 移除注册
        2. 清理 Actor 资源

        Args:
            worker: Dask Worker 实例
        """
        if not self._initialized or self._actor is None:
            return

        logger.info(f"{self.name} plugin teardown on worker {worker.address}")

        try:
            # 步骤 1: 从 Worker 移除
            if hasattr(worker, "actors"):
                worker.actors.pop(self._get_actor_name(), None)  # type: ignore

            # 步骤 2: 清理 Actor
            if hasattr(self._actor, "shutdown"):
                await self._actor.shutdown()
            elif hasattr(self._actor, "stop_async"):
                await self._actor.stop_async()
            elif hasattr(self._actor, "close"):
                await self._actor.close()

            logger.info(f"{self.name} Actor stopped | worker={worker.address}")

        except Exception as e:
            logger.error(
                f"Error during {self.name} teardown | " f"worker={worker.address}, error={e}",
                exc_info=True,
            )
        finally:
            self._actor = None
            self._initialized = False

    def _check_resources(self, worker: Worker) -> bool:
        """资源验证（统一实现）

        检查 Worker 是否有 WIN 资源标签（如果需要）。

        Args:
            worker: Dask Worker 实例

        Returns:
            True: 通过验证
            False: 未通过验证
        """
        if not self.config.only_on_windows:
            return True

        # 优先使用新 API (Dask 2025.12+)
        resources = getattr(worker.state, "total_resources", {})
        if not resources:
            # 向后兼容：尝试旧 API
            resources = getattr(worker, "resources", {}) or {}

        if not resources.get("WIN"):
            logger.warning(
                f"[资源验证失败] {self.name} plugin 跳过: Windows 资源标签缺失 | "
                f"worker={worker.address}, "
                f"实际 resources={resources}, "
                f"期望 resources={{'WIN': 1.0}} | "
                f"请检查 Worker 启动命令是否包含 --resources WIN=1.0"
            )
            return False

        logger.info(
            f"[资源验证通过] {self.name} plugin 激活 | "
            f"worker={worker.address}, "
            f"resources={resources}"
        )
        return True

    def _register_actor(self, worker: Worker) -> None:
        """注册 Actor（统一实现）

        将 Actor 注册到 worker.actors 命名空间。

        Args:
            worker: Dask Worker 实例
        """
        if not hasattr(worker, "actors"):
            worker.actors = {}  # type: ignore
        worker.actors[self._get_actor_name()] = self._actor  # type: ignore
        logger.info(f"[{self.name}] Actor 注册成功 | name={self._get_actor_name()}")

    @abstractmethod
    async def _load_dependencies(self) -> None:
        """加载依赖（子类实现）

        例如: 导入 SDK、连接到远程服务等。

        Raises:
            Exception: 依赖加载失败时抛出异常
        """
        pass

    @abstractmethod
    async def _create_actor(self) -> Any:
        """创建 Actor 实例（子类实现）

        返回:
            Actor 实例，失败时返回 None
        """
        pass

    @abstractmethod
    def _get_actor_name(self) -> str:
        """获取 Actor 名称（子类实现）

        返回:
            Actor 在 worker.actors 中的注册名称
        """
        pass

    @property
    def is_initialized(self) -> bool:
        """检查 Plugin 是否已初始化"""
        return self._initialized

    @property
    def actor(self) -> Any:
        """获取 Actor 实例"""
        return self._actor

    def transition(
        self,
        key: str,
        start: str,
        finish: str,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """任务状态转换钩子（可选重写）

        默认为空操作。
        """
        pass
