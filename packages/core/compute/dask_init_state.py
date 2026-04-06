"""
Dask 初始化状态管理模块

提供后台异步初始化 Dask 集群的能力，跟踪各组件就绪状态。
解决 FastAPI lifespan 阻塞导致 Uvicorn 无法及时监听端口的问题。

设计原则:
- 状态机保护: 使用枚举和锁确保状态转换原子性
- 事件驱动: 使用 asyncio.Event 让调用者优雅等待
- 组件粒度: 跟踪 Scheduler、Workers、AmazingData 各自状态
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, Optional

from loguru import logger

if TYPE_CHECKING:
    from fastapi import FastAPI


class DaskInitPhase(Enum):
    """Dask 初始化阶段"""

    PENDING = "pending"  # 尚未开始
    INITIALIZING = "initializing"  # 初始化中
    READY = "ready"  # 完全就绪
    PARTIAL = "partial"  # 部分就绪（Scheduler 可用但 Workers 或 Actor 异常）
    FAILED = "failed"  # 初始化失败


@dataclass
class ComponentStatus:
    """单个组件的状态"""

    ready: bool = False
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    ready_at: Optional[datetime] = None


@dataclass
class DaskInitStatus:
    """Dask 初始化状态快照"""

    phase: DaskInitPhase = DaskInitPhase.PENDING
    message: str = "等待初始化"
    progress_percent: int = 0

    # 各组件状态
    scheduler: ComponentStatus = field(default_factory=ComponentStatus)
    workers: ComponentStatus = field(default_factory=ComponentStatus)
    amazingdata: ComponentStatus = field(default_factory=ComponentStatus)

    # 时间信息
    started_at: Optional[datetime] = None
    ready_at: Optional[datetime] = None
    elapsed_seconds: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为 API 响应格式"""
        return {
            "phase": self.phase.value,
            "message": self.message,
            "progress_percent": self.progress_percent,
            "components": {
                "scheduler": {
                    "ready": self.scheduler.ready,
                    "error": self.scheduler.error,
                },
                "workers": {
                    "ready": self.workers.ready,
                    "error": self.workers.error,
                },
                "amazingdata": {
                    "ready": self.amazingdata.ready,
                    "error": self.amazingdata.error,
                },
            },
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ready_at": self.ready_at.isoformat() if self.ready_at else None,
            "elapsed_seconds": self.elapsed_seconds,
        }


