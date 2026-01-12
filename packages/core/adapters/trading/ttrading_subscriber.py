"""T-Trading 订阅适配器。

桥接 TTradingService 与订阅系统，实现:
- 策略激活时自动订阅实时数据
- 收到行情时自动检查信号触发
- 保持原有接口向后兼容
"""

import asyncio
import logging
from typing import TYPE_CHECKING, Dict, Optional, Set

from core.ports.market_data.subscription import SubscriberPriority

if TYPE_CHECKING:
    from core.ports.market_data.l2_pinned_buffer import L2Snapshot, L2Tick

logger = logging.getLogger(__name__)


class TTradingSubscriber:
    """
    T-Trading 订阅适配器

    实现 MarketDataSubscriber 协议，桥接 TTradingService

    职责:
    - 收到 tick 数据时调用策略的 check_signals
    - 管理策略与股票代码的订阅关系
    """

    def __init__(self):
        self._active_codes: Set[str] = set()  # 当前订阅的股票
        self._code_strategies: Dict[str, Set[str]] = {}  # code → strategy_ids
        self._last_prices: Dict[str, float] = {}  # code → last_price
        self._stats = {
            "ticks_received": 0,
            "signals_checked": 0,
            "signals_triggered": 0,
        }

    # ==================== MarketDataSubscriber 协议实现 ====================

    @property
    def subscriber_id(self) -> str:
        return "ttrading_realtime_monitor"

    @property
    def priority(self) -> SubscriberPriority:
        return SubscriberPriority.HIGH  # 做T需要最低延迟 → RAM

    @property
    def module_name(self) -> str:
        return "t_trading"

    def on_tick(self, code: str, tick: "L2Tick") -> None:
        """收到逐笔数据"""
        self._stats["ticks_received"] += 1
        self._last_prices[code] = tick.price

        # 异步检查信号
        asyncio.create_task(self._check_strategies_for_code(code, tick.price))

    def on_snapshot(self, code: str, snapshot: "L2Snapshot") -> None:
        """收到快照数据"""
        self._last_prices[code] = snapshot.last
        asyncio.create_task(self._check_strategies_for_code(code, snapshot.last))

    def on_error(self, code: str, error: Exception) -> None:
        """错误回调"""
        logger.warning(f"TTradingSubscriber 收到错误: {code} - {error}")

    def on_subscription_status(self, code: str, subscribed: bool) -> None:
        """订阅状态变更"""
        if subscribed:
            self._active_codes.add(code)
            logger.info(f"TTradingSubscriber 已订阅: {code}")
        else:
            self._active_codes.discard(code)
            logger.info(f"TTradingSubscriber 已取消订阅: {code}")

    # ==================== 策略管理 ====================

    def register_strategy(self, strategy_id: str, symbol: str) -> None:
        """注册策略 (策略激活时调用)"""
        if symbol not in self._code_strategies:
            self._code_strategies[symbol] = set()
        self._code_strategies[symbol].add(strategy_id)
        logger.info(f"TTradingSubscriber 注册策略: {strategy_id} → {symbol}")

    def unregister_strategy(self, strategy_id: str, symbol: str) -> None:
        """注销策略 (策略暂停/删除时调用)"""
        if symbol in self._code_strategies:
            self._code_strategies[symbol].discard(strategy_id)
            if not self._code_strategies[symbol]:
                del self._code_strategies[symbol]
        logger.info(f"TTradingSubscriber 注销策略: {strategy_id} → {symbol}")

    def get_strategies_for_code(self, code: str) -> Set[str]:
        """获取股票关联的策略"""
        return self._code_strategies.get(code, set()).copy()

    def get_last_price(self, code: str) -> Optional[float]:
        """获取最新价格"""
        return self._last_prices.get(code)

    def get_stats(self) -> Dict:
        """获取统计"""
        return {
            **self._stats,
            "active_codes": len(self._active_codes),
            "tracked_strategies": sum(len(s) for s in self._code_strategies.values()),
        }

    # ==================== 内部方法 ====================

    async def _check_strategies_for_code(self, code: str, current_price: float) -> None:
        """检查该股票关联的所有策略"""
        strategy_ids = self._code_strategies.get(code, set())
        if not strategy_ids:
            return

        self._stats["signals_checked"] += len(strategy_ids)

        try:
            from core.infrastructure.trading.ttrading_service import get_ttrading_service

            service = get_ttrading_service()

            for strategy_id in strategy_ids:
                try:
                    triggered = await service.check_signals(strategy_id, current_price)
                    if triggered:
                        self._stats["signals_triggered"] += len(triggered)
                except Exception as e:
                    logger.error(f"检查策略信号失败: {strategy_id} - {e}")
        except Exception as e:
            logger.error(f"获取 TTradingService 失败: {e}")


# 全局单例
_ttrading_subscriber: Optional[TTradingSubscriber] = None


def get_ttrading_subscriber() -> TTradingSubscriber:
    """获取 TTradingSubscriber 单例"""
    global _ttrading_subscriber
    if _ttrading_subscriber is None:
        _ttrading_subscriber = TTradingSubscriber()
    return _ttrading_subscriber


__all__ = ["TTradingSubscriber", "get_ttrading_subscriber"]
