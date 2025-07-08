# src/trader/core/gateway/base.py
from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import threading
import time
from abc import ABC, abstractmethod
from enum import Enum

from src.trader.core.constant import (
    EVENT_TICK,
    EVENT_ORDER,
    EVENT_TRADE,
    EVENT_ERROR,
    EVENT_LOG,
)
from src.trader.core.event.bus import CoreBus, AuxBus
from src.trader.core.event.engine import Event

LOGGER = logging.getLogger(__name__)


class GatewayStatus(Enum):
    """
    表示网关状态的枚举类。

    此类定义了网关连接的各种可能状态，用于表示连接的生命周期及其状态。

    :ivar DISCONNECTED: 表示网关未连接状态。
    :type DISCONNECTED: int
    :ivar CONNECTING: 表示网关正在尝试连接中的状态。
    :type CONNECTING: int
    :ivar CONNECTED: 表示网关已成功连接的状态。
    :type CONNECTED: int
    :ivar RECONNECTING: 表示网关尝试重新连接的状态。
    :type RECONNECTING: int
    :ivar CLOSED: 表示网关已关闭的状态。
    :type CLOSED: int
    """
    DISCONNECTED = 0
    CONNECTING = 1
    CONNECTED = 2
    RECONNECTING = 3
    CLOSED = 4


