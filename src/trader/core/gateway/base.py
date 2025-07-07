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
    DISCONNECTED = 0
    CONNECTING = 1
    CONNECTED = 2
    RECONNECTING = 3
    CLOSED = 4


class BaseGateway(ABC):
    """
    抽象网关基类

    - 行情/委托/成交 → CoreBus    (低延迟)
    - 心跳、日志、风控等 → AuxBus  (后台线程池)
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
        self.aux_bus.add_handler(
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
