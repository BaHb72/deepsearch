# deepsearch/trader/core/event/bus.py
"""
双总线封装
- CoreBus：零线程池、零系统 TIMER，专供超低延迟链路。
- AuxBus ：带线程池 + 周期调度，用于心跳 / 风控 / 日志等后台任务。
"""
from __future__ import annotations

import os

from src.trader.core.event.engine import EventEngine


class CoreBus(EventEngine):
    """行情 → 策略 → 下单极速通道（禁止异步处理器）"""

    def __init__(self) -> None:
        # timer_interval = 0 代表取消默认 1 s TIMER
        super().__init__(timer_interval=0, max_workers=0)

    # 硬禁止异步处理器
    def _get_executor(self):
        raise RuntimeError("CoreBus 禁止 async_handler；请走 AuxBus")


class AuxBus(EventEngine):
    """后台业务总线（心跳 / 风控 / Persist 等）"""

    def __init__(self, timer_interval: float = 1.0, max_workers: int | None = None) -> None:
        if max_workers is None:
            max_workers = min(32, (os.cpu_count() or 1) * 2)
        super().__init__(timer_interval=timer_interval, max_workers=max_workers)
