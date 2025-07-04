# deepsearch/trader/core/gateway/base.py
from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from enum import Enum

from trader.core.constant import (
    EVENT_TICK,
    EVENT_ORDER,
    EVENT_TRADE,
    EVENT_ERROR,
)
from trader.core.event.bus import CoreBus, AuxBus
from trader.core.event.engine import Event
from trader.core.logger import get_logger


class GatewayStatus(Enum):
    """网关连接状态。"""
    DISCONNECTED = 0
    CONNECTING = 1
    CONNECTED = 2
    RECONNECTING = 3


class BaseGateway(ABC):
    """
    抽象网关基类：
    - 行情/委托/成交事件 → CoreBus （低延迟）
    - 心跳、日志、风控等后台任务 → AuxBus
    """

    HEARTBEAT_RECONNECT_DELAY = 1.0  # 心跳失败后重连等待秒数

    # ------------------------------------------------------------------
    # 初始化
    # ------------------------------------------------------------------
    def __init__(
            self,
            core_bus: CoreBus,
            aux_bus: AuxBus,
            gateway_name: str,
    ) -> None:
        self.core_bus = core_bus
        self.aux_bus = aux_bus
        self.gateway_name = gateway_name

        self.status: GatewayStatus = GatewayStatus.DISCONNECTED
        self.logger = get_logger(service=gateway_name)

        # 心跳控制
        self._heartbeat_enabled: bool = False
        self._heartbeat_interval: float | None = None

        self.logger.info(f"网关 [{gateway_name}] 初始化完成")

    # ------------------------------------------------------------------
    # 事件推送（走 CoreBus）
    # ------------------------------------------------------------------
    def _publish(self, event_type: str, data=None) -> None:
        self.core_bus.put(Event(event_type, data))

    def on_tick(self, tick) -> None:
        self._publish(EVENT_TICK, tick)

    def on_order(self, order) -> None:
        self._publish(EVENT_ORDER, order)

    def on_trade(self, trade) -> None:
        self._publish(EVENT_TRADE, trade)

    def on_error(self, err) -> None:
        self.logger.error(err)
        self._publish(EVENT_ERROR, err)

    def write_log(self, msg: str, level: int = logging.INFO) -> None:
        self.logger.log(level, msg)

    # ------------------------------------------------------------------
    # 心跳调度（走 AuxBus）
    # ------------------------------------------------------------------
    def start_heartbeat(self, interval: float = 5.0) -> None:
        """启用心跳；已有则忽略重复调用。"""
        if self._heartbeat_enabled:
            return

        self._heartbeat_interval = max(0.1, interval)
        self._heartbeat_enabled = True

        # 注册定时任务（异步线程池执行）
        self.aux_bus.add_periodic(
            interval=self._heartbeat_interval,
            handler=self._heartbeat_task,
            event_type=f"HEARTBEAT@{self.gateway_name}",
            async_handler=True,
            priority=-1,  # 优先级最低
        )
        self.write_log(f"心跳已启动，间隔={self._heartbeat_interval}s")

    def stop_heartbeat(self) -> None:
        """关闭心跳；实际由 _heartbeat_task 内部判断退出。"""
        self._heartbeat_enabled = False
        self.write_log("心跳已停止")

    # ---------------- 内部心跳任务 ----------------
    def _heartbeat_task(self, _evt: Event) -> None:
        if not self._heartbeat_enabled:
            return

        try:
            self.heartbeat()  # 由子类实现；若异常则触发重连
        except Exception as exc:  # noqa: BLE001
            self.write_log(f"心跳异常: {exc}; 准备重连", level=logging.ERROR)
            self.status = GatewayStatus.RECONNECTING

            try:
                self.close()
            except Exception as close_err:  # noqa: BLE001
                self.write_log(f"关闭连接异常: {close_err}", level=logging.WARNING)

            time.sleep(self.HEARTBEAT_RECONNECT_DELAY)

            try:
                self.connect()
            except Exception as conn_err:  # noqa: BLE001
                self.write_log(f"重连失败: {conn_err}", level=logging.ERROR)

    # ------------------------------------------------------------------
    # 抽象接口（子类实现）
    # ------------------------------------------------------------------
    @abstractmethod
    def connect(self) -> None:
        ...

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

    # 可选：子类若无需心跳，可不覆写
    def heartbeat(self) -> None:
        """心跳检测（子类可覆盖）。"""
        pass
