# deepsearch/trader/core/gateway/base.py
from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import threading
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
    DISCONNECTED = 0
    CONNECTING = 1
    CONNECTED = 2
    RECONNECTING = 3


class BaseGateway(ABC):
    """
    抽象网关基类

    - 行情/委托/成交 → CoreBus    (低延迟)
    - 心跳、日志、风控等 → AuxBus  (后台线程池)
    """

    HEARTBEAT_RECONNECT_DELAY = 1.0  # 心跳失败后 N 秒再重连

    # ------------------------ 初始化 ------------------------
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

        # 心跳状态
        self._heartbeat_enabled = False
        self._heartbeat_interval: float | None = None
        self._heartbeat_task_id: int | None = None
        self._heartbeat_lock = threading.Lock()

        # 重连互斥
        self._reconnecting = False
        self._reconnect_lock = threading.Lock()

        # 专用后台线程池（避免调用 AuxBus 私有接口）
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=2, thread_name_prefix=f"{gateway_name}-bg"
        )

        self.logger.info("网关 [%s] 初始化完成", gateway_name)

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
        self.logger.error(err); self._publish(EVENT_ERROR, err)

    def write_log(self, msg: str, level: int = logging.INFO) -> None:
        self.logger.log(level, msg)

    # -------------------- 心跳接口 --------------------
    def start_heartbeat(self, interval: float = 5.0) -> None:
        """
        开启或修改心跳。重复调用即为调整周期。
        若 AuxBus 抛异常，则恢复上一状态并向上层抛出。
        """
        interval = max(0.1, interval)

        try:
            if self._heartbeat_task_id is None:
                self._heartbeat_task_id = self.aux_bus.add_periodic(
                    interval=interval,
                    handler=self._heartbeat_task,
                    event_type=f"HEARTBEAT@{self.gateway_name}",
                    async_handler=False,  # 已在 AuxBus 线程
                    priority=-1,
                )
                self.write_log(f"心跳已启动，间隔={interval}s")
            else:
                self.aux_bus.update_periodic(self._heartbeat_task_id, new_interval=interval)
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
        """向后兼容老 UI"""
        self.start_heartbeat(new_interval)

    def stop_heartbeat(self) -> None:
        with self._heartbeat_lock:
            if self._heartbeat_task_id is not None:
                self.aux_bus.cancel_periodic(self._heartbeat_task_id)
                self._heartbeat_task_id = None
            self._heartbeat_enabled = False
        self.write_log("心跳已停止")

    # ---------------- 内部心跳任务 ----------------
    def _heartbeat_task(self, _evt: Event) -> None:
        if not self._heartbeat_enabled or not self._heartbeat_lock.acquire(blocking=False):
            return

        try:
            self.heartbeat()  # 子类实现，抛异常即视为断线
        except Exception as exc:  # noqa: BLE001
            self.write_log(f"心跳异常: {exc}; 尝试重连", level=logging.ERROR)
            self._schedule_reconnect()
        finally:
            self._heartbeat_lock.release()

    # ---------------- 重连逻辑 ----------------
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
            self.write_log(f"关闭连接失败: {exc}", level=logging.ERROR)

        # 在线程池里 sleep+connect，避免阻塞 AuxBus 线程
        def _do_reconnect() -> None:
            try:
                time.sleep(self.HEARTBEAT_RECONNECT_DELAY)
                self.connect()
                self.status = GatewayStatus.CONNECTED
                self.write_log("重连成功")
            except Exception as exc:  # noqa: BLE001
                self.write_log(f"重连失败: {exc}", level=logging.ERROR)
            finally:
                self._reconnecting = False

        self._executor.submit(_do_reconnect)

    # ---------------- 异步 connect ----------------
    async def connect_async(self) -> None:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self.connect)

    # ---------------- 抽象接口 ----------------
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

    def heartbeat(self) -> None:
        pass  # 子类可覆写

    # ---------------- 资源清理 ----------------
    def cleanup(self) -> None:
        self.stop_heartbeat()
        try:
            self.close()
        except Exception as exc:  # noqa: BLE001
            self.write_log(f"关闭网关异常: {exc}", level=logging.ERROR)
        self._executor.shutdown(wait=True)
