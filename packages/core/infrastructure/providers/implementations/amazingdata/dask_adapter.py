"""AmazingData Dask Adapter (Redis Task Queue)

通过 Redis 任务队列远程调用 Windows Worker 上的 AmazingDataActor。
用于分布式部署场景，实现 DataProvider 接口。

Architecture:
    API (FastAPI)                       Worker (Dask)
           │                                   │
           │  ─── Redis RPUSH ─────────────▶  │  (BLPOP 监听)
           │                                   │
           │                      worker.actors["amazingdata"]
           │                              │
           │                      actor.call_sync(method, **kwargs)
           │                              │
           │  ◀─── Redis GET ────────────  │  (结果写入 Redis)

    完全通过 Redis 通信，无需 Dask Client，
    彻底消除 Tornado/asyncio 事件循环冲突。

Features:
    - Redis 任务队列替代 Dask Client（RPUSH/BLPOP）
    - 错误处理和自动重试
    - 超时保护

Usage:
    >>> adapter = AmazingDataDaskAdapter(redis_client=redis, redis_url="redis://...")
    >>> await adapter.initialize()
    >>> result = await adapter.query_kline(code_list=["000001.SZ"], ...)
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime
from time import monotonic
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Sequence

import pandas as pd
from core.infrastructure.providers.interfaces.base import DataProviderError
from loguru import logger

from .amazingdata_types import period_to_sdk_int

if TYPE_CHECKING:
    from redis.asyncio import Redis as AsyncRedis

# Redis key 前缀，用于存储 Dask 调用结果
_REDIS_RESULT_PREFIX = "dask_result:"
_ACTOR_READY_KEY = "dask_actor_ready:amazingdata"
_ACTOR_HEARTBEAT_KEY = "dask_actor_heartbeat:amazingdata"
_BSE_PREFIXES: tuple[str, ...] = ("43", "83", "87", "88")
_SNAPSHOT_BATCH_SIZE = 120


def _normalize_symbol(symbol: str) -> str:
    text = str(symbol or "").strip().upper()
    if not text:
        return ""
    if "." in text:
        code, suffix = text.split(".", 1)
        code = "".join(ch for ch in code if ch.isdigit())
        if suffix in {"SH", "SZ", "BJ"} and code:
            return f"{code}.{suffix}"
        return text
    code = "".join(ch for ch in text if ch.isdigit())
    if len(code) == 6:
        if code.startswith("6"):
            return f"{code}.SH"
        if code.startswith(("0", "3")):
            return f"{code}.SZ"
        if code.startswith(("4", "8")):
            return f"{code}.BJ"
    return code or text


def _resolve_exchange(symbol: str) -> str:
    normalized = _normalize_symbol(symbol)
    if normalized.endswith(".SH"):
        return "SH"
    if normalized.endswith(".SZ"):
        return "SZ"
    if normalized.endswith(".BJ"):
        return "BJ"
    code = normalized.split(".", 1)[0]
    if code.startswith("6"):
        return "SH"
    if code.startswith(("0", "3")):
        return "SZ"
    if code.startswith(("4", "8")):
        return "BJ"
    return "SH"


def _infer_board_labels(symbol: str) -> tuple[str, ...]:
    code = _normalize_symbol(symbol).split(".", 1)[0]
    if not code:
        return ()
    boards: list[str] = []
    if code.startswith(("688", "689")):
        boards.extend(("科创板", "主板"))
    elif code.startswith(("300", "301")):
        boards.extend(("创业板", "主板"))
    elif code.startswith(_BSE_PREFIXES) or code.startswith(("4", "8")):
        boards.append("北证")
    else:
        boards.append("主板")
    return tuple(dict.fromkeys(board for board in boards if board))


class AmazingDataDaskAdapter:
    """AmazingData Redis-based Adapter

    实现 DataProvider 接口，通过 Redis 任务队列远程调用 Worker 上的 Actor。

    使用 Redis 作为双向通道：
    - 任务提交: RPUSH 到 "amazingdata:task_queue"
    - 结果获取: GET "dask_result:{task_id}"
    完全不依赖 Dask Client，消除 Tornado/asyncio 冲突。

    Attributes:
        name: 数据源名称
        _redis: Redis 异步客户端
        _timeout: 远程调用超时时间（秒）
        _retry_count: 失败重试次数
        _windows_worker: 缓存的 Windows Worker 地址
        _actor_available: Actor 是否可用
    """

    name = "amazingdata"

    def __init__(
        self,
        dask_client: Any = None,  # 保留参数兼容性，不再使用
        redis_client: "AsyncRedis | None" = None,
        redis_url: str = "redis://localhost:6379",
        timeout: float = 45.0,
        first_call_timeout: float = 120.0,
        snapshot_timeout: float | None = None,
        retry_count: int = 3,
        scheduler_address: str = "tcp://localhost:8786",
    ):
        """初始化 Adapter

        Args:
            dask_client: 已废弃，保留兼容性
            redis_client: Redis 异步客户端（用于提交任务和获取结果）
            redis_url: Redis 连接 URL
            timeout: 后续调用超时时间（秒），纯 SDK 执行
            first_call_timeout: 首次调用超时时间（秒），包含登录流程
            snapshot_timeout: query_snapshot 方法级超时预算（秒）
            retry_count: 失败重试次数
            scheduler_address: 已废弃，保留兼容性
        """
        self._redis = redis_client
        self._redis_url = redis_url
        self._timeout = timeout
        self._first_call_timeout = first_call_timeout
        snapshot_budget = (
            float(snapshot_timeout) if snapshot_timeout is not None else float(timeout)
        )
        max_budget = max(float(timeout), float(first_call_timeout))
        self._snapshot_timeout = max(12.0, min(snapshot_budget, max_budget))
        self._retry_count = retry_count

        # 缓存 Windows Worker 地址（用于日志）
        self._windows_worker: str | None = None
        self._actor_available = False
        self._initialized = False
        self._first_call_done = False
        self._last_runtime_issue: str | None = None
        self._subscribed_symbols: set[str] = set()
        self._subscription_callbacks: list[Callable[[dict[str, Any]], Awaitable[None] | None]] = []
        self._runtime_recovery_grace_seconds = 6.0
        self._runtime_recovery_poll_interval = 0.2

        logger.info(
            "[AmazingDataDaskAdapter] 初始化 | mode=redis-queue | redis={}",
            "connected" if redis_client else "none",
        )

    @staticmethod
    def _decode_redis_value(raw_value: Any) -> str | None:
        """将 Redis 返回值标准化为字符串。"""
        if raw_value is None:
            return None
        if isinstance(raw_value, bytes):
            return raw_value.decode("utf-8", errors="ignore")
        if isinstance(raw_value, str):
            return raw_value
        return str(raw_value)

    async def _get_redis_ttl(self, key: str) -> int | None:
        """在适配器边界读取 TTL，兼容不完整的类型声明。"""
        if not self._redis:
            return None

        ttl_method = getattr(self._redis, "ttl", None)
        if not callable(ttl_method):
            return None

        ttl_value = await ttl_method(key)
        return ttl_value if isinstance(ttl_value, int) else None

    @staticmethod
    def _extract_worker_address(marker_value: str | None) -> str | None:
        """从 ready/heartbeat 标记中提取 worker 地址。"""
        if not marker_value:
            return None
        idx = marker_value.find("tcp://")
        if idx >= 0:
            return marker_value[idx:]
        return None

    @staticmethod
    def _looks_like_worker_crash(error_text: str) -> bool:
        """根据错误文本判断是否疑似 Worker/SDK 崩溃。"""
        text = (error_text or "").lower()
        crash_signals = (
            "unable to contact actor",
            "unable to contact actor's worker",
            "worker closed",
            "worker died",
            "process exited",
            "access violation",
            "segmentation fault",
            "systemexit",
            "connection reset",
        )
        return any(sig in text for sig in crash_signals)

    async def _probe_actor_runtime(self) -> tuple[bool, str | None]:
        """探测 Actor 运行时是否仍存活（优先 heartbeat，兼容 ready 标记）。"""
        if not self._redis:
            return True, None

        try:
            heartbeat_value = self._decode_redis_value(await self._redis.get(_ACTOR_HEARTBEAT_KEY))
            ready_value = self._decode_redis_value(await self._redis.get(_ACTOR_READY_KEY))

            marker_value = heartbeat_value or ready_value
            if not marker_value:
                return False, "Redis 未检测到 AmazingData Actor 心跳/就绪标记"

            marker_worker = self._extract_worker_address(marker_value)
            if marker_worker and marker_worker != self._windows_worker:
                old_worker = self._windows_worker
                self._windows_worker = marker_worker
                logger.warning(
                    "[AmazingData/Dask] 检测到 Actor Worker 地址变化 | old={} | new={}",
                    old_worker,
                    marker_worker,
                )

            return True, None
        except Exception as exc:
            return False, f"运行时探测异常: {exc}"

    def _mark_actor_unavailable(self, reason: str, error_type: str = "PROCESS_CRASH") -> None:
        """统一处理 Actor 不可用状态，向系统健康面上报。"""
        self._actor_available = False
        self._initialized = False
        self._first_call_done = False
        self._last_runtime_issue = reason

        logger.error("[AmazingData/Dask] 标记 Actor 不可用 | reason={}", reason)

        try:
            from core.infrastructure.monitoring.provider_health import get_monitor

            get_monitor().record_error("amazingdata", error_type, reason)
        except Exception:
            logger.debug("[AmazingData/Dask] 写入 ProviderHealth 失败", exc_info=True)

        try:
            from core.compute.dask_init_state import get_dask_init_manager_sync

            manager = get_dask_init_manager_sync()
            if manager is not None:
                manager.mark_amazingdata_runtime_unavailable(reason)
        except Exception:
            logger.debug("[AmazingData/Dask] 写入 DaskInitState 失败", exc_info=True)

    def _mark_actor_recovered(self) -> None:
        """统一处理 Actor 运行时恢复状态。"""
        was_unavailable = not self._actor_available or bool(self._last_runtime_issue)
        self._actor_available = True
        self._initialized = True
        self._last_runtime_issue = None

        if was_unavailable:
            logger.info(
                "[AmazingData/Dask] 检测到 Actor 运行时恢复 | worker={}",
                self._windows_worker,
            )

        try:
            from core.compute.dask_init_state import get_dask_init_manager_sync

            manager = get_dask_init_manager_sync()
            if manager is not None:
                mark_recovered = getattr(manager, "mark_amazingdata_runtime_recovered", None)
                if callable(mark_recovered):
                    mark_recovered(self._windows_worker)
        except Exception:
            logger.debug("[AmazingData/Dask] 写入 DaskInitState 恢复状态失败", exc_info=True)

    async def _attempt_runtime_recovery(self) -> bool:
        """尝试通过 Redis 运行时标记恢复 Actor 可用状态。"""
        if not self._redis:
            return False

        runtime_alive, runtime_reason = await self._probe_actor_runtime()
        if not runtime_alive:
            logger.warning(
                "[AmazingData/Dask] Actor 运行时恢复失败 | reason={}",
                runtime_reason or "unknown",
            )
            return False

        self._mark_actor_recovered()
        return True

    async def _ensure_runtime_ready_for_call(
        self,
        *,
        method: str,
        wait_seconds: float,
    ) -> None:
        """在提交任务前确认运行时标记可用，避免直接进入长超时。"""
        runtime_alive, runtime_reason = await self._probe_actor_runtime()
        if runtime_alive:
            if (not self._actor_available) or self._last_runtime_issue:
                self._mark_actor_recovered()
            return

        wait_budget = max(self._runtime_recovery_poll_interval, float(wait_seconds))
        deadline = monotonic() + wait_budget
        logger.warning(
            "[AmazingData/Dask] 调用前检测到运行时标记缺失 | method={} | wait_budget={:.1f}s | reason={}",
            method,
            wait_budget,
            runtime_reason or "unknown",
        )

        while monotonic() < deadline:
            await asyncio.sleep(self._runtime_recovery_poll_interval)
            runtime_alive, runtime_reason = await self._probe_actor_runtime()
            if runtime_alive:
                self._mark_actor_recovered()
                logger.info(
                    "[AmazingData/Dask] 调用前运行时恢复成功 | method={} | worker={}",
                    method,
                    self._windows_worker,
                )
                return

        reason = f"Actor 调用前运行时异常: {runtime_reason or 'Redis 未检测到 AmazingData Actor 心跳/就绪标记'}"
        self._mark_actor_unavailable(reason, error_type="PROCESS_CRASH")
        raise DataProviderError(reason)

    # ==================== 连接管理 ====================

    async def _submit_via_redis(self, task_id: str, method: str, kwargs: dict) -> None:
        """通过 Redis 任务队列提交任务到 Worker

        替代 Dask Client.submit()，完全通过 Redis 通信。
        Worker 端的 RedisTaskListener 会 BLPOP 取出任务并执行。

        Args:
            task_id: 任务 ID
            method: Actor 方法名
            kwargs: 方法参数
        """
        task_request = json.dumps(
            {
                "task_id": task_id,
                "method": method,
                "kwargs": kwargs,
            }
        )
        await self._redis.rpush("amazingdata:task_queue", task_request)  # type: ignore[union-attr]
        logger.debug(
            "[AmazingData/Redis] 任务已提交 | task_id={} | method={}",
            task_id,
            method,
        )

    async def initialize(self) -> bool:
        """初始化 Adapter，查找可用的 Windows Worker

        Returns:
            初始化是否成功
        """
        if self._initialized:
            return True

        try:
            # 查找有 WIN:1 资源的 Worker
            self._windows_worker = await self._find_windows_worker()
            if not self._windows_worker:
                logger.error("[AmazingData/Dask] 未找到 Windows Worker (WIN:1)")
                return False

            # 验证 Actor 是否已注册
            self._actor_available = await self._check_actor_available()
            if not self._actor_available:
                logger.error(
                    "[AmazingData/Dask] Worker {} 上未找到 amazingdata Actor",
                    self._windows_worker,
                )
                return False

            self._initialized = True
            self._last_runtime_issue = None
            logger.info(
                "[AmazingData/Dask] 初始化成功 | worker={} | actor=available",
                self._windows_worker,
            )
            return True

        except Exception as e:
            logger.error("[AmazingData/Dask] 初始化失败: {}", e, exc_info=True)
            return False

    async def _find_windows_worker(self) -> str | None:
        """从 Redis 获取 Worker 地址

        Worker 就绪时会设置 Redis key "dask_actor_ready:amazingdata"。

        Returns:
            Worker 地址，未找到返回 None
        """
        if not self._redis:
            return None

        try:
            marker_value = self._decode_redis_value(await self._redis.get(_ACTOR_READY_KEY))
            if not marker_value:
                # 向后兼容：若未设置 ready，尝试读取 heartbeat
                marker_value = self._decode_redis_value(await self._redis.get(_ACTOR_HEARTBEAT_KEY))

            if not marker_value:
                logger.warning("[AmazingData/Dask] Redis 中未找到 Worker 就绪/心跳标记")
                return None

            worker_addr = self._extract_worker_address(marker_value)
            if worker_addr:
                logger.debug(
                    "[AmazingData/Dask] 从 Redis 获取 Worker 地址 | addr={}",
                    worker_addr,
                )
                return worker_addr

            logger.warning(
                "[AmazingData/Dask] Worker 标记格式异常 | value={}",
                marker_value,
            )
            return None

        except Exception as e:
            logger.error("[AmazingData/Dask] 查找 Worker 失败: {}", e)
            return None

    async def _check_actor_available(
        self,
        max_retries: int = 3,
        base_timeout: float = 15.0,
    ) -> bool:
        """检查 Actor 是否已注册（带重试的健康检查）

        使用与 _call_actor 相同的 Redis 轮询模式，避免 asyncio.to_thread + Future.result()
        导致的事件循环冲突问题。

        核心原理：
        1. 提交健康检查任务到 Worker（fire-and-forget）
        2. Worker 检查 actors 字典是否有 "amazingdata" 键
        3. Worker 将结果写入 Redis
        4. Client 轮询 Redis 获取结果

        重试机制（作为兜底保护）：
        - 最多重试 3 次
        - 使用指数退避：15s -> 30s -> 60s
        - 每次重试前等待 2s, 4s, 8s

        注意：这里只检查 Actor 字典是否有 key，不调用任何 Actor 方法，
        因此不会触发登录流程。

        Args:
            max_retries: 最大重试次数
            base_timeout: 基础超时时间（秒），会指数增长

        Returns:
            Actor 是否可用
        """
        if not self._windows_worker:
            logger.warning("[AmazingData/Dask] 无 Windows Worker，跳过 Actor 检查")
            return False

        if not self._redis:
            logger.warning("[AmazingData/Dask] Redis 未配置，跳过 Actor 健康检查")
            return True  # 假定可用，让首次调用时发现问题

        for attempt in range(max_retries):
            # 指数退避：15s, 30s, 60s
            current_timeout = base_timeout * (2**attempt)
            task_id = f"health_check:{uuid.uuid4().hex[:8]}"

            logger.info(
                "[AmazingData/Dask] Actor 健康检查 | "
                "尝试 {}/{} | timeout={}s | worker={} | task_id={}",
                attempt + 1,
                max_retries,
                current_timeout,
                self._windows_worker,
                task_id,
            )

            try:
                result = await self._do_health_check(task_id, current_timeout)
                if result:
                    return True

                # 检查失败但未超时（Actor 确实不存在）
                # 等待后重试
                if attempt < max_retries - 1:
                    wait_time = 2 ** (attempt + 1)  # 2s, 4s, 8s
                    logger.info(
                        "[AmazingData/Dask] Actor 未就绪，{}s 后重试...",
                        wait_time,
                    )
                    await asyncio.sleep(wait_time)

            except Exception as e:
                logger.warning(
                    "[AmazingData/Dask] 健康检查异常 | 尝试 {}/{} | error={}",
                    attempt + 1,
                    max_retries,
                    e,
                )
                if attempt < max_retries - 1:
                    wait_time = 2 ** (attempt + 1)
                    await asyncio.sleep(wait_time)

        logger.error(
            "[AmazingData/Dask] Actor 健康检查失败 | 已重试 {} 次",
            max_retries,
        )
        return False

    async def _do_health_check(self, task_id: str, timeout: float) -> bool:
        """执行单次健康检查

        Args:
            task_id: 任务 ID
            timeout: 超时时间（秒）

        Returns:
            True 如果 Actor 可用，False 否则
        """
        # 通过 Redis 任务队列提交健康检查（使用特殊方法名 "_health_check"）
        await self._submit_via_redis(task_id, "_health_check", {})

        # 轮询 Redis
        redis_key = f"dask_result:{task_id}"
        poll_interval = 0.1  # 100ms
        max_polls = int(timeout / poll_interval)

        for i in range(max_polls):
            result_data = await self._redis.get(redis_key)  # type: ignore[union-attr]
            if result_data:
                await self._redis.delete(redis_key)  # type: ignore[union-attr]
                data = json.loads(result_data)
                if data["status"] == "success":
                    is_available = data["result"]
                    if is_available:
                        logger.info(
                            "[AmazingData/Dask] Actor 健康检查通过 | worker={}",
                            self._windows_worker,
                        )
                    else:
                        logger.warning(
                            "[AmazingData/Dask] Actor 未注册 | worker={}",
                            self._windows_worker,
                        )
                    return is_available
            await asyncio.sleep(poll_interval)

        logger.warning(
            "[AmazingData/Dask] Actor 健康检查超时 ({}s) | worker={}",
            timeout,
            self._windows_worker,
        )
        return False

    def is_connected(self) -> bool:
        """检查是否已连接

        Returns:
            是否已连接并可用
        """
        return self._initialized and self._actor_available

    # ==================== ILifecycleProvider 协议实现 ====================

    async def start(self) -> None:
        """启动 Adapter（已在 initialize 中完成，此处为协议兼容）"""
        pass

    async def stop(self) -> None:
        """停止 Adapter，清理 Redis 连接"""
        if self._redis:
            try:
                await self._redis.close()  # type: ignore[func-returns-value]
            except Exception as e:
                logger.warning("[AmazingData/Dask] 关闭 Redis 连接失败: {}", e)
        self._initialized = False
        self._actor_available = False

    async def health_check(self):
        """健康检查，返回 HealthCheckResult

        通过 DaskInitManager 的状态和 Redis 连通性判断健康状况。
        """
        from core.infrastructure.providers.protocols.lifecycle import (
            HealthCheckResult,
            HealthStatus,
        )

        if not self._initialized:
            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                message="Adapter 未初始化",
            )

        if not self._actor_available:
            recovered = await self._attempt_runtime_recovery()
            if not recovered:
                return HealthCheckResult(
                    status=HealthStatus.UNHEALTHY,
                    message="Actor 不可用",
                )

        # 检查 Redis 连通性
        if self._redis:
            try:
                await self._redis.ping()
            except Exception as e:
                return HealthCheckResult(
                    status=HealthStatus.DEGRADED,
                    message=f"Redis 连接异常: {e}",
                )

        runtime_alive, runtime_reason = await self._probe_actor_runtime()
        if not runtime_alive:
            reason = f"AmazingData Worker 运行时异常: {runtime_reason or '未知'}"
            self._mark_actor_unavailable(reason, error_type="PROCESS_CRASH")
            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                message=reason,
                details={"worker": self._windows_worker},
            )
        self._mark_actor_recovered()

        # 检查 DaskInitManager 的 AmazingData 就绪状态
        try:
            from core.compute.dask_init_state import get_dask_init_manager_sync

            manager = get_dask_init_manager_sync()
            if manager and manager.amazingdata_ready:
                return HealthCheckResult(
                    status=HealthStatus.HEALTHY,
                    message="DaskAdapter 正常运行",
                    details={
                        "worker": self._windows_worker,
                        "first_call_done": self._first_call_done,
                    },
                )
        except Exception:
            pass

        return HealthCheckResult(
            status=HealthStatus.DEGRADED,
            message="Dask Worker 状态未知",
        )

    async def get_runtime_marker_state(self) -> dict[str, Any]:
        """获取 AmazingData Actor 运行时标记诊断信息。"""
        state: dict[str, Any] = {
            "marker_present": False,
            "marker_worker": None,
            "marker_ttl": None,
            "ready_ttl": None,
            "heartbeat_ttl": None,
            "last_runtime_error": self._last_runtime_issue,
        }

        if not self._redis:
            state["error"] = "redis_unavailable"
            return state

        try:
            ready_raw = await self._redis.get(_ACTOR_READY_KEY)
            heartbeat_raw = await self._redis.get(_ACTOR_HEARTBEAT_KEY)
            ready_ttl = await self._get_redis_ttl(_ACTOR_READY_KEY)
            heartbeat_ttl = await self._get_redis_ttl(_ACTOR_HEARTBEAT_KEY)

            ready_value = self._decode_redis_value(ready_raw)
            heartbeat_value = self._decode_redis_value(heartbeat_raw)
            marker_value = heartbeat_value or ready_value
            marker_worker = self._extract_worker_address(marker_value)

            ttl_candidates = [
                ttl for ttl in (ready_ttl, heartbeat_ttl) if isinstance(ttl, int) and ttl >= 0
            ]
            state.update(
                {
                    "marker_present": bool(marker_value),
                    "marker_worker": marker_worker,
                    "marker_ttl": max(ttl_candidates) if ttl_candidates else None,
                    "ready_ttl": (
                        ready_ttl if isinstance(ready_ttl, int) and ready_ttl >= 0 else None
                    ),
                    "heartbeat_ttl": (
                        heartbeat_ttl
                        if isinstance(heartbeat_ttl, int) and heartbeat_ttl >= 0
                        else None
                    ),
                }
            )
            return state
        except Exception as e:
            state["error"] = str(e)
            return state

    # ==================== 核心远程调用 ====================

    async def _call_actor(
        self,
        method: str,
        retry: int = 0,
        timeout_seconds: float | None = None,
        **kwargs: Any,
    ) -> Any:
        """通用远程调用方法

        使用 Redis 作为结果传递通道，彻底绕过 Dask Future 的返回机制。

        实现原理：
        1. 生成唯一的 task_id
        2. 提交任务到 Worker（fire-and-forget，不等待 future.result()）
        3. 轮询 Redis 获取结果（Worker 在完成后将结果存入 Redis）

        为什么需要这样做：
        - Dask Client 内部使用 tornado IOLoop
        - FastAPI 使用 asyncio 事件循环
        - 两者在同一进程中运行时存在根本性冲突
        - future.result() 无法正常返回，即使 Worker 已成功完成任务
        - 尝试过线程隔离、进程隔离，都无法解决
        - Redis 是一个简单可靠的消息传递系统，可以绕过这个问题

        Args:
            method: Actor 方法名 (如 "query_kline")
            retry: 当前重试次数
            **kwargs: 方法参数

        Returns:
            Actor 方法返回值

        Raises:
            DataProviderError: 调用失败或超时
        """
        if not self._actor_available:
            recovered = await self._attempt_runtime_recovery()
            if recovered:
                logger.info(
                    "[AmazingData/Dask] 调用前已恢复 Actor 可用状态 | method={}",
                    method,
                )
            else:
                reason = (
                    f"Actor 不可用（最近异常: {self._last_runtime_issue}）"
                    if self._last_runtime_issue
                    else "Actor 不可用，请先调用 initialize()"
                )
                raise DataProviderError(reason)

        if not self._redis:
            raise DataProviderError("Redis 客户端未配置，无法获取调用结果")

        # 生成唯一任务ID（包含方法名和短UUID，用于 Redis 键和 Dask Dashboard）
        # 格式: {method}:{short_uuid}，例如 query_kline:a1b2c3d4
        task_id = f"{method}:{uuid.uuid4().hex[:8]}"

        # 根据是否首次调用选择超时时间；可被方法级预算覆盖。
        if timeout_seconds is not None and timeout_seconds > 0:
            current_timeout = float(timeout_seconds)
        else:
            current_timeout = (
                self._first_call_timeout if not self._first_call_done else self._timeout
            )

        runtime_wait_budget = min(
            self._runtime_recovery_grace_seconds,
            max(self._runtime_recovery_poll_interval * 2, current_timeout * 0.3),
        )
        await self._ensure_runtime_ready_for_call(
            method=method,
            wait_seconds=runtime_wait_budget,
        )

        try:
            worker_addr = self._windows_worker

            logger.info(
                "[AmazingData/Dask] 提交任务 | method={} | task_id={} | worker={} | timeout={}s{}",
                method,
                task_id,
                worker_addr,
                current_timeout,
                " (首次调用，含登录)" if not self._first_call_done else "",
            )

            # 通过 Redis 任务队列提交（替代 Dask Client.submit）
            await self._submit_via_redis(task_id, method, kwargs)

            # 轮询 Redis 获取结果
            redis_key = f"{_REDIS_RESULT_PREFIX}{task_id}"
            poll_interval = 0.1  # 100ms 轮询间隔
            max_polls = int(current_timeout / poll_interval)

            try:
                for i in range(max_polls):
                    result_data = await self._redis.get(redis_key)
                    if result_data:
                        # 删除 Redis key
                        await self._redis.delete(redis_key)

                        # 解析结果
                        data = json.loads(result_data)
                        if data["status"] == "success":
                            # 首次调用成功，后续使用普通超时
                            if not self._first_call_done:
                                self._first_call_done = True
                                logger.info(
                                    "[AmazingData/Dask] 首次调用成功 | method={} | task_id={} | 后续超时={}s",
                                    method,
                                    task_id,
                                    self._timeout,
                                )
                            else:
                                logger.info(
                                    "[AmazingData/Dask] 调用成功 | method={} | task_id={}",
                                    method,
                                    task_id,
                                )
                            return data["result"]
                        else:
                            error_msg = data.get("error", "Unknown error")
                            logger.error(
                                "[AmazingData/Dask] Worker 返回错误 | method={} | error={}",
                                method,
                                error_msg,
                            )
                            if self._looks_like_worker_crash(error_msg):
                                self._mark_actor_unavailable(
                                    f"Worker 返回崩溃信号: {error_msg}",
                                    error_type="PROCESS_CRASH",
                                )
                            raise DataProviderError(f"Actor 调用失败: {error_msg}")

                    await asyncio.sleep(poll_interval)

                    # 每 10 秒记录一次等待日志
                    if (i + 1) % 100 == 0:
                        elapsed = (i + 1) * poll_interval
                        logger.debug(
                            "[AmazingData/Dask] 等待结果 | method={} | elapsed={:.1f}s",
                            method,
                            elapsed,
                        )

                # 超时 - 删除 Redis key 防止泄漏
                logger.error(
                    "[AmazingData/Dask] 调用超时 | method={} | timeout={}s{}",
                    method,
                    current_timeout,
                    " (首次调用)" if not self._first_call_done else "",
                )

                # 超时时也要删除 Redis key（防止泄漏）
                try:
                    await self._redis.delete(redis_key)
                except Exception as e:
                    logger.warning(
                        "[AmazingData/Dask] 删除超时 Redis key 失败 | key={} | error={}",
                        redis_key,
                        e,
                    )

                runtime_alive, runtime_reason = await self._probe_actor_runtime()
                if not runtime_alive:
                    crash_reason = (
                        f"Actor 调用超时且检测到 Worker 运行时异常: {runtime_reason or '未知'}"
                    )
                    self._mark_actor_unavailable(crash_reason, error_type="PROCESS_CRASH")
                    raise DataProviderError(crash_reason)

                if retry < self._retry_count:
                    logger.info("[AmazingData/Dask] 重试 {}/{}", retry + 1, self._retry_count)
                    return await self._call_actor(
                        method,
                        retry=retry + 1,
                        timeout_seconds=timeout_seconds,
                        **kwargs,
                    )

                raise DataProviderError(f"Actor 调用超时: {method}")

            finally:
                pass  # Redis 模式无需 Future 管理

        except DataProviderError:
            raise
        except Exception as e:
            logger.error(
                "[AmazingData/Dask] 调用失败 | method={} | error_type={} | error={!r}",
                method,
                type(e).__name__,
                str(e),
                exc_info=True,
            )
            if retry < self._retry_count:
                logger.info("[AmazingData/Dask] 重试 {}/{}", retry + 1, self._retry_count)
                await asyncio.sleep(1)  # 延迟重试
                return await self._call_actor(
                    method,
                    retry=retry + 1,
                    timeout_seconds=timeout_seconds,
                    **kwargs,
                )
            raise DataProviderError(f"Actor 调用失败: {method} - {e}")

    async def cleanup_pending_futures(self) -> int:
        """兼容性方法，Redis 模式无需清理 Future"""
        return 0

    # ==================== 基础数据接口 (BaseData) ====================

    async def get_code_info(self, security_type: str = "EXTRA_STOCK_A") -> pd.DataFrame:
        """3.5.2.1 每日最新证券信息

        Args:
            security_type: 代码类型，默认EXTRA_STOCK_A（沪深北A股）

        Returns:
            DataFrame: 证券信息
        """
        result = await self._call_actor("get_code_info", security_type=security_type)
        return pd.DataFrame(result) if result else pd.DataFrame()

    async def get_code_list(self, security_type: str = "EXTRA_STOCK_A") -> list[str] | None:
        """3.5.2.2 每日最新代码列表

        Args:
            security_type: 代码类型

        Returns:
            代码列表
        """
        result = await self._call_actor("get_code_list", security_type=security_type)
        return result

    async def get_future_code_list(self, security_type: str = "EXTRA_FUTURE") -> list[str] | None:
        """3.5.2.3 每日最新代码表（期货交易所）"""
        return await self._call_actor("get_future_code_list", security_type=security_type)

    async def get_option_code_list(self, security_type: str = "EXTRA_ETF_OP") -> list[str] | None:
        """3.5.2.4 每日最新代码表（期权）"""
        return await self._call_actor("get_option_code_list", security_type=security_type)

    async def get_future_code_info(self, security_type: str = "EXTRA_FUTURE") -> pd.DataFrame:
        """期货代码信息（SDK 扩展接口）"""
        result = await self._call_actor("get_future_code_info", security_type=security_type)
        return pd.DataFrame(result) if result else pd.DataFrame()

    async def get_stock_list(
        self,
        market: str | None = None,
        board: str | None = None,
        limit: int | None = None,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """获取股票列表（领域层接口）

        实现 StockListCapable 协议，供 DataProxy 使用。
        将 market/board 参数转换为 security_type 后调用 SDK。

        Args:
            market: 市场过滤 ("SH", "SZ", "BJ")，None 表示全部
            board: 板块过滤 ("主板", "创业板", "科创板")，None 表示全部

        Returns:
            股票信息列表
        """
        # 兼容历史调用：get_stock_list(limit=10) / get_stock_list(10)
        if isinstance(market, int) and board is None and limit is None:
            limit = market
            market = None
        if isinstance(board, int) and limit is None:
            limit = board
            board = None

        if market is None:
            market_value = kwargs.get("market")
            if isinstance(market_value, str):
                market = market_value
        if board is None:
            board_value = kwargs.get("board")
            if isinstance(board_value, str):
                board = board_value
        if limit is None:
            limit_value = kwargs.get("limit")
            if isinstance(limit_value, int):
                limit = limit_value

        # 默认获取沪深北A股
        security_type = "EXTRA_STOCK_A"

        # Actor 会将 get_stock_list 映射到 get_code_list
        result = await self._call_actor("get_code_list", security_type=security_type)

        if result is None:
            return []

        # 转换为领域层期望的格式 (list[dict])，补齐 board 信息供 BoardUniverse 解析。
        stocks = []
        normalized_board_filter = str(board).strip() if isinstance(board, str) else ""
        for code in result:
            if not isinstance(code, str):
                continue
            normalized_symbol = _normalize_symbol(code)
            if not normalized_symbol:
                continue

            # 按市场过滤
            if market:
                if market == "SH" and not normalized_symbol.endswith(".SH"):
                    continue
                if market == "SZ" and not normalized_symbol.endswith(".SZ"):
                    continue
                if market == "BJ" and not normalized_symbol.endswith(".BJ"):
                    continue

            inferred_boards = _infer_board_labels(normalized_symbol)
            if normalized_board_filter and normalized_board_filter not in inferred_boards:
                continue

            board_text = ";".join(inferred_boards)
            stocks.append(
                {
                    "symbol": normalized_symbol,
                    "name": "",
                    "exchange": _resolve_exchange(normalized_symbol),
                    "board": board_text,
                    "board_name": board_text,
                    "LISTPLATE_NAME": board_text,
                }
            )

        if limit is not None and limit >= 0:
            stocks = stocks[:limit]

        return stocks

    # ==================== 实时行情兼容接口 ====================

    async def subscribe_quote(
        self,
        symbols: Sequence[str],
        callback: Callable[[dict[str, Any]], Awaitable[None] | None],
        data_type: str = "snapshot",
    ) -> bool:
        """兼容 AmazingDataProvider 的订阅接口。

        Dask 适配器当前通过 query_snapshot 轮询拉取快照，
        因此这里只维护订阅集合与回调引用，避免上层因接口缺失失败。
        """

        del data_type
        normalized: list[str] = []
        for symbol in symbols:
            if not isinstance(symbol, str):
                continue
            canonical = _normalize_symbol(symbol)
            if canonical:
                normalized.append(canonical)
        if normalized:
            self._subscribed_symbols.update(normalized)
        if callable(callback):
            self._subscription_callbacks.append(callback)
        return True

    async def subscribe_stock_snapshot(
        self,
        symbols: Sequence[str],
        callback: Callable[[dict[str, Any]], Awaitable[None] | None],
        data_type: str = "snapshot",
    ) -> bool:
        """订阅通用入口，保持与 AmazingDataProvider 一致。"""
        return await self.subscribe_quote(symbols, callback, data_type=data_type)

    async def unsubscribe_quote(self, symbols: Sequence[str]) -> bool:
        """取消订阅（Dask 轮询模式仅更新本地订阅集合）。"""
        for symbol in symbols:
            if not isinstance(symbol, str):
                continue
            canonical = _normalize_symbol(symbol)
            if canonical:
                self._subscribed_symbols.discard(canonical)
        return True

    @staticmethod
    def _is_missing_value(value: Any) -> bool:
        if value is None:
            return True
        if isinstance(value, str):
            return not value.strip()
        try:
            return bool(pd.isna(value))
        except Exception:
            return False

    @classmethod
    def _coalesce(cls, *values: Any) -> Any:
        for value in values:
            if cls._is_missing_value(value):
                continue
            return value
        return None

    @staticmethod
    def _to_number(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _to_int(value: Any, default: int = 0) -> int:
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _format_trade_time(value: Any) -> str:
        if isinstance(value, pd.Timestamp):
            return value.to_pydatetime().strftime("%Y-%m-%d %H:%M:%S")
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d %H:%M:%S")
        if isinstance(value, str):
            text = value.strip()
            if text:
                return text
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def _current_date_yyyymmdd() -> int:
        return int(datetime.now().strftime("%Y%m%d"))

    @staticmethod
    def _normalize_yyyymmdd(value: Any, *, field: str) -> int:
        try:
            normalized = int(str(value).strip())
        except (TypeError, ValueError) as exc:
            raise DataProviderError(
                f"AMAZINGDATA_PARAM_INVALID: {field} 必须是 YYYYMMDD 整数，当前值={value!r}"
            ) from exc
        if normalized < 19000101 or normalized > 21991231:
            raise DataProviderError(
                f"AMAZINGDATA_PARAM_INVALID: {field} 超出有效范围，当前值={normalized}"
            )
        return normalized

    @staticmethod
    def _normalize_hhmm(value: Any, *, field: str) -> int:
        try:
            normalized = int(str(value).strip())
        except (TypeError, ValueError) as exc:
            raise DataProviderError(
                f"AMAZINGDATA_PARAM_INVALID: {field} 必须是 HHMM 整数，当前值={value!r}"
            ) from exc
        if normalized < 0 or normalized > 2359:
            raise DataProviderError(
                f"AMAZINGDATA_PARAM_INVALID: {field} 超出有效范围，当前值={normalized}"
            )
        return normalized

    async def _candidate_snapshot_dates(self, today: int) -> list[int]:
        dates: list[int] = [today]
        try:
            calendar = await self.get_calendar()
        except Exception:
            return dates

        normalized_values: set[int] = set()
        for item in calendar:
            if not isinstance(item, (int, float, str)):
                continue
            text = str(item).strip()
            if not text:
                continue
            try:
                normalized_values.add(int(text))
            except ValueError:
                continue
        normalized_calendar = sorted(normalized_values)
        if not normalized_calendar:
            return dates

        latest_on_or_before = max(
            (item for item in normalized_calendar if item <= today), default=None
        )
        if latest_on_or_before is None:
            return dates
        if latest_on_or_before not in dates:
            dates.append(latest_on_or_before)

        try:
            idx = normalized_calendar.index(latest_on_or_before)
        except ValueError:
            return dates
        if idx > 0:
            prev_day = normalized_calendar[idx - 1]
            if prev_day not in dates:
                dates.append(prev_day)
        return dates

    @staticmethod
    def _iter_symbol_batches(
        symbols: Sequence[str],
        *,
        batch_size: int = _SNAPSHOT_BATCH_SIZE,
    ) -> list[list[str]]:
        normalized_size = max(1, int(batch_size))
        return [
            list(symbols[index : index + normalized_size])
            for index in range(0, len(symbols), normalized_size)
        ]

    @classmethod
    def _pick_latest_row(cls, frame: pd.DataFrame) -> dict[str, Any] | None:
        if frame.empty:
            return None
        normalized_columns = {str(column).lower(): column for column in frame.columns}
        trade_column = normalized_columns.get("trade_time") or normalized_columns.get("time")
        if trade_column is not None:
            ordered = frame.copy()
            ordered["__trade_time__"] = pd.to_datetime(
                ordered[trade_column],
                errors="coerce",
            )
            ordered = ordered.sort_values(by="__trade_time__", kind="stable")
            row = ordered.iloc[-1]
        else:
            row = frame.iloc[-1]
        payload: dict[str, Any] = {}
        for key, value in row.items():
            if key == "__trade_time__":
                continue
            payload[str(key).lower()] = value
        return payload

    @classmethod
    def _snapshot_row_to_quote(
        cls,
        fallback_symbol: str,
        row_payload: dict[str, Any],
    ) -> dict[str, Any] | None:
        symbol = cls._coalesce(row_payload.get("code"), row_payload.get("symbol"), fallback_symbol)
        if cls._is_missing_value(symbol):
            return None
        normalized_symbol = _normalize_symbol(str(symbol))
        if not normalized_symbol:
            return None

        last = cls._coalesce(
            row_payload.get("last"),
            row_payload.get("price"),
            row_payload.get("close"),
        )
        pre_close = cls._coalesce(row_payload.get("pre_close"), row_payload.get("prev_close"), last)
        open_price = cls._coalesce(row_payload.get("open"), last)
        high_price = cls._coalesce(row_payload.get("high"), last)
        low_price = cls._coalesce(row_payload.get("low"), last)
        close_price = cls._coalesce(row_payload.get("close"), pre_close, last)
        amount = cls._coalesce(row_payload.get("amount"), 0.0)
        volume = cls._coalesce(row_payload.get("volume"), 0)
        trade_time = cls._format_trade_time(
            cls._coalesce(row_payload.get("trade_time"), row_payload.get("time"))
        )

        quote: dict[str, Any] = {
            "symbol": normalized_symbol,
            "name": str(cls._coalesce(row_payload.get("name"), "")),
            "time": trade_time,
            "last": cls._to_number(last, 0.0),
            "open": cls._to_number(open_price, 0.0),
            "high": cls._to_number(high_price, 0.0),
            "low": cls._to_number(low_price, 0.0),
            "close": cls._to_number(close_price, 0.0),
            "amount": cls._to_number(amount, 0.0),
            "volume": cls._to_int(volume, 0),
            "status": cls._coalesce(
                row_payload.get("status"),
                row_payload.get("trading_phase_code"),
            ),
        }
        quote["pre_close"] = cls._to_number(pre_close, quote["close"])

        ask_price1 = cls._coalesce(row_payload.get("ask_price1"), row_payload.get("ask1"))
        ask_volume1 = cls._coalesce(row_payload.get("ask_volume1"), row_payload.get("ask1_volume"))
        bid_price1 = cls._coalesce(row_payload.get("bid_price1"), row_payload.get("bid1"))
        bid_volume1 = cls._coalesce(row_payload.get("bid_volume1"), row_payload.get("bid1_volume"))
        if not cls._is_missing_value(ask_price1):
            quote["ask1"] = cls._to_number(ask_price1, 0.0)
        if not cls._is_missing_value(ask_volume1):
            quote["ask1_volume"] = cls._to_int(ask_volume1, 0)
        if not cls._is_missing_value(bid_price1):
            quote["bid1"] = cls._to_number(bid_price1, 0.0)
        if not cls._is_missing_value(bid_volume1):
            quote["bid1_volume"] = cls._to_int(bid_volume1, 0)

        high_limit = cls._coalesce(row_payload.get("high_limited"), row_payload.get("high_limit"))
        low_limit = cls._coalesce(row_payload.get("low_limited"), row_payload.get("low_limit"))
        if not cls._is_missing_value(high_limit):
            quote["high_limit"] = cls._to_number(high_limit, 0.0)
        if not cls._is_missing_value(low_limit):
            quote["low_limit"] = cls._to_number(low_limit, 0.0)
        return quote

    @classmethod
    def _snapshot_payload_to_quotes(
        cls,
        snapshot_payload: dict[str, pd.DataFrame] | None,
        requested_symbols: Sequence[str],
    ) -> dict[str, dict[str, Any]]:
        if not snapshot_payload:
            return {}

        frames_by_symbol: dict[str, pd.DataFrame] = {}
        for symbol_key, frame_value in snapshot_payload.items():
            if not isinstance(frame_value, pd.DataFrame):
                continue
            normalized_key = _normalize_symbol(str(symbol_key))
            if normalized_key:
                frames_by_symbol[normalized_key] = frame_value

        quotes: dict[str, dict[str, Any]] = {}
        for symbol in requested_symbols:
            symbol_frame = frames_by_symbol.get(symbol)
            if symbol_frame is None:
                continue
            row_payload = cls._pick_latest_row(symbol_frame)
            if not row_payload:
                continue
            quote = cls._snapshot_row_to_quote(symbol, row_payload)
            if quote:
                quotes[symbol] = quote
        return quotes

    async def get_realtime_quote(
        self,
        symbols: Sequence[str] | str,
    ) -> dict[str, dict[str, Any]]:
        """兼容实时行情接口，基于 query_snapshot 生成最新快照字典。"""
        if isinstance(symbols, str):
            raw_symbols: list[str] = [symbols]
        else:
            raw_symbols = [str(item) for item in symbols if isinstance(item, str)]

        normalized_symbols = [
            symbol for symbol in (_normalize_symbol(item) for item in raw_symbols) if symbol
        ]
        # 去重并保持顺序
        deduped_symbols = list(dict.fromkeys(normalized_symbols))
        if not deduped_symbols:
            return {}

        today = self._current_date_yyyymmdd()
        candidate_dates = await self._candidate_snapshot_dates(today)
        symbol_batches = self._iter_symbol_batches(deduped_symbols)

        for candidate_date in candidate_dates:
            quotes: dict[str, dict[str, Any]] = {}
            for batch in symbol_batches:
                try:
                    snapshot_payload = await self.query_snapshot(
                        code_list=batch,
                        begin_date=candidate_date,
                        end_date=candidate_date,
                    )
                except Exception as exc:
                    logger.warning(
                        "[AmazingData/Dask] get_realtime_quote 查询失败 | date={} | batch={} | error={}",
                        candidate_date,
                        len(batch),
                        exc,
                    )
                    continue

                batch_quotes = self._snapshot_payload_to_quotes(snapshot_payload, batch)
                if batch_quotes:
                    quotes.update(batch_quotes)
            if quotes:
                return quotes
        return {}

    async def get_calendar_range(
        self,
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> list[int] | None:
        """3.5.2.7 交易日历（SDK 原生 API）

        Args:
            begin_date: 开始日期 (YYYYMMDD)
            end_date: 结束日期 (YYYYMMDD)

        Returns:
            交易日列表
        """
        kwargs: dict[str, Any] = {}
        if begin_date is not None:
            kwargs["begin_date"] = begin_date
        if end_date is not None:
            kwargs["end_date"] = end_date

        result = await self._call_actor("get_calendar", **kwargs)
        return result

    async def get_calendar(
        self,
        market: str = "SH",
        data_type: str = "int",
    ) -> list[int]:
        """获取交易日历（领域层接口）

        实现 CalendarCapable 协议，供 DataProxy 使用。

        Args:
            market: 市场代码 ("SH", "SZ", "BJ")，A股市场统一日历，此参数仅为接口兼容
            data_type: 返回数据类型 ("int" 或 "str")，兼容 factory 调用

        Returns:
            交易日列表 (格式: 20250102)
        """
        # SDK 的 get_calendar() 不接受 market 参数，A股市场统一使用同一日历
        # 这里不传递任何参数给 Actor，由 Actor 内部调用 SDK 的无参版本
        logger.debug("DaskAdapter.get_calendar: 开始调用 Actor")
        result = await self._call_actor("get_calendar")
        if result is None:
            logger.debug("DaskAdapter.get_calendar: Actor 返回 None")
            return []
        converted = [int(d) for d in result]
        logger.debug("DaskAdapter.get_calendar: 获取到 {} 条交易日", len(converted))
        return converted

    async def get_backward_factor(
        self,
        code_list: list[str],
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> pd.DataFrame:
        """3.5.2.4 复权因子（后复权）

        Args:
            code_list: 代码列表
            begin_date: 开始日期
            end_date: 结束日期

        Returns:
            DataFrame: 复权因子
        """
        result = await self._call_actor(
            "get_backward_factor",
            code_list=code_list,
            begin_date=begin_date,
            end_date=end_date,
        )
        return pd.DataFrame(result) if result else pd.DataFrame()

    async def get_adj_factor(
        self,
        code_list: list[str],
        local_path: str | None = None,
        is_local: bool = True,
    ) -> pd.DataFrame:
        """3.5.2.6 复权因子（单次复权因子）"""
        kwargs: dict[str, Any] = {"code_list": code_list, "is_local": is_local}
        if local_path is not None:
            kwargs["local_path"] = local_path
        result = await self._call_actor("get_adj_factor", **kwargs)
        return pd.DataFrame(result) if result else pd.DataFrame()

    async def get_hist_code_list(
        self,
        begin_date: int | None = None,
        end_date: int | None = None,
        security_type: str = "EXTRA_STOCK_A",
    ) -> pd.DataFrame:
        """3.5.2.6 历史代码列表

        Args:
            begin_date: 开始日期
            end_date: 结束日期
            security_type: 证券类型

        Returns:
            DataFrame: 历史代码列表
        """
        result = await self._call_actor(
            "get_hist_code_list",
            begin_date=begin_date,
            end_date=end_date,
            security_type=security_type,
        )
        return pd.DataFrame(result) if result else pd.DataFrame()

    async def get_history_stock_status(
        self,
        code_list: list[str],
        local_path: str | None = None,
        is_local: bool = True,
    ) -> pd.DataFrame:
        """3.5.2.9 历史证券信息

        SDK v1.0.4: 签名改为 (code_list, local_path, is_local)，移除 date 参数

        Args:
            code_list: 代码列表
            local_path: 本地缓存路径
            is_local: 是否优先读取本地缓存

        Returns:
            DataFrame: 历史证券状态
        """
        kwargs: dict[str, Any] = {"code_list": code_list}
        if local_path is not None:
            kwargs["local_path"] = local_path
        kwargs["is_local"] = is_local
        result = await self._call_actor("get_history_stock_status", **kwargs)
        return pd.DataFrame(result) if result else pd.DataFrame()

    async def get_bj_code_mapping(
        self,
        local_path: str | None = None,
        is_local: bool = True,
    ) -> pd.DataFrame:
        """3.5.2.10 北交所代码映射

        SDK v1.0.4: 签名改为 (local_path, is_local)，无 code_list

        Returns:
            DataFrame: 北交所代码映射
        """
        kwargs: dict[str, Any] = {}
        if local_path is not None:
            kwargs["local_path"] = local_path
        kwargs["is_local"] = is_local
        result = await self._call_actor("get_bj_code_mapping", **kwargs)
        return pd.DataFrame(result) if result else pd.DataFrame()

    async def get_stock_basic(
        self,
        code_list: list[str],
        local_path: str | None = None,
        is_local: bool = True,
    ) -> pd.DataFrame:
        """3.5.2.8 证券基础信息"""
        kwargs: dict[str, Any] = {"code_list": code_list, "is_local": is_local}
        if local_path is not None:
            kwargs["local_path"] = local_path
        result = await self._call_actor("get_stock_basic", **kwargs)
        return pd.DataFrame(result) if result else pd.DataFrame()

    # ==================== 历史行情接口 (MarketData) ====================

    async def query_snapshot(
        self,
        code_list: list[str],
        begin_date: int,
        end_date: int,
        *,
        begin_time: int | None = None,
        end_time: int | None = None,
    ) -> dict[str, pd.DataFrame] | None:
        """3.5.4.1 历史快照

        Args:
            code_list: 代码列表
            begin_date: 开始日期 (YYYYMMDD)
            end_date: 结束日期 (YYYYMMDD)
            begin_time: 起始时间 (HHMM)
            end_time: 结束时间 (HHMM)

        Returns:
            字典，key为代码，value为DataFrame
        """
        normalized_codes = [
            code
            for code in (
                _normalize_symbol(str(item)) for item in (code_list or []) if isinstance(item, str)
            )
            if code
        ]
        if not normalized_codes:
            raise DataProviderError("AMAZINGDATA_PARAM_INVALID: code_list 不能为空")

        normalized_begin = self._normalize_yyyymmdd(begin_date, field="begin_date")
        normalized_end = self._normalize_yyyymmdd(end_date, field="end_date")
        if normalized_begin > normalized_end:
            raise DataProviderError("AMAZINGDATA_PARAM_INVALID: begin_date 不能晚于 end_date")

        kwargs: dict[str, Any] = {
            "code_list": normalized_codes,
            "begin_date": normalized_begin,
            "end_date": normalized_end,
        }
        if begin_time is not None:
            kwargs["begin_time"] = self._normalize_hhmm(begin_time, field="begin_time")
        if end_time is not None:
            kwargs["end_time"] = self._normalize_hhmm(end_time, field="end_time")

        result = await self._call_actor(
            "query_snapshot",
            timeout_seconds=self._snapshot_timeout,
            **kwargs,
        )
        if result is None:
            return None

        # 转换结果
        if not isinstance(result, dict):
            raise DataProviderError(
                "AMAZINGDATA_SNAPSHOT_INVALID_RESULT: query_snapshot 返回值不是字典结构"
            )
        return {str(k): pd.DataFrame(v) for k, v in result.items()}

    async def query_kline(
        self,
        code_list: list[str],
        begin_date: int,
        end_date: int,
        period: str | None = None,
    ) -> dict[str, pd.DataFrame] | None:
        """3.5.4.2 历史K线

        Args:
            code_list: 代码列表
            begin_date: 开始日期 (YYYYMMDD)
            end_date: 结束日期 (YYYYMMDD)
            period: 周期，默认日线 ("day")

        Returns:
            字典，key为代码，value为DataFrame
        """
        kwargs: dict[str, Any] = {
            "code_list": code_list,
            "begin_date": begin_date,
            "end_date": end_date,
        }
        # SDK v1.0.4: period 必须传整数（Period 枚举值从字符串改为 int）
        kwargs["period"] = period_to_sdk_int(period)

        result = await self._call_actor("query_kline", **kwargs)
        if result is None:
            return None

        # 转换结果
        return {k: pd.DataFrame(v) for k, v in result.items()}

    # ==================== 财务数据接口 (InfoData) ====================

    async def get_balance_sheet(
        self,
        code_list: list[str],
        local_path: str | None = None,
        is_local: bool = True,
    ) -> pd.DataFrame:
        """3.5.5.1 资产负债表

        SDK v1.0.4: 签名改为 (code_list, local_path, is_local)

        Args:
            code_list: 股票代码列表
            local_path: 本地缓存路径
            is_local: 是否优先读取本地缓存

        Returns:
            DataFrame: 资产负债表数据
        """
        kwargs: dict[str, Any] = {"code_list": code_list}
        if local_path is not None:
            kwargs["local_path"] = local_path
        kwargs["is_local"] = is_local
        result = await self._call_actor("get_balance_sheet", **kwargs)
        return pd.DataFrame(result) if result else pd.DataFrame()

    async def get_cash_flow(
        self,
        code_list: list[str],
        local_path: str | None = None,
        is_local: bool = True,
    ) -> pd.DataFrame:
        """3.5.5.2 现金流量表

        SDK v1.0.4: 签名改为 (code_list, local_path, is_local)

        Args:
            code_list: 股票代码列表
            local_path: 本地缓存路径
            is_local: 是否优先读取本地缓存

        Returns:
            DataFrame: 现金流量表数据
        """
        kwargs: dict[str, Any] = {"code_list": code_list}
        if local_path is not None:
            kwargs["local_path"] = local_path
        kwargs["is_local"] = is_local
        result = await self._call_actor("get_cash_flow", **kwargs)
        return pd.DataFrame(result) if result else pd.DataFrame()

    async def get_income(
        self,
        code_list: list[str],
        local_path: str | None = None,
        is_local: bool = True,
    ) -> pd.DataFrame:
        """3.5.5.3 利润表

        SDK v1.0.4: 签名改为 (code_list, local_path, is_local)

        Args:
            code_list: 股票代码列表
            local_path: 本地缓存路径
            is_local: 是否优先读取本地缓存

        Returns:
            DataFrame: 利润表数据
        """
        kwargs: dict[str, Any] = {"code_list": code_list}
        if local_path is not None:
            kwargs["local_path"] = local_path
        kwargs["is_local"] = is_local
        result = await self._call_actor("get_income", **kwargs)
        return pd.DataFrame(result) if result else pd.DataFrame()

    async def get_profit_express(
        self,
        code_list: list[str],
        local_path: str | None = None,
        is_local: bool = True,
    ) -> pd.DataFrame:
        """3.5.5.4 业绩快报

        SDK v1.0.4: 签名改为 (code_list, local_path, is_local)

        Args:
            code_list: 股票代码列表
            local_path: 本地缓存路径
            is_local: 是否优先读取本地缓存

        Returns:
            DataFrame: 业绩快报数据
        """
        kwargs: dict[str, Any] = {"code_list": code_list}
        if local_path is not None:
            kwargs["local_path"] = local_path
        kwargs["is_local"] = is_local
        result = await self._call_actor("get_profit_express", **kwargs)
        return pd.DataFrame(result) if result else pd.DataFrame()

    async def get_profit_notice(
        self,
        code_list: list[str],
        local_path: str | None = None,
        is_local: bool = True,
    ) -> pd.DataFrame:
        """3.5.5.5 业绩预告

        SDK v1.0.4: 签名改为 (code_list, local_path, is_local)

        Args:
            code_list: 股票代码列表
            local_path: 本地缓存路径
            is_local: 是否优先读取本地缓存

        Returns:
            DataFrame: 业绩预告数据
        """
        kwargs: dict[str, Any] = {"code_list": code_list}
        if local_path is not None:
            kwargs["local_path"] = local_path
        kwargs["is_local"] = is_local
        result = await self._call_actor("get_profit_notice", **kwargs)
        return pd.DataFrame(result) if result else pd.DataFrame()

    # ==================== 股东数据接口 ====================

    async def get_share_holder(
        self,
        code_list: list[str],
        local_path: str | None = None,
        is_local: bool = True,
    ) -> pd.DataFrame:
        """3.5.6.1 十大股东

        SDK v1.0.4: 签名改为 (code_list, local_path, is_local)

        Args:
            code_list: 股票代码列表
            local_path: 本地缓存路径
            is_local: 是否优先读取本地缓存

        Returns:
            DataFrame: 十大股东数据
        """
        kwargs: dict[str, Any] = {"code_list": code_list}
        if local_path is not None:
            kwargs["local_path"] = local_path
        kwargs["is_local"] = is_local
        result = await self._call_actor("get_share_holder", **kwargs)
        return pd.DataFrame(result) if result else pd.DataFrame()

    async def get_holder_num(
        self,
        code_list: list[str],
        local_path: str | None = None,
        is_local: bool = True,
    ) -> pd.DataFrame:
        """股东人数

        SDK v1.0.4: 签名改为 (code_list, local_path, is_local)

        Args:
            code_list: 股票代码列表
            local_path: 本地缓存路径
            is_local: 是否优先读取本地缓存

        Returns:
            DataFrame: 股东人数数据
        """
        kwargs: dict[str, Any] = {"code_list": code_list}
        if local_path is not None:
            kwargs["local_path"] = local_path
        kwargs["is_local"] = is_local
        result = await self._call_actor("get_holder_num", **kwargs)
        return pd.DataFrame(result) if result else pd.DataFrame()

    async def get_equity_structure(
        self,
        code_list: list[str],
        local_path: str | None = None,
        is_local: bool = True,
    ) -> pd.DataFrame:
        """股本结构

        SDK v1.0.4: 签名改为 (code_list, local_path, is_local)

        Args:
            code_list: 股票代码列表
            local_path: 本地缓存路径
            is_local: 是否优先读取本地缓存

        Returns:
            DataFrame: 股本结构数据
        """
        kwargs: dict[str, Any] = {"code_list": code_list}
        if local_path is not None:
            kwargs["local_path"] = local_path
        kwargs["is_local"] = is_local
        result = await self._call_actor("get_equity_structure", **kwargs)
        return pd.DataFrame(result) if result else pd.DataFrame()

    async def get_equity_pledge_freeze(
        self,
        code_list: list[str],
        local_path: str | None = None,
        is_local: bool = True,
    ) -> pd.DataFrame:
        """股权质押冻结

        SDK v1.0.4: 签名改为 (code_list, local_path, is_local)

        Args:
            code_list: 股票代码列表
            local_path: 本地缓存路径
            is_local: 是否优先读取本地缓存

        Returns:
            DataFrame: 股权质押冻结数据
        """
        kwargs: dict[str, Any] = {"code_list": code_list}
        if local_path is not None:
            kwargs["local_path"] = local_path
        kwargs["is_local"] = is_local
        result = await self._call_actor("get_equity_pledge_freeze", **kwargs)
        return pd.DataFrame(result) if result else pd.DataFrame()

    async def get_equity_restricted(
        self,
        code_list: list[str],
        local_path: str | None = None,
        is_local: bool = True,
    ) -> pd.DataFrame:
        """限售股解禁

        SDK v1.0.4: 签名改为 (code_list, local_path, is_local)

        Args:
            code_list: 股票代码列表
            local_path: 本地缓存路径
            is_local: 是否优先读取本地缓存

        Returns:
            DataFrame: 限售股解禁数据
        """
        kwargs: dict[str, Any] = {"code_list": code_list}
        if local_path is not None:
            kwargs["local_path"] = local_path
        kwargs["is_local"] = is_local
        result = await self._call_actor("get_equity_restricted", **kwargs)
        return pd.DataFrame(result) if result else pd.DataFrame()

    # ==================== 资讯数据接口 ====================

    async def get_dividend(
        self,
        code_list: list[str],
        local_path: str | None = None,
        is_local: bool = True,
    ) -> pd.DataFrame:
        """3.5.7.5 分红配送

        SDK v1.0.4: 签名改为 (code_list, local_path, is_local)

        Args:
            code_list: 股票代码列表
            local_path: 本地缓存路径
            is_local: 是否优先读取本地缓存

        Returns:
            DataFrame: 分红配送数据
        """
        kwargs: dict[str, Any] = {"code_list": code_list}
        if local_path is not None:
            kwargs["local_path"] = local_path
        kwargs["is_local"] = is_local
        result = await self._call_actor("get_dividend", **kwargs)
        return pd.DataFrame(result) if result else pd.DataFrame()

    async def get_right_issue(
        self,
        code_list: list[str],
        local_path: str | None = None,
        is_local: bool = True,
    ) -> pd.DataFrame:
        """配股

        SDK v1.0.4: 签名改为 (code_list, local_path, is_local)
        SDK Bug 已通过 sdk_patches.py monkey-patch 修复 (reindex 替代直接列选择)

        Args:
            code_list: 股票代码列表
            local_path: 本地缓存路径
            is_local: 是否优先读取本地缓存
        """
        kwargs: dict[str, Any] = {"code_list": code_list}
        if local_path is not None:
            kwargs["local_path"] = local_path
        kwargs["is_local"] = is_local
        result = await self._call_actor("get_right_issue", **kwargs)
        return pd.DataFrame(result) if result else pd.DataFrame()

    async def get_margin_summary(
        self,
        local_path: str | None = None,
        is_local: bool = True,
    ) -> pd.DataFrame:
        """3.5.7.2 融资融券汇总

        SDK v1.0.4: 签名改为 (local_path, is_local)，无 code_list

        Args:
            local_path: 本地缓存路径
            is_local: 是否优先读取本地缓存

        Returns:
            DataFrame: 融资融券汇总数据
        """
        kwargs: dict[str, Any] = {}
        if local_path is not None:
            kwargs["local_path"] = local_path
        kwargs["is_local"] = is_local
        result = await self._call_actor("get_margin_summary", **kwargs)
        return pd.DataFrame(result) if result else pd.DataFrame()

    async def get_margin_detail(
        self,
        code_list: list[str],
        local_path: str | None = None,
        is_local: bool = True,
    ) -> pd.DataFrame:
        """融资融券明细

        SDK v1.0.4: 签名改为 (code_list, local_path, is_local)
        SDK Bug 已通过 sdk_patches.py monkey-patch 修复 (大小写 + 路径)

        Args:
            code_list: 股票代码列表
            local_path: 本地缓存路径
            is_local: 是否优先读取本地缓存
        """
        kwargs: dict[str, Any] = {"code_list": code_list}
        if local_path is not None:
            kwargs["local_path"] = local_path
        kwargs["is_local"] = is_local
        result = await self._call_actor("get_margin_detail", **kwargs)
        return pd.DataFrame(result) if result else pd.DataFrame()

    async def get_long_hu_bang(
        self,
        code_list: list[str],
        local_path: str | None = None,
        is_local: bool = True,
    ) -> pd.DataFrame:
        """3.5.7.4 龙虎榜

        SDK v1.0.4: 签名改为 (code_list, local_path, is_local)

        Args:
            code_list: 股票代码列表
            local_path: 本地缓存路径
            is_local: 是否优先读取本地缓存

        Returns:
            DataFrame: 龙虎榜数据
        """
        kwargs: dict[str, Any] = {"code_list": code_list}
        if local_path is not None:
            kwargs["local_path"] = local_path
        kwargs["is_local"] = is_local
        result = await self._call_actor("get_long_hu_bang", **kwargs)
        return pd.DataFrame(result) if result else pd.DataFrame()

    async def get_block_trading(
        self,
        code_list: list[str],
        local_path: str | None = None,
        is_local: bool = True,
    ) -> pd.DataFrame:
        """3.5.7.1 大宗交易

        SDK v1.0.4: 签名改为 (code_list, local_path, is_local)

        Args:
            code_list: 股票代码列表
            local_path: 本地缓存路径
            is_local: 是否优先读取本地缓存

        Returns:
            DataFrame: 大宗交易数据
        """
        kwargs: dict[str, Any] = {"code_list": code_list}
        if local_path is not None:
            kwargs["local_path"] = local_path
        kwargs["is_local"] = is_local
        result = await self._call_actor("get_block_trading", **kwargs)
        return pd.DataFrame(result) if result else pd.DataFrame()

    # ==================== 行业数据接口 ====================

    @staticmethod
    def _result_to_dataframe(result: Any) -> pd.DataFrame:
        """将 Actor 返回结果转换为 DataFrame。"""
        if result is None:
            return pd.DataFrame()
        if isinstance(result, pd.DataFrame):
            return result.copy()
        if isinstance(result, list):
            return pd.DataFrame(result)
        if isinstance(result, dict):
            return pd.DataFrame(result)
        return pd.DataFrame([result])

    @classmethod
    def _industry_result_to_dataframe(
        cls,
        result: Any,
        *,
        preferred_code: str | None = None,
    ) -> pd.DataFrame:
        """处理行业接口常见的 dict[index_code -> list[records]] 结构。"""
        if not isinstance(result, dict):
            return cls._result_to_dataframe(result)

        normalized_code = str(preferred_code or "").strip().upper()
        if normalized_code:
            for key, value in result.items():
                key_token = str(key or "").strip().upper()
                if key_token == normalized_code:
                    return cls._result_to_dataframe(value)

        frames: list[pd.DataFrame] = []
        for key, value in result.items():
            frame = cls._result_to_dataframe(value)
            if frame.empty:
                continue
            if "INDEX_CODE" not in frame.columns:
                frame = frame.copy()
                frame["INDEX_CODE"] = str(key)
            frames.append(frame)

        if frames:
            return pd.concat(frames, ignore_index=True)

        return cls._result_to_dataframe(result)

    async def get_industry_daily(
        self,
        industry_code: str,
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> pd.DataFrame:
        """行业日线

        Args:
            industry_code: 行业代码
            begin_date: 开始日期
            end_date: 结束日期

        Returns:
            DataFrame: 行业日线数据
        """
        # SDK v1.0.4: get_industry_daily(code_list, local_path, is_local, **kwargs)
        kwargs: dict[str, Any] = {"code_list": [industry_code]}
        if begin_date is not None:
            kwargs["begin_date"] = begin_date
        if end_date is not None:
            kwargs["end_date"] = end_date

        result = await self._call_actor("get_industry_daily", **kwargs)
        return self._industry_result_to_dataframe(result, preferred_code=industry_code)

    async def get_industry_weight(
        self,
        industry_code: str,
        date: int | None = None,
    ) -> pd.DataFrame:
        """行业权重

        Args:
            industry_code: 行业代码
            date: 日期

        Returns:
            DataFrame: 行业权重数据
        """
        # SDK v1.0.4: get_industry_weight(code_list, local_path, is_local, **kwargs)
        kwargs: dict[str, Any] = {"code_list": [industry_code]}
        if date is not None:
            kwargs["date"] = date

        result = await self._call_actor("get_industry_weight", **kwargs)
        return self._industry_result_to_dataframe(result, preferred_code=industry_code)

    async def get_industry_constituent(
        self,
        industry_code: str,
        date: int | None = None,
    ) -> pd.DataFrame:
        """行业成分股

        Args:
            industry_code: 行业代码
            date: 日期

        Returns:
            DataFrame: 行业成分股数据
        """
        if date is not None:
            logger.debug(
                "[AmazingData/Dask] get_industry_constituent 忽略 date 参数: {}",
                date,
            )

        # SDK v1.0.4: get_industry_constituent(code_list, local_path, is_local)
        result = await self._call_actor(
            "get_industry_constituent",
            code_list=[industry_code],
        )
        return self._industry_result_to_dataframe(result, preferred_code=industry_code)

    async def get_industry_base_info(
        self,
        industry_type: str | None = None,
    ) -> pd.DataFrame:
        """行业基础信息

        Args:
            industry_type: 行业分类类型

        Returns:
            DataFrame: 行业基础信息
        """
        if industry_type is not None:
            logger.debug(
                "[AmazingData/Dask] get_industry_base_info 忽略 industry_type 参数: {}",
                industry_type,
            )

        # SDK v1.0.4: get_industry_base_info(local_path, is_local)
        result = await self._call_actor("get_industry_base_info")
        return pd.DataFrame(result) if result else pd.DataFrame()

    # ==================== 特色数据接口 ====================

    async def get_option_basic_info(
        self,
        code_list: list[str],
    ) -> pd.DataFrame:
        """期权基础信息

        Args:
            code_list: 期权代码列表

        Returns:
            DataFrame: 期权基础信息
        """
        result = await self._call_actor("get_option_basic_info", code_list=code_list)
        return pd.DataFrame(result) if result else pd.DataFrame()

    async def get_option_std_ctr_specs(
        self,
        underlying_code: str | None = None,
    ) -> pd.DataFrame:
        """期权标准合约规格

        Args:
            underlying_code: 标的代码

        Returns:
            DataFrame: 期权标准合约规格
        """
        kwargs: dict[str, Any] = {}
        if underlying_code is not None:
            kwargs["underlying_code"] = underlying_code

        result = await self._call_actor("get_option_std_ctr_specs", **kwargs)
        return pd.DataFrame(result) if result else pd.DataFrame()

    async def get_option_mon_ctr_specs(
        self,
        underlying_code: str | None = None,
        month: str | None = None,
    ) -> pd.DataFrame:
        """期权月度合约

        Args:
            underlying_code: 标的代码
            month: 月份

        Returns:
            DataFrame: 期权月度合约
        """
        kwargs: dict[str, Any] = {}
        if underlying_code is not None:
            kwargs["underlying_code"] = underlying_code
        if month is not None:
            kwargs["month"] = month

        result = await self._call_actor("get_option_mon_ctr_specs", **kwargs)
        return pd.DataFrame(result) if result else pd.DataFrame()

    async def get_option_mon_ctr_spcon(
        self,
        underlying_code: str | None = None,
        month: str | None = None,
    ) -> pd.DataFrame:
        """兼容旧方法名，内部转发到 get_option_mon_ctr_specs。"""
        return await self.get_option_mon_ctr_specs(underlying_code, month)

    async def get_kzz_issuance(
        self, code_list: list[str], local_path: str | None = None, is_local: bool = True
    ) -> pd.DataFrame:
        kwargs: dict[str, Any] = {"code_list": code_list, "is_local": is_local}
        if local_path is not None:
            kwargs["local_path"] = local_path
        result = await self._call_actor("get_kzz_issuance", **kwargs)
        return pd.DataFrame(result) if result else pd.DataFrame()

    async def get_kzz_share(
        self, code_list: list[str], local_path: str | None = None, is_local: bool = True
    ) -> pd.DataFrame:
        kwargs: dict[str, Any] = {"code_list": code_list, "is_local": is_local}
        if local_path is not None:
            kwargs["local_path"] = local_path
        result = await self._call_actor("get_kzz_share", **kwargs)
        return pd.DataFrame(result) if result else pd.DataFrame()

    async def get_kzz_conv(
        self, code_list: list[str], local_path: str | None = None, is_local: bool = True
    ) -> pd.DataFrame:
        kwargs: dict[str, Any] = {"code_list": code_list, "is_local": is_local}
        if local_path is not None:
            kwargs["local_path"] = local_path
        result = await self._call_actor("get_kzz_conv", **kwargs)
        return pd.DataFrame(result) if result else pd.DataFrame()

    async def get_kzz_conv_change(
        self, code_list: list[str], local_path: str | None = None, is_local: bool = True
    ) -> pd.DataFrame:
        kwargs: dict[str, Any] = {"code_list": code_list, "is_local": is_local}
        if local_path is not None:
            kwargs["local_path"] = local_path
        result = await self._call_actor("get_kzz_conv_change", **kwargs)
        return pd.DataFrame(result) if result else pd.DataFrame()

    async def get_kzz_corr(
        self, code_list: list[str], local_path: str | None = None, is_local: bool = True
    ) -> pd.DataFrame:
        kwargs: dict[str, Any] = {"code_list": code_list, "is_local": is_local}
        if local_path is not None:
            kwargs["local_path"] = local_path
        result = await self._call_actor("get_kzz_corr", **kwargs)
        return pd.DataFrame(result) if result else pd.DataFrame()

    async def get_kzz_call(
        self, code_list: list[str], local_path: str | None = None, is_local: bool = True
    ) -> pd.DataFrame:
        kwargs: dict[str, Any] = {"code_list": code_list, "is_local": is_local}
        if local_path is not None:
            kwargs["local_path"] = local_path
        result = await self._call_actor("get_kzz_call", **kwargs)
        return pd.DataFrame(result) if result else pd.DataFrame()

    async def get_kzz_put(
        self, code_list: list[str], local_path: str | None = None, is_local: bool = True
    ) -> pd.DataFrame:
        kwargs: dict[str, Any] = {"code_list": code_list, "is_local": is_local}
        if local_path is not None:
            kwargs["local_path"] = local_path
        result = await self._call_actor("get_kzz_put", **kwargs)
        return pd.DataFrame(result) if result else pd.DataFrame()

    async def get_kzz_put_call_item(
        self, code_list: list[str], local_path: str | None = None, is_local: bool = True
    ) -> pd.DataFrame:
        kwargs: dict[str, Any] = {"code_list": code_list, "is_local": is_local}
        if local_path is not None:
            kwargs["local_path"] = local_path
        result = await self._call_actor("get_kzz_put_call_item", **kwargs)
        return pd.DataFrame(result) if result else pd.DataFrame()

    async def get_kzz_put_explanation(
        self, code_list: list[str], local_path: str | None = None, is_local: bool = True
    ) -> pd.DataFrame:
        kwargs: dict[str, Any] = {"code_list": code_list, "is_local": is_local}
        if local_path is not None:
            kwargs["local_path"] = local_path
        result = await self._call_actor("get_kzz_put_explanation", **kwargs)
        return pd.DataFrame(result) if result else pd.DataFrame()

    async def get_kzz_call_explanation(
        self, code_list: list[str], local_path: str | None = None, is_local: bool = True
    ) -> pd.DataFrame:
        kwargs: dict[str, Any] = {"code_list": code_list, "is_local": is_local}
        if local_path is not None:
            kwargs["local_path"] = local_path
        result = await self._call_actor("get_kzz_call_explanation", **kwargs)
        return pd.DataFrame(result) if result else pd.DataFrame()

    async def get_kzz_suspend(
        self, code_list: list[str], local_path: str | None = None, is_local: bool = True
    ) -> pd.DataFrame:
        kwargs: dict[str, Any] = {"code_list": code_list, "is_local": is_local}
        if local_path is not None:
            kwargs["local_path"] = local_path
        result = await self._call_actor("get_kzz_suspend", **kwargs)
        return pd.DataFrame(result) if result else pd.DataFrame()

    async def get_etf_pcf(
        self,
        code_list: list[str],
        date: int | None = None,
    ) -> pd.DataFrame:
        """ETF PCF 申赎清单

        Args:
            code_list: ETF 代码列表
            date: 日期

        Returns:
            DataFrame: ETF PCF 数据
        """
        kwargs: dict[str, Any] = {"code_list": code_list}
        if date is not None:
            kwargs["date"] = date

        result = await self._call_actor("get_etf_pcf", **kwargs)
        return pd.DataFrame(result) if result else pd.DataFrame()

    async def get_fund_share(
        self,
        code_list: list[str],
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> pd.DataFrame:
        """基金份额

        Args:
            code_list: 基金代码列表
            begin_date: 开始日期
            end_date: 结束日期

        Returns:
            DataFrame: 基金份额数据
        """
        kwargs: dict[str, Any] = {"code_list": code_list}
        if begin_date is not None:
            kwargs["begin_date"] = begin_date
        if end_date is not None:
            kwargs["end_date"] = end_date

        result = await self._call_actor("get_fund_share", **kwargs)
        return pd.DataFrame(result) if result else pd.DataFrame()

    async def get_fund_iopv(
        self,
        code_list: list[str],
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> pd.DataFrame:
        """基金 IOPV

        Args:
            code_list: 基金代码列表
            begin_date: 开始日期
            end_date: 结束日期

        Returns:
            DataFrame: 基金 IOPV 数据
        """
        kwargs: dict[str, Any] = {"code_list": code_list}
        if begin_date is not None:
            kwargs["begin_date"] = begin_date
        if end_date is not None:
            kwargs["end_date"] = end_date

        result = await self._call_actor("get_fund_iopv", **kwargs)
        return pd.DataFrame(result) if result else pd.DataFrame()

    async def get_index_constituent(
        self,
        index_code: str,
        date: int | None = None,
    ) -> pd.DataFrame:
        """指数成分股

        Args:
            index_code: 指数代码
            date: 日期

        Returns:
            DataFrame: 指数成分股数据
        """
        kwargs: dict[str, Any] = {"index_code": index_code}
        if date is not None:
            kwargs["date"] = date

        result = await self._call_actor("get_index_constituent", **kwargs)
        return pd.DataFrame(result) if result else pd.DataFrame()

    async def get_index_weight(
        self,
        index_code: str,
        date: int | None = None,
    ) -> pd.DataFrame:
        """指数权重

        Args:
            index_code: 指数代码
            date: 日期

        Returns:
            DataFrame: 指数权重数据
        """
        kwargs: dict[str, Any] = {"index_code": index_code}
        if date is not None:
            kwargs["date"] = date

        result = await self._call_actor("get_index_weight", **kwargs)
        return pd.DataFrame(result) if result else pd.DataFrame()

    async def get_treasury_yield(
        self,
        begin_date: int | None = None,
        end_date: int | None = None,
    ) -> pd.DataFrame:
        """国债收益率

        Args:
            begin_date: 开始日期
            end_date: 结束日期

        Returns:
            DataFrame: 国债收益率数据
        """
        kwargs: dict[str, Any] = {}
        if begin_date is not None:
            kwargs["begin_date"] = begin_date
        if end_date is not None:
            kwargs["end_date"] = end_date

        result = await self._call_actor("get_treasury_yield", **kwargs)
        return pd.DataFrame(result) if result else pd.DataFrame()

    # ==================== 生命周期管理 ====================

    async def shutdown(self) -> None:
        """关闭 Adapter"""
        await self.stop()
        self._actor_available = False
        self._initialized = False

        # 清理挂起的 Future（防止内存泄漏）
        await self.cleanup_pending_futures()

        logger.info("[AmazingData/Dask] 已关闭")


__all__ = ["AmazingDataDaskAdapter"]
