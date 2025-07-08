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
    """
    CoreBus 类的功能概述。

    CoreBus 是一个基于事件引擎的核心事件总线类。
    它继承自 EventEngine，用于处理事件分发功能并禁止异步事件处理器。
    此类主要用于需要同步事件分发的场景。

    :ivar queue_size: 队列的大小，用于限制事件队列容量。
    :type queue_size: int
    """

    def __init__(self, queue_size: int = 10_000) -> None:
        super().__init__(queue_size=queue_size, max_workers=0)  # 0 = 关闭线程池

    # 硬禁止异步处理器
    def _get_executor(self):
        raise RuntimeError("CoreBus 禁止 async_handler；请走 AuxBus")


class AuxBus(EventEngine):
    """后台业务总线（心跳 / 风控 / Persist 等）"""

    def __init__(self, queue_size: int = 10_000, max_workers: int | None = None) -> None:
        if max_workers is None:
            max_workers = min(32, (os.cpu_count() or 1) * 2)
        super().__init__(queue_size=queue_size, max_workers=max_workers)