class BaseGateway(ABC):
    """
    BaseGateway 是一个负责处理网关初始化、心跳管理、事件推送和连接生命周期的抽象基类。

    此类旨在为网关通信提供一个通用的框架，包括事件处理、异步任务管理、可靠的心跳机制以及
    支持重连逻辑的默认实现。此外，此框架允许子类覆写关键抽象方法以实现自定义行为。

    :ivar core_bus: 核心总线实例，负责事件的传递和处理。
    :type core_bus: CoreBus
    :ivar aux_bus: 辅助总线实例，提供事件和扩展功能的支持。
    :type aux_bus: AuxBus
    :ivar gateway_name: 网关实例的标识名称。
    :type gateway_name: str
    :ivar status: 当前网关的状态（初始为 DISCONNECTED）。
    :type status: GatewayStatus
    :ivar logger: 用于记录网关相关日志的日志记录器实例。
    :type logger: logging.Logger
    """

    HEARTBEAT_RECONNECT_DELAY = 1.0  # 心跳失败后 N 秒再重连
    _HB_EVENT_TYPE = "__GATEWAY_HEARTBEAT__"

    # ------------------------ 初始化 ------------------------
    def __init__(
            self,
            core_bus: CoreBus,
            aux_bus: AuxBus,
            gateway_name: str,
    ) -> None:
        """
        表示网关初始化的构造函数。

        此构造函数通过核心总线和辅助总线初始化网关，同时设置网关名称和初始状态。

        :param core_bus: 核心总线的实例，用于通信及事件处理
        :type core_bus: CoreBus
        :param aux_bus: 辅助总线的实例，提供扩展支持及事件处理
        :type aux_bus: AuxBus
        :param gateway_name: 网关的名称，用于标识实例
        :type gateway_name: str
        """
        self.core_bus: CoreBus = core_bus
        self.aux_bus: AuxBus = aux_bus
        self.gateway_name: str = gateway_name

        self.status: GatewayStatus = GatewayStatus.DISCONNECTED
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=2, thread_name_prefix=f"{gateway_name}-bg"
        )

        self._heartbeat_enabled: bool = False
        self._heartbeat_interval: float | None = None
        self._heartbeat_task_id: int | None = None
        self._reconnecting: bool = False
        self._reconnect_lock = threading.Lock()

        self.logger = logging.getLogger(f"gateway.{gateway_name}")
        self.logger.info("网关 [%s] 初始化完成", gateway_name)

        # 注册心跳处理器（只需一次）
        self.aux_bus.register(
            event_type=self._HB_EVENT_TYPE,
            handler=self._heartbeat_task,
            async_flag=False,
        )

    # -------------------- 事件推送 --------------------
    def _publish(self, etype: str, data=None) -> None:
        self.core_bus.put(Event(etype, data))

    def on_tick(self, tick):
        self._publish(EVENT_TICK, tick)

    def on_order(self, order):
        self._publish(EVENT_ORDER, order)

    def on_trade(self, trade):
        self._publish(EVENT_TRADE, trade)

    def on_error(self, err):
        self.logger.error(err)
        self._publish(EVENT_ERROR, err)

    def write_log(self, msg: str, level: int = logging.INFO) -> None:
        self.logger.log(level, msg)
        self._publish(EVENT_LOG, msg)

    # -------------------- 心跳接口 --------------------
    def start_heartbeat(self, interval: float = 5.0) -> None:
        """
        开启或修改心跳。重复调用即为调整周期。
        若 AuxBus 抛异常，则恢复上一状态并向上层抛出。
        """
        interval = max(0.1, interval)

        try:
            if not self._heartbeat_enabled:
                # 首次启动
                self._heartbeat_task_id = self.aux_bus.add_periodic(
                    event_type=self._HB_EVENT_TYPE,
                    interval=interval,
                    priority=0,
                    async_flag=False,
                )
                self.write_log(f"心跳已启动，间隔={interval}s")
            else:
                # 仅调整周期
                assert self._heartbeat_task_id is not None
                self.aux_bus.update_periodic(
                    self._heartbeat_task_id, new_interval=interval
                )
                self.write_log(f"心跳周期已调整为 {interval}s")

            self._heartbeat_enabled = True
            self._heartbeat_interval = interval

        except Exception as exc:  # noqa: BLE001
            # 回滚状态
            self._heartbeat_enabled = False
            self._heartbeat_task_id = None
            self.write_log(f"启动/调整心跳失败: {exc}", level=logging.ERROR)
            raise

    def update_heartbeat_interval(self, new_interval: float) -> None:
        if not self._heartbeat_enabled:
            raise RuntimeError("心跳未启动，无法调整周期")
        self.start_heartbeat(new_interval)

    def stop_heartbeat(self) -> None:
        if not self._heartbeat_enabled:
            return
        try:
            assert self._heartbeat_task_id is not None
            self.aux_bus.cancel_periodic(self._heartbeat_task_id)
            self.write_log("心跳已停止")
        finally:
            self._heartbeat_enabled = False
            self._heartbeat_task_id = None
            self._heartbeat_interval = None

    # ---------------- 心跳任务 ----------------
    def _heartbeat_task(self, _evt: Event) -> None:  # noqa: D401
        """收到 _HEARTBEAT 事件时触发"""
        try:
            self.heartbeat()
        except Exception as exc:  # noqa: BLE001
            self.write_log(f"心跳检测失败: {exc}", level=logging.ERROR)
            # 失败后计划重连
            self._schedule_reconnect()

    def _schedule_reconnect(self) -> None:
        if self._reconnecting:
            return
        with self._reconnect_lock:
            if self._reconnecting:
                return
            self._reconnecting = True

        self.status = GatewayStatus.RECONNECTING

        try:
            self.close()
        except Exception as exc:  # noqa: BLE001
            self.write_log(f"主动关闭连接失败: {exc}", level=logging.ERROR)

        # 交给后台线程异步重连，避免阻塞总线
        def _do_reconnect() -> None:
            time.sleep(self.HEARTBEAT_RECONNECT_DELAY)
            try:
                self.connect()
            except Exception as exc:  # noqa: BLE001
                self.write_log(f"重连失败: {exc}", level=logging.ERROR)
            finally:
                self._reconnecting = False

        self._executor.submit(_do_reconnect)

    # ---------------- 连接生命周期抽象 ----------------
    @abstractmethod
    async def connect_async(self) -> None:
        ...

    def connect(self) -> None:
        asyncio.run(self.connect_async())

    @abstractmethod
    def close(self) -> None:
        ...

    @abstractmethod
    def subscribe(self, symbol: str) -> None:
        ...

    @abstractmethod
    def send_order(self, order_req) -> str:
        ...

    @abstractmethod
    def cancel_order(self, order_id: str) -> None:
        ...

    def heartbeat(self) -> None:
        """子类可覆写：检查通道连通性 / 发送 ping。"""
        pass

    # ---------------- 资源清理 ----------------
    def cleanup(self) -> None:
        self.stop_heartbeat()
        try:
            self.close()
        except Exception as exc:  # noqa: BLE001
            self.write_log(f"关闭网关异常: {exc}", level=logging.ERROR)
        self._executor.shutdown(wait=True)
