# deepsearch/trader/core/event/bus.py
"""
双总线封装：
- CoreBus：零线程池、零系统 TIMER，专供超低延迟链路。
- AuxBus ：开启线程池 + 多周期调度，用于心跳、风控、日志等后台任务。
"""
from trader.core.event.engine import EventEngine


class CoreBus(EventEngine):
    """行情→策略→下单的极速通道（无线程池，无系统 TIMER）"""

    def __init__(self) -> None:
        super().__init__(timer_interval=0)  # 关闭默认 TIMER
        self._thread_pool._max_workers = 0  # type: ignore[attr-defined]
        self._thread_pool.shutdown(wait=False)  # 不再接受异步任务


class AuxBus(EventEngine):
    """后台业务总线"""

    def __init__(self, timer_interval: float = 1.0) -> None:
        super().__init__(timer_interval=timer_interval)