class DaskInitStateManager:
    """
    Dask 初始化状态管理器

    职责:
    - 管理后台初始化 Task
    - 跟踪各组件就绪状态
    - 提供等待机制供 API 依赖使用
    """

    def __init__(self) -> None:
        self._logger = logger.bind(component="DaskInitStateManager")

        # 状态
        self._phase = DaskInitPhase.PENDING
        self._message = "等待初始化"
        self._lock = asyncio.Lock()

        # 组件状态
        self._scheduler_status = ComponentStatus()
        self._workers_status = ComponentStatus()
        self._amazingdata_status = ComponentStatus()

        # 时间追踪
        self._started_at: Optional[datetime] = None
        self._ready_at: Optional[datetime] = None

        # 事件信号（允许外部等待就绪）
        self._ready_event = asyncio.Event()
        self._scheduler_ready_event = asyncio.Event()
        self._amazingdata_ready_event = asyncio.Event()

        # 后台任务引用
        self._init_task: Optional[asyncio.Task[None]] = None

        # AmazingData DaskAdapter 实例引用（供 API 端点直接获取）
        self._amazingdata_adapter: Any = None

    # ========================================================================
    # 状态查询
    # ========================================================================

    @property
    def phase(self) -> DaskInitPhase:
        """当前初始化阶段"""
        return self._phase

    @property
    def is_ready(self) -> bool:
        """是否完全就绪"""
        return self._phase == DaskInitPhase.READY

    @property
    def is_partial(self) -> bool:
        """是否部分就绪"""
        return self._phase == DaskInitPhase.PARTIAL

    @property
    def is_usable(self) -> bool:
        """是否可用（就绪或部分就绪）"""
        return self._phase in (DaskInitPhase.READY, DaskInitPhase.PARTIAL)

    @property
    def scheduler_ready(self) -> bool:
        """Scheduler 是否就绪"""
        return self._scheduler_status.ready

    @property
    def amazingdata_ready(self) -> bool:
        """AmazingData Actor 是否就绪"""
        return self._amazingdata_status.ready

    @property
    def amazingdata_adapter(self) -> Any:
        """获取已注册的 AmazingData DaskAdapter 实例（可能为 None）"""
        return self._amazingdata_adapter

    def get_status(self) -> DaskInitStatus:
        """获取当前状态快照"""
        elapsed = None
        if self._started_at:
            end_time = self._ready_at or datetime.now()
            elapsed = (end_time - self._started_at).total_seconds()

        return DaskInitStatus(
            phase=self._phase,
            message=self._message,
            progress_percent=self._calculate_progress(),
            scheduler=ComponentStatus(
                ready=self._scheduler_status.ready,
                error=self._scheduler_status.error,
                started_at=self._scheduler_status.started_at,
                ready_at=self._scheduler_status.ready_at,
            ),
            workers=ComponentStatus(
                ready=self._workers_status.ready,
                error=self._workers_status.error,
                started_at=self._workers_status.started_at,
                ready_at=self._workers_status.ready_at,
            ),
            amazingdata=ComponentStatus(
                ready=self._amazingdata_status.ready,
                error=self._amazingdata_status.error,
                started_at=self._amazingdata_status.started_at,
                ready_at=self._amazingdata_status.ready_at,
            ),
            started_at=self._started_at,
            ready_at=self._ready_at,
            elapsed_seconds=elapsed,
        )

    def mark_amazingdata_runtime_unavailable(self, error: str) -> None:
        """标记 AmazingData 运行时不可用（初始化完成后的故障通道）。

        用于处理 SDK hard-exit / Worker 进程崩溃等运行时问题。
        调用后会将整体阶段降为 PARTIAL，并保留错误详情供 API/巡检查询。
        """
        self._amazingdata_status.ready = False
        self._amazingdata_status.error = error
        self._amazingdata_status.ready_at = None

        if self._scheduler_status.ready:
            self._phase = DaskInitPhase.PARTIAL
            self._message = "Dask 集群部分就绪（AmazingData 运行时异常）"
        else:
            self._phase = DaskInitPhase.FAILED
            self._message = "Dask 集群不可用（AmazingData 运行时异常）"

        self._logger.error("AmazingData 运行时降级: {}", error)

    def mark_amazingdata_runtime_recovered(self, worker: str | None = None) -> None:
        """标记 AmazingData 运行时恢复。

        当 Adapter 检测到 Redis 运行时标记重新出现后调用，
        用于将状态从 PARTIAL 回切到 READY。
        """
        self._amazingdata_status.ready = True
        self._amazingdata_status.error = None
        self._amazingdata_status.ready_at = datetime.now()

        if self._scheduler_status.ready and self._workers_status.ready:
            self._phase = DaskInitPhase.READY
            self._message = "Dask 集群完全就绪"
        elif self._scheduler_status.ready:
            self._phase = DaskInitPhase.PARTIAL
            self._message = "Dask 集群部分就绪（Workers 未就绪）"
        else:
            self._phase = DaskInitPhase.FAILED
            self._message = "Dask 集群初始化失败"

        self._logger.info(
            "AmazingData 运行时恢复: worker={}",
            worker or "unknown",
        )

    def _calculate_progress(self) -> int:
        """计算初始化进度百分比"""
        if self._phase == DaskInitPhase.PENDING:
            return 0
        if self._phase in (DaskInitPhase.READY, DaskInitPhase.PARTIAL):
            return 100
        if self._phase == DaskInitPhase.FAILED:
            return 0

        # 初始化中，根据组件状态计算
        progress = 10  # 已开始
        if self._scheduler_status.ready:
            progress += 30
        if self._workers_status.ready:
            progress += 30
        if self._amazingdata_status.ready:
            progress += 30
        return min(progress, 99)  # 最多 99%，留给最终完成

    # ========================================================================
    # 等待方法
    # ========================================================================

    async def wait_ready(self, timeout: Optional[float] = None) -> bool:
        """
        等待 Dask 完全就绪

        Args:
            timeout: 超时时间（秒），None 表示无限等待

        Returns:
            True 如果就绪，False 如果超时或失败
        """
        try:
            await asyncio.wait_for(self._ready_event.wait(), timeout=timeout)
            return self.is_ready or self.is_partial
        except asyncio.TimeoutError:
            return False

    async def wait_scheduler_ready(self, timeout: Optional[float] = None) -> bool:
        """等待 Scheduler 就绪"""
        try:
            await asyncio.wait_for(self._scheduler_ready_event.wait(), timeout=timeout)
            return self._scheduler_status.ready
        except asyncio.TimeoutError:
            return False

    async def wait_amazingdata_ready(self, timeout: Optional[float] = None) -> bool:
        """等待 AmazingData Actor 就绪"""
        try:
            await asyncio.wait_for(self._amazingdata_ready_event.wait(), timeout=timeout)
            return self._amazingdata_status.ready
        except asyncio.TimeoutError:
            return False

    # ========================================================================
    # 后台初始化
    # ========================================================================

    async def initialize_in_background(self, app: "FastAPI") -> None:
        """
        在后台执行 Dask 集群初始化

        此方法应作为 asyncio.Task 运行，不阻塞 lifespan。

        Args:
            app: FastAPI 应用实例，用于访问 app.state
        """
        async with self._lock:
            if self._phase != DaskInitPhase.PENDING:
                self._logger.warning(f"初始化已在进行中或已完成: {self._phase.value}")
                return

            self._phase = DaskInitPhase.INITIALIZING
            self._message = "开始初始化 Dask 集群"
            self._started_at = datetime.now()

        self._logger.info("后台 Dask 初始化开始...")

        try:
            # 阶段 1: 启动 Dask 集群（Scheduler + Workers）
            cluster_started = await self._start_dask_cluster()

            if not cluster_started:
                await self._set_failed("Dask 集群启动失败")
                return

            # 阶段 2: 注册 AmazingData 代理（如果集群启动成功）
            await self._register_amazingdata_adapter(app)

            # 确定最终状态
            await self._finalize_status()

        except Exception as e:
            self._logger.error(f"Dask 初始化异常: {e}")
            await self._set_failed(str(e))

    async def _start_dask_cluster(self) -> bool:
        """启动 Dask 集群"""
        self._scheduler_status.started_at = datetime.now()
        self._workers_status.started_at = datetime.now()
        self._message = "启动 Dask Scheduler..."

        try:
            from core.compute.dask_cluster_manager import ensure_dask_cluster

            cluster_started = await ensure_dask_cluster()

            if cluster_started:
                self._scheduler_status.ready = True
                self._scheduler_status.ready_at = datetime.now()
                self._workers_status.ready = True
                self._workers_status.ready_at = datetime.now()
                self._scheduler_ready_event.set()
                self._logger.info("Dask 集群启动成功（Scheduler + Workers）")
            else:
                self._scheduler_status.error = "集群启动返回 False"
                self._workers_status.error = "集群启动返回 False"
                self._logger.warning("Dask 集群启动失败")

            return cluster_started

        except Exception as e:
            self._scheduler_status.error = str(e)
            self._workers_status.error = str(e)
            self._logger.error(f"Dask 集群启动异常: {e}")
            return False

    async def _register_amazingdata_adapter(self, app: "FastAPI") -> None:
        """注册 AmazingData Dask 代理

        在注册之前，先等待 Plugin 在 Worker 上完成 setup。
        这是解决时序竞争问题的关键步骤。
        """
        self._amazingdata_status.started_at = datetime.now()
        self._message = "等待 AmazingData Plugin 就绪..."

        # 关键步骤：等待 Plugin 在 Worker 上完成 setup
        try:
            from core.compute.dask_worker_manager import get_dask_worker_manager
            from core.config import get_config

            worker_manager = await get_dask_worker_manager()
            wait_timeout = 60.0
            try:
                cfg = get_config()
                timeouts_cfg = getattr(cfg, "timeouts", None)
                dask_timeout_cfg = getattr(timeouts_cfg, "dask", None) if timeouts_cfg else None
                if dask_timeout_cfg is not None:
                    wait_timeout = float(getattr(dask_timeout_cfg, "amazingdata_init", 60.0))
            except Exception:
                pass
            self._logger.info("等待 AmazingData Plugin 就绪...")

            plugin_ready = await worker_manager.wait_amazingdata_plugin_ready(
                timeout=wait_timeout,
            )

            if not plugin_ready:
                self._amazingdata_status.error = "Plugin 就绪等待失败"
                self._logger.warning(
                    "AmazingData Plugin 未就绪（等待 {:.1f}s），继续尝试通过 Redis 就绪标记注册代理",
                    wait_timeout,
                )
            else:
                self._logger.info("AmazingData Plugin 已就绪，开始注册代理...")
            self._message = "注册 AmazingData 代理..."

        except Exception as e:
            self._logger.warning(f"等待 Plugin 就绪时出错: {e}")
            # 继续尝试注册，让后续的 Actor 检查来决定是否可用

        provider_container = getattr(app.state, "provider_container", None)
        if provider_container is None:
            self._amazingdata_status.error = "ProviderContainer 不可用"
            self._logger.warning("ProviderContainer 不可用，跳过 AmazingData 注册")
            return

        try:
            import redis.asyncio as aioredis
            from core.config import get_config
            from core.infrastructure.providers.implementations.amazingdata.dask_adapter import (
                AmazingDataDaskAdapter,
            )

            # 获取配置
            app_settings = get_config()

            # Scheduler 地址
            scheduler_address = "tcp://localhost:8786"
            dask_config = getattr(app_settings, "dask", None)
            if dask_config and hasattr(dask_config, "scheduler_address"):
                addr = dask_config.scheduler_address
                # 确保 tcp:// 前缀
                scheduler_address = addr if addr.startswith("tcp://") else f"tcp://{addr}"

            # Redis 地址
            redis_url = "redis://localhost:6379"
            cache_config = getattr(app_settings, "cache", None)
            if cache_config and hasattr(cache_config, "url"):
                redis_url = cache_config.url

            # 不在此处创建 Dask Client，由 adapter 按需创建
            # adapter 内部使用 asynchronous=True 模式创建 Client，参与同一 asyncio 事件循环
            self._logger.info(
                f"[AmazingData/Dask] scheduler={scheduler_address} (Client 将按需创建)"
            )

            # 创建 Redis 客户端
            redis_client = aioredis.from_url(
                redis_url,
                encoding="utf-8",
                decode_responses=True,
            )

            # 从统一超时配置读取（Settings.timeouts.amazingdata）
            timeouts_cfg = getattr(app_settings, "timeouts", None)
            if timeouts_cfg:
                amazingdata_timeout = timeouts_cfg.amazingdata.normal_call
                amazingdata_first_call_timeout = timeouts_cfg.amazingdata.first_call
            else:
                amazingdata_timeout = 45.0
                amazingdata_first_call_timeout = 90.0

            self._logger.info(
                f"[AmazingData/Dask] 超时配置 | normal={amazingdata_timeout}s | "
                f"first_call={amazingdata_first_call_timeout}s"
            )

            # 创建 Adapter（纯 Redis 模式，无需 Dask Client）
            # 任务通过 Redis RPUSH 提交，Worker 端 RedisTaskListener BLPOP 执行
            adapter = AmazingDataDaskAdapter(
                redis_client=redis_client,
                redis_url=redis_url,
                timeout=amazingdata_timeout,
                first_call_timeout=amazingdata_first_call_timeout,
            )

            actor_ready_wait = max(15.0, float(amazingdata_first_call_timeout))
            if timeouts_cfg and getattr(timeouts_cfg, "dask", None) is not None:
                actor_ready_wait = max(
                    actor_ready_wait,
                    float(getattr(timeouts_cfg.dask, "amazingdata_init", actor_ready_wait)),
                )

            # 从 Redis key 等待 Worker 地址（格式: "ready:tcp://localhost:58200"）
            worker_address = await self._wait_for_actor_ready_marker(
                redis_client,
                timeout_seconds=actor_ready_wait,
            )

            if not worker_address:
                self._amazingdata_status.error = "Actor 就绪标记缺失"
                self._logger.warning(
                    "AmazingData Actor 就绪标记缺失，跳过代理注册 | timeout={:.1f}s",
                    actor_ready_wait,
                )
                try:
                    close_async = getattr(redis_client, "aclose", None)
                    if callable(close_async):
                        await close_async()
                    else:
                        redis_client.close()
                except Exception as close_exc:
                    self._logger.debug("关闭 AmazingData Redis 客户端失败: {}", close_exc)
                self._amazingdata_ready_event.set()
                return
            adapter._windows_worker = worker_address
            adapter._actor_available = True
            adapter._initialized = True

            provider_container.register_external("amazingdata", adapter)
            self._amazingdata_adapter = adapter
            app.state.amazingdata_redis_client = redis_client
            self._amazingdata_status.ready = True
            self._amazingdata_status.error = None
            self._amazingdata_status.ready_at = datetime.now()
            self._amazingdata_ready_event.set()
            self._logger.info(
                f"AmazingData Dask 代理已注册到 ProviderContainer | worker={worker_address}"
            )

        except Exception as e:
            self._amazingdata_status.error = str(e)
            self._amazingdata_ready_event.set()
            self._logger.warning(f"注册 AmazingData 代理失败: {e}")

    @staticmethod
    def _extract_worker_address(ready_value: Any) -> str | None:
        if isinstance(ready_value, (bytes, bytearray, memoryview)):
            ready_text = bytes(ready_value).decode("utf-8", errors="ignore").strip()
        else:
            ready_text = str(ready_value or "").strip()
        marker_index = ready_text.find("tcp://")
        if marker_index < 0:
            return None
        return ready_text[marker_index:] or None

    async def _wait_for_actor_ready_marker(
        self,
        redis_client: Any,
        *,
        timeout_seconds: float,
    ) -> str | None:
        """轮询 Redis 就绪标记，避免 Actor 刚完成 setup 即被判定缺失。"""
        deadline = time.monotonic() + max(0.1, timeout_seconds)
        last_value: Any = None
        while time.monotonic() < deadline:
            try:
                last_value = await redis_client.get("dask_actor_ready:amazingdata")
            except Exception as exc:
                self._logger.debug("读取 dask_actor_ready:amazingdata 失败: {}", exc)
                last_value = None
            worker_address = self._extract_worker_address(last_value)
            if worker_address:
                return worker_address

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            await asyncio.sleep(min(0.5, remaining))

        self._logger.warning(
            "等待 AmazingData Actor 就绪标记超时 ({:.1f}s) last_value={!r}",
            timeout_seconds,
            last_value,
        )
        return None

    async def _finalize_status(self) -> None:
        """确定最终初始化状态"""
        async with self._lock:
            self._ready_at = datetime.now()

            if self._scheduler_status.ready and self._amazingdata_status.ready:
                self._phase = DaskInitPhase.READY
                self._message = "Dask 集群完全就绪"
                self._logger.info("Dask 初始化完成: 完全就绪")
            elif self._scheduler_status.ready:
                self._phase = DaskInitPhase.PARTIAL
                self._message = "Dask 集群部分就绪（AmazingData 不可用）"
                self._logger.warning("Dask 初始化完成: 部分就绪")
            else:
                self._phase = DaskInitPhase.FAILED
                self._message = "Dask 集群初始化失败"
                self._logger.error("Dask 初始化失败")

            # 通知等待者
            self._ready_event.set()

    async def _set_failed(self, error: str) -> None:
        """设置失败状态"""
        async with self._lock:
            self._phase = DaskInitPhase.FAILED
            self._message = f"初始化失败: {error}"
            self._ready_at = datetime.now()
            self._ready_event.set()
            self._scheduler_ready_event.set()
            self._amazingdata_ready_event.set()

    # ========================================================================
    # 关闭
    # ========================================================================

    async def shutdown(self) -> None:
        """关闭管理器，取消后台任务"""
        if self._init_task and not self._init_task.done():
            self._init_task.cancel()
            try:
                await self._init_task
            except asyncio.CancelledError:
                pass


# ============================================================================
# 单例管理
# ============================================================================

_init_manager: Optional[DaskInitStateManager] = None
_init_manager_lock = asyncio.Lock()


async def get_dask_init_manager() -> DaskInitStateManager:
    """获取或创建 Dask 初始化状态管理器单例"""
    global _init_manager
    async with _init_manager_lock:
        if _init_manager is None:
            _init_manager = DaskInitStateManager()
        return _init_manager


def get_dask_init_manager_sync() -> Optional[DaskInitStateManager]:
    """同步获取 Dask 初始化状态管理器（可能为 None）"""
    return _init_manager
