from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import threading
import time
from abc import ABC, abstractmethod
from enum import Enum

from deepsearch.event import (
    EVENT_TICK,
    EVENT_ORDER,
    EVENT_TRADE,
    EVENT_ERROR,
    EVENT_LOG,
)
from deepsearch.event.bus.bus import CompositeMessageBus
from deepsearch.event.engine import Event

LOGGER = logging.getLogger(__name__)


class GatewayStatus(Enum):
    """
    表示网关状态的枚举类。

    该枚举类用于定义不同的网关连接状态，以便在代码中清晰地描述和控制网关的状态。

    :ivar DISCONNECTED: 网关当前未连接的状态。
    :type DISCONNECTED: int
    :ivar CONNECTING: 网关正在尝试建立连接的状态。
    :type CONNECTING: int
    :ivar CONNECTED: 网关成功建立连接的状态。
    :type CONNECTED: int
    :ivar RECONNECTING: 网关尝试重新连接的状态。
    :type RECONNECTING: int
    :ivar CLOSED: 网关连接已关闭的状态。
    :type CLOSED: int
    """
    DISCONNECTED = 0
    CONNECTING = 1
    CONNECTED = 2
    RECONNECTING = 3
    CLOSED = 4


class BaseGateway(ABC):
    """
    BaseGateway 基类用于定义交易网关接口及部分基础行为。

    该类主要负责交易网关的心跳机制、生命周期管理以及事件推送等功能。
    通过继承该类可以实现具体的网关逻辑，如连接交易所、推送交易相关事件、管理订单等。

    :ivar message_bus: 消息总线，用于通信及事件处理。
    :type message_bus: CompositeMessageBus
    :ivar gateway_name: 网关名称，用于标识实例。
    :type gateway_name: str
    :ivar status: 网关当前状态，枚举类型 GatewayStatus，初始状态为 DISCONNECTED。
    :type status: GatewayStatus
    :ivar logger: 日志记录器，用于记录网关运行过程中重要的信息。
    :type logger: logging.Logger
    """

    HEARTBEAT_RECONNECT_DELAY = 1.0  # 心跳失败后 N 秒再重连
    _HB_EVENT_TYPE = "__GATEWAY_HEARTBEAT__"

    # ------------------------ 初始化 ------------------------
    def __init__(
            self,
            message_bus: CompositeMessageBus,
            gateway_name: str,
    ) -> None:
        """
        表示网关初始化的构造函数。

        此构造函数通过消息总线初始化网关，同时设置网关名称和初始状态。

        :param message_bus: 消息总线实例，用于通信及事件处理
        :type message_bus: CompositeMessageBus
        :param gateway_name: 网关的名称，用于标识实例
        :type gateway_name: str
        """
        self.message_bus: CompositeMessageBus = message_bus
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

        # 注册心跳处理器
        self.message_bus.subscribe(
            topic=self._HB_EVENT_TYPE,
            handler=self._heartbeat_task,
        )

    # -------------------- 事件推送 --------------------
    def _publish(self, etype: str, data=None) -> None:
        event = Event(etype, data)
        self.message_bus.publish(etype, event)

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
        """
        interval = max(0.1, interval)

        try:
            if not self._heartbeat_enabled:
                # 首次启动心跳
                self._schedule_heartbeat(interval)
                self.write_log(f"心跳已启动，间隔={interval}s")
            else:
                # 调整心跳周期
                self._schedule_heartbeat(interval)
                self.write_log(f"心跳周期已调整为 {interval}s")

            self._heartbeat_enabled = True
            self._heartbeat_interval = interval

        except Exception as exc:  # noqa: BLE001
            # 回滚状态
            self._heartbeat_enabled = False
            self._heartbeat_task_id = None
            self.write_log(f"启动/调整心跳失败: {exc}", level=logging.ERROR)
            raise

    def _schedule_heartbeat(self, interval: float) -> None:
        """调度心跳任务"""

        def heartbeat_loop():
            while self._heartbeat_enabled:
                try:
                    time.sleep(interval)
                    if self._heartbeat_enabled:
                        self.message_bus.publish(self._HB_EVENT_TYPE, None)
                except Exception as exc:
                    self.write_log(f"心跳调度失败: {exc}", level=logging.ERROR)
                    break

        # 提交心跳任务到线程池
        self._executor.submit(heartbeat_loop)

    def update_heartbeat_interval(self, new_interval: float) -> None:
        if not self._heartbeat_enabled:
            raise RuntimeError("心跳未启动，无法调整周期")
        self.start_heartbeat(new_interval)

    def stop_heartbeat(self) -> None:
        if not self._heartbeat_enabled:
            return
        try:
            self._heartbeat_enabled = False
            self.write_log("心跳已停止")
        finally:
            self._heartbeat_enabled = False
            self._heartbeat_task_id = None
            self._heartbeat_interval = None

    # ---------------- 心跳任务 ----------------
    def _heartbeat_task(self, _evt) -> None:  # noqa: D401
        """收到心跳事件时触发"""
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
        """在同步或异步环境中执行 ``connect_async``。

                当检测到当前线程没有运行中的事件循环时，使用 ``asyncio.run``
                直接运行 :meth:`connect_async`。
                若已处于事件循环内，则通过 ``asyncio.create_task`` 调度执行。
                """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(self.connect_async())
        else:
            loop.create_task(self.connect_async())

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