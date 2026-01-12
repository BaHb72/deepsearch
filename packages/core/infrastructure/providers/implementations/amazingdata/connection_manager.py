"""Connection and session orchestration for AmazingDataProvider."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.infrastructure.providers.interfaces.base import DataProviderError
from core.infrastructure.providers.interfaces.capabilities import DataCapability
from core.utils.network.connection_pool import ConnectionPool, PoolConfig

from .distributed_session import DistributedSessionManager
from .helpers import async_retry
from .logging_utils import log_debug, log_error, log_info, log_warning
from .session_manager import AmazingDataSessionManager

if TYPE_CHECKING:
    from .amazingdata import AmazingDataProvider


class AmazingDataConnectionManager:
    """Manage AmazingData SDK connection lifecycle (login/logout, heartbeat, reconnect)."""

    def __init__(self, owner: "AmazingDataProvider") -> None:
        self._owner = owner
        self._session_manager = AmazingDataSessionManager(owner)
        self._distributed_session: DistributedSessionManager | None = None
        self._pool: ConnectionPool | None = None
        self._pool_config = PoolConfig(
            min_size=2,
            max_size=10,
            idle_timeout=300,
            validation_interval=60,
            acquire_timeout=5.0,
        )
        self._reconnect_task: asyncio.Task[None] | None = None
        self._heartbeat_task: asyncio.Task[None] | None = None
        self._login_lock: asyncio.Lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Pool management
    # ------------------------------------------------------------------
    async def initialize(self) -> None:
        if self._owner._degraded_mode:
            log_warning(
                "AmazingData 处于降级模式，跳过真实初始化流程",
                action="initialize",
                metadata={"mode": "degraded"},
            )
            self._owner._connected = False
            return

        # Initialize distributed session manager if enabled
        if getattr(self._owner.config, "distributed_session_enabled", True):
            redis_url = getattr(self._owner.config, "redis_url", "redis://localhost:6379")
            self._distributed_session = DistributedSessionManager(redis_url=redis_url)
            await self._distributed_session.initialize()
            log_info(
                "分布式会话管理器已初始化",
                action="initialize",
                metadata={"redis_url": redis_url},
            )

        self._pool = ConnectionPool(
            factory=self._owner._create_connection,
            config=self._pool_config,
            validator=self._owner._validate_connection,
            closer=self._owner._close_connection,
        )
        await self._pool.initialize()
        await self.login()

        if self._owner.config.heartbeat_interval > 0:
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        if self._owner.config.auto_reconnect:
            self._reconnect_task = asyncio.create_task(self._reconnect_loop())

        log_info("AmazingData 初始化完成", action="initialize")

    async def shutdown(self) -> None:
        log_info("停止 AmazingData 数据源", action="stop")

        if self._owner._degraded_mode:
            log_warning(
                "AmazingData 处于降级模式，跳过停止操作",
                action="stop",
                metadata={"mode": "degraded"},
            )
            return

        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
            finally:
                self._heartbeat_task = None
        if self._reconnect_task:
            self._reconnect_task.cancel()
            try:
                await self._reconnect_task
            except asyncio.CancelledError:
                pass
            finally:
                self._reconnect_task = None

        if self._pool:
            await self._pool.close()
            self._pool = None

        # Shutdown distributed session manager
        if self._distributed_session:
            await self._distributed_session.shutdown()
            self._distributed_session = None

        await self.logout()

    # ------------------------------------------------------------------
    # Login / logout
    # ------------------------------------------------------------------
    async def login(self) -> bool:
        """Perform login with distributed coordination if enabled."""
        async with self._login_lock:
            if self._owner._connected:
                log_debug("登录检查：已连接，跳过", action="login")
                return True

            # Use distributed session if available
            if self._distributed_session is not None:
                log_info("使用分布式会话管理器协调登录", action="login")
                return await self._distributed_session.ensure_login(
                    login_callback=self._owner._perform_login,
                )

            # Fallback to local login
            return await self._login_with_retry()

    @async_retry(max_attempts=3, backoff_base=2)
    async def _login_with_retry(self) -> bool:
        return await self._login_internal()

    async def _login_internal(self) -> bool:
        lock = await self._session_manager.acquire_login_file_lock()
        if lock is None:
            raise DataProviderError("AmazingData login is locked by another worker")

        try:
            return await self._owner._perform_login()
        finally:
            await self._session_manager.release_login_file_lock()

    async def logout(self) -> None:
        await self._owner._perform_logout()

    # ------------------------------------------------------------------
    # Heartbeat & reconnect
    # ------------------------------------------------------------------
    async def _heartbeat_loop(self) -> None:
        consecutive_failures = 0
        max_consecutive_failures = 3

        while True:
            try:
                await asyncio.sleep(self._owner.config.heartbeat_interval)

                if not self._owner._connected:
                    continue

                try:
                    await self._owner._perform_heartbeat()
                    consecutive_failures = 0
                except asyncio.TimeoutError:
                    consecutive_failures += 1
                    log_warning(
                        f"AmazingData heartbeat timeout ({consecutive_failures}/{max_consecutive_failures})",
                        action="heartbeat",
                    )
                    if consecutive_failures >= max_consecutive_failures:
                        log_error(
                            f"AmazingData heartbeat failed {consecutive_failures} times, disconnecting",
                            action="heartbeat",
                        )
                        self._owner._connected = False
                        consecutive_failures = 0
                except Exception as exc:  # noqa: BLE001
                    consecutive_failures += 1
                    if consecutive_failures >= max_consecutive_failures:
                        log_error(
                            f"AmazingData heartbeat failed {consecutive_failures} times",
                            action="heartbeat",
                            metadata={"error": repr(exc)},
                        )
                        self._owner._connected = False
                        consecutive_failures = 0
            except asyncio.CancelledError:
                break
            except Exception as exc:  # noqa: BLE001
                log_error(f"心跳循环异常: {exc}", action="heartbeat")

    async def _reconnect_loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(self._owner.config.reconnect_interval)

                if self._owner._connected:
                    self._owner._stats["reconnect_attempts"] = 0
                    continue

                attempts = self._owner._increment_stat("reconnect_attempts")
                log_info("AmazingData reconnecting | attempts={}".format(attempts))
                try:
                    reconnect_success = await self.login()
                except DataProviderError as exc:
                    log_error(
                        "AmazingData reconnect attempt failed: {}".format(exc),
                        action="reconnect",
                    )
                    reconnect_success = False

                if reconnect_success:
                    log_info("AmazingData reconnected | attempts={}".format(attempts))
                    self._owner._stats["reconnect_attempts"] = 0
                    if self._owner._subscriptions:
                        await self._owner._restore_subscriptions()
                else:
                    log_warning("重连失败，稍后重试...", action="reconnect")
            except asyncio.CancelledError:
                break
            except Exception as exc:  # noqa: BLE001
                log_error(f"重连循环异常: {exc}", action="reconnect")

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------
    async def ensure_session(self) -> bool:
        if self._owner._degraded_mode:
            log_warning("AmazingData 处于降级模式，不执行会话管理", action="session")
            return False

        if self._pool is None:
            await self.initialize()
            return self._owner._connected

        if self._owner._connected:
            return True

        await self.login()
        return self._owner._connected

    def get_capabilities(self) -> set[DataCapability]:
        return {
            DataCapability.REALTIME_QUOTE,
            DataCapability.REALTIME_QUOTES,
            DataCapability.KLINE_DATA,
            DataCapability.MINUTE_DATA,
            DataCapability.TICK_DATA,
            DataCapability.STOCK_LIST,
            DataCapability.FINANCIAL_DATA,
            DataCapability.KEY_INDICATORS,
            DataCapability.SHAREHOLDER_INFO,
            DataCapability.DRAGON_TIGER,
            DataCapability.BLOCK_TRADE,
            DataCapability.MARGIN_TRADING,
            DataCapability.NORTH_FLOW,
            DataCapability.TRADING_CALENDAR,
            DataCapability.ADJUSTMENT_FACTOR,
            DataCapability.STOCK_INFO,
        }
