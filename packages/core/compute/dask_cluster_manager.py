"""
Dask 集群统一管理器

组合 Scheduler 和 Worker 管理器，提供统一的集群生命周期管理。
保证正确的启动顺序（Scheduler -> Workers）和关闭顺序（Workers -> Scheduler）。

架构设计:
- DaskClusterManager: 统一入口，组合 SchedulerManager 和 WorkerManager
- 启动顺序: 先确保 Scheduler 可用，再启动 Workers
- 关闭顺序: 先停止 Workers，再停止本地 Scheduler
- 向后兼容: 提供 ensure_windows_workers() 等旧接口
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, ClassVar, Dict, List, Optional

from loguru import logger

if TYPE_CHECKING:
    from core.compute.dask_scheduler_manager import DaskSchedulerManager
    from core.compute.dask_worker_manager import DaskWorkerManager


# ============================================================================
# 状态定义
# ============================================================================


class ClusterState(Enum):
    """Dask 集群状态"""

    IDLE = "idle"  # 初始状态
    STARTING_SCHEDULER = "starting_scheduler"  # 启动 Scheduler
    STARTING_WORKERS = "starting_workers"  # 启动 Workers
    RUNNING = "running"  # 集群运行中
    STOPPING_WORKERS = "stopping_workers"  # 停止 Workers
    STOPPING_SCHEDULER = "stopping_scheduler"  # 停止 Scheduler
    STOPPED = "stopped"  # 已停止
    FAILED = "failed"  # 失败状态


# ============================================================================
# 数据类
# ============================================================================


@dataclass
class ClusterStatus:
    """集群状态信息"""

    state: str
    scheduler_ready: bool
    scheduler_source: str
    scheduler_address: Optional[str]
    workers_running: bool
    worker_count: int
    error: Optional[str]
    started_at: Optional[str]
    uptime: Optional[float]


# ============================================================================
# 主管理器类
# ============================================================================


class DaskClusterManager:
    """
    Dask 集群统一管理器

    组合 SchedulerManager 和 WorkerManager，提供：
    - 正确的启动/关闭顺序
    - 统一的状态管理
    - 向后兼容的 API

    状态转换:
    IDLE -> STARTING_SCHEDULER -> STARTING_WORKERS -> RUNNING
    RUNNING -> STOPPING_WORKERS -> STOPPING_SCHEDULER -> STOPPED
    """

    # 状态转换表
    # 允许从启动中状态转换到停止状态，以支持 Ctrl+C 中断启动流程
    VALID_TRANSITIONS: ClassVar[Dict[ClusterState, List[ClusterState]]] = {
        ClusterState.IDLE: [ClusterState.STARTING_SCHEDULER, ClusterState.FAILED],
        ClusterState.STARTING_SCHEDULER: [
            ClusterState.STARTING_WORKERS,
            ClusterState.STOPPING_WORKERS,  # 允许中断启动
            ClusterState.FAILED,
        ],
        ClusterState.STARTING_WORKERS: [
            ClusterState.RUNNING,
            ClusterState.STOPPING_WORKERS,  # 允许中断启动
            ClusterState.FAILED,
        ],
        ClusterState.RUNNING: [ClusterState.STOPPING_WORKERS, ClusterState.FAILED],
        ClusterState.STOPPING_WORKERS: [
            ClusterState.STOPPING_SCHEDULER,
            ClusterState.FAILED,
        ],
        ClusterState.STOPPING_SCHEDULER: [ClusterState.STOPPED, ClusterState.FAILED],
        ClusterState.STOPPED: [ClusterState.IDLE],
        ClusterState.FAILED: [ClusterState.IDLE],
    }

    def __init__(self) -> None:
        """初始化集群管理器"""
        self._logger = logger.bind(component="DaskClusterManager")

        # 状态机
        self._state = ClusterState.IDLE
        self._state_lock = asyncio.Lock()
        self._error: Optional[str] = None

        # 子管理器（延迟初始化）
        self._scheduler_manager: Optional["DaskSchedulerManager"] = None
        self._worker_manager: Optional["DaskWorkerManager"] = None

        # 元数据
        self._started_at: Optional[datetime] = None
        self._stopped_at: Optional[datetime] = None

    # ========================================================================
    # 属性
    # ========================================================================

    @property
    def state(self) -> ClusterState:
        """当前状态（只读）"""
        return self._state

    @property
    def is_running(self) -> bool:
        """检查集群是否运行中"""
        return self._state == ClusterState.RUNNING

    @property
    def scheduler_address(self) -> Optional[str]:
        """Scheduler 地址"""
        if self._scheduler_manager and self._scheduler_manager.is_ready:
            return self._scheduler_manager.address
        return None

    # ========================================================================
    # 状态转换
    # ========================================================================

    async def _transition_to(
        self,
        target: ClusterState,
        error: Optional[str] = None,
    ) -> bool:
        """原子状态转换"""
        async with self._state_lock:
            if target not in self.VALID_TRANSITIONS.get(self._state, []):
                self._logger.warning(f"无效的状态转换: {self._state.value} -> {target.value}")
                return False

            old_state = self._state
            self._state = target
            self._error = error

            self._logger.info(f"集群状态转换: {old_state.value} -> {target.value}")
            return True

    def _can_start(self) -> bool:
        """检查是否可以启动"""
        return self._state in (
            ClusterState.IDLE,
            ClusterState.STOPPED,
            ClusterState.FAILED,
        )

    # ========================================================================
    # 生命周期方法
    # ========================================================================

    async def start(self) -> bool:
        """
        启动 Dask 集群

        流程:
        1. 确保 Scheduler 可用（外部或本地）
        2. 启动 Workers

        Returns:
            True 如果集群启动成功
        """
        if not self._can_start():
            self._logger.warning(f"无法从状态 {self._state.value} 启动集群")
            return False

        try:
            # 重置状态
            if self._state in (ClusterState.STOPPED, ClusterState.FAILED):
                await self._transition_to(ClusterState.IDLE)

            # 阶段 1: 启动 Scheduler
            if not await self._transition_to(ClusterState.STARTING_SCHEDULER):
                return False

            if not await self._ensure_scheduler():
                await self._transition_to(ClusterState.FAILED, "Scheduler 启动失败")
                return False

            # 阶段 2: 启动 Workers
            if not await self._transition_to(ClusterState.STARTING_WORKERS):
                return False

            if not await self._start_workers():
                # Workers 启动失败不一定是致命错误，记录警告但继续
                self._logger.warning("Workers 启动失败，但 Scheduler 可用")
                # 仍然转换到 RUNNING 状态，因为 Scheduler 是可用的
                # 某些场景下可能只需要 Scheduler（如使用 Docker Workers）

            # 阶段 3: 运行中
            await self._transition_to(ClusterState.RUNNING)
            self._started_at = datetime.now()

            self._logger.info(
                f"Dask 集群已启动 | "
                f"scheduler={self.scheduler_address} | "
                f"workers={self._get_worker_count()}"
            )
            return True

        except Exception as e:
            self._logger.error(f"集群启动失败: {e}")
            await self._transition_to(ClusterState.FAILED, str(e))
            return False

    async def stop(self, timeout: float = 10.0) -> None:
        """
        停止 Dask 集群

        流程:
        1. 停止 Workers
        2. 停止本地 Scheduler（如果是我们启动的）

        Args:
            timeout: 等待优雅关闭的最大时间
        """
        if self._state in (ClusterState.STOPPED, ClusterState.IDLE):
            return

        try:
            # 阶段 1: 停止 Workers
            await self._transition_to(ClusterState.STOPPING_WORKERS)
            await self._stop_workers(timeout)

            # 阶段 2: 停止 Scheduler
            await self._transition_to(ClusterState.STOPPING_SCHEDULER)
            await self._stop_scheduler(timeout)

            # 完成
            await self._transition_to(ClusterState.STOPPED)
            self._stopped_at = datetime.now()

            self._logger.info("Dask 集群已停止")

        except Exception as e:
            self._logger.error(f"集群停止失败: {e}")
            await self._transition_to(ClusterState.FAILED, str(e))

    async def reset(self) -> None:
        """重置集群状态"""
        if self._state in (ClusterState.FAILED, ClusterState.STOPPED):
            if self._scheduler_manager:
                await self._scheduler_manager.reset()
            if self._worker_manager:
                await self._worker_manager.reset()
            await self._transition_to(ClusterState.IDLE)

    # ========================================================================
    # 内部实现
    # ========================================================================

    async def _ensure_scheduler(self) -> bool:
        """确保 Scheduler 可用"""
        from core.compute.dask_scheduler_manager import DaskSchedulerManager

        if self._scheduler_manager is None:
            self._scheduler_manager = DaskSchedulerManager()

        return await self._scheduler_manager.start()

    async def _start_workers(self) -> bool:
        """启动 Workers

        注意：必须使用单例 get_dask_worker_manager() 而不是创建新实例，
        因为 dask_init_state 等其他模块会通过单例来等待 Plugin 就绪事件。
        如果创建新实例，Event 会在不同实例上触发和等待，导致永远等不到。
        """
        from core.compute.dask_worker_manager import get_dask_worker_manager

        if self._worker_manager is None:
            # 关键修复：使用单例而不是创建新实例
            self._worker_manager = await get_dask_worker_manager()

        return await self._worker_manager.start()

    async def _stop_workers(self, timeout: float) -> None:
        """停止 Workers"""
        if self._worker_manager:
            await self._worker_manager.stop(timeout)

    async def _stop_scheduler(self, timeout: float) -> None:
        """停止 Scheduler"""
        if self._scheduler_manager:
            await self._scheduler_manager.stop(timeout)

    def _get_worker_count(self) -> int:
        """获取 Worker 数量"""
        if self._worker_manager:
            return self._worker_manager.worker_count
        return 0

    # ========================================================================
    # 状态查询
    # ========================================================================

    def get_status(self) -> Dict[str, Any]:
        """获取完整状态信息"""
        scheduler_status = (
            self._scheduler_manager.get_status()
            if self._scheduler_manager
            else {"state": "idle", "source": "none"}
        )

        worker_status = (
            self._worker_manager.get_status()
            if self._worker_manager
            else {"state": "idle", "workers": {"count": 0}}
        )

        return {
            "state": self._state.value,
            "error": self._error,
            "scheduler": scheduler_status,
            "workers": worker_status,
            "started_at": self._started_at.isoformat() if self._started_at else None,
            "uptime": (
                (datetime.now() - self._started_at).total_seconds()
                if self._started_at and self.is_running
                else None
            ),
        }


# ============================================================================
# 单例和全局函数
# ============================================================================

_cluster_manager: Optional[DaskClusterManager] = None
_cluster_manager_lock = asyncio.Lock()


async def get_cluster_manager() -> DaskClusterManager:
    """获取或创建单例管理器实例"""
    global _cluster_manager
    async with _cluster_manager_lock:
        if _cluster_manager is None:
            _cluster_manager = DaskClusterManager()
        return _cluster_manager


async def ensure_dask_cluster() -> bool:
    """
    确保 Dask 集群已启动

    统一入口函数，自动处理 Scheduler 和 Workers。

    Returns:
        True 如果集群启动成功
    """
    manager = await get_cluster_manager()
    return await manager.start()


async def shutdown_dask_cluster() -> None:
    """
    关闭 Dask 集群

    按正确顺序关闭 Workers 和 Scheduler。
    """
    manager = await get_cluster_manager()
    await manager.stop()


def get_cluster_status() -> dict:
    """获取集群状态"""
    global _cluster_manager
    if _cluster_manager is None:
        return {"state": "idle", "scheduler": None, "workers": None}
    return _cluster_manager.get_status()


# ============================================================================
# 向后兼容函数
# ============================================================================


async def ensure_windows_workers() -> bool:
    """
    确保 Windows Dask Workers 已启动

    向后兼容函数，内部调用 ensure_dask_cluster()。
    保持旧接口兼容性。
    """
    return await ensure_dask_cluster()


async def stop_windows_workers() -> None:
    """
    停止 Windows Dask Workers

    向后兼容函数，内部调用 shutdown_dask_cluster()。
    保持旧接口兼容性。
    """
    await shutdown_dask_cluster()
