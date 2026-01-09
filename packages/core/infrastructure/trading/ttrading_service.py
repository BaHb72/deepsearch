"""
T-Trading 日内做T策略服务

提供策略的 CRUD 操作、价格监控和通知发送功能。
策略数据存储在 Redis 中。
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Callable, Optional

import redis.asyncio as aioredis
from loguru import logger
from pydantic import BaseModel, Field
from typing_extensions import Literal

if TYPE_CHECKING:
    from redis.asyncio import Redis as AsyncRedis


class TradingSignal(BaseModel):
    """单个买卖点条件"""

    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    signal_type: Literal["buy", "sell"] = Field(..., description="买入/卖出")
    trigger_price: float = Field(..., description="触发价格")
    position_ratio: float = Field(..., ge=0, le=100, description="仓位比例 (0-100%)")
    enabled: bool = Field(default=True, description="是否启用")
    triggered: bool = Field(default=False, description="是否已触发")
    triggered_at: Optional[datetime] = Field(default=None, description="触发时间")


class TTradingStrategy(BaseModel):
    """日内做T策略"""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str = Field(..., min_length=1, description="股票代码")
    name: str = Field(..., min_length=1, description="策略名称")
    signals: list[TradingSignal] = Field(default_factory=list, description="买卖点列表")
    notify_enabled: bool = Field(default=True, description="是否发送通知")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    status: Literal["active", "paused", "completed"] = Field(
        default="active", description="策略状态"
    )


# Redis 客户端单例
_redis_client: Optional["AsyncRedis"] = None


async def _get_redis_client() -> "AsyncRedis":
    """获取 Redis 客户端单例"""
    global _redis_client
    if _redis_client is None:
        # 尝试从配置获取 Redis 连接信息，默认使用本地连接
        try:
            from core.config import get_config

            config = get_config()
            cache_config = getattr(config, "database", None)
            if cache_config:
                cache_db = getattr(cache_config, "cache", None)
                if cache_db:
                    host = getattr(cache_db, "host", "localhost")
                    port = getattr(cache_db, "port", 6379)
                    password = getattr(cache_db, "password", None)
                    db = getattr(cache_db, "db", 0)
                    _redis_client = aioredis.from_url(
                        f"redis://{host}:{port}/{db}",
                        password=password,
                        encoding="utf-8",
                        decode_responses=True,
                    )
                    return _redis_client
        except Exception as e:
            logger.debug(f"从配置加载 Redis 连接失败，使用默认配置: {e}")

        # 默认连接
        _redis_client = aioredis.from_url(
            "redis://localhost:6379/0",
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis_client


class TTradingService:
    """日内做T策略服务"""

    REDIS_KEY_PREFIX = "ttrading:strategy:"
    REDIS_LIST_KEY = "ttrading:strategies"

    def __init__(
        self,
        notification_callback: Optional[Callable[[str, str], Any]] = None,
    ) -> None:
        self._logger = logger.bind(component="TTradingService")
        self._notification_callback = notification_callback
        self._monitor_task: Optional[asyncio.Task] = None
        self._running = False

    async def _get_redis(self) -> "AsyncRedis":
        """获取 Redis 客户端"""
        return await _get_redis_client()

    def _subscribe_realtime(self, strategy_id: str, symbol: str) -> None:
        """订阅实时数据（内部使用）"""
        try:
            from core.adapters.market_data.memory_scheduler import get_memory_scheduler
            from core.adapters.market_data.subscription_manager import get_subscription_manager
            from core.adapters.trading.ttrading_subscriber import get_ttrading_subscriber

            subscriber = get_ttrading_subscriber()
            manager = get_subscription_manager()

            # 绑定调度器
            if manager._scheduler is None:
                manager.set_scheduler(get_memory_scheduler())

            # 注册策略并订阅
            subscriber.register_strategy(strategy_id, symbol)
            manager.subscribe(symbol, subscriber)

            self._logger.info(f"策略 {strategy_id} 已订阅 {symbol} 实时数据")
        except Exception as e:
            self._logger.warning(f"订阅实时数据失败 (不影响策略功能): {e}")

    def _unsubscribe_realtime(self, strategy_id: str, symbol: str) -> None:
        """取消订阅实时数据（内部使用）"""
        try:
            from core.adapters.market_data.subscription_manager import get_subscription_manager
            from core.adapters.trading.ttrading_subscriber import get_ttrading_subscriber

            subscriber = get_ttrading_subscriber()
            manager = get_subscription_manager()

            # 注销策略
            subscriber.unregister_strategy(strategy_id, symbol)

            # 如果该股票没有其他策略订阅，则取消订阅
            if not subscriber.get_strategies_for_code(symbol):
                manager.unsubscribe(symbol, subscriber)

            self._logger.info(f"策略 {strategy_id} 已取消订阅 {symbol}")
        except Exception as e:
            self._logger.warning(f"取消订阅失败 (不影响策略功能): {e}")

    # ==================== CRUD 操作 ====================

    async def create_strategy(self, strategy: TTradingStrategy) -> TTradingStrategy:
        """创建新策略"""
        redis = await self._get_redis()
        key = f"{self.REDIS_KEY_PREFIX}{strategy.id}"

        # 存储策略 JSON
        await redis.set(key, strategy.model_dump_json())  # type: ignore[attr-defined]
        # 添加到策略列表
        await redis.sadd(self.REDIS_LIST_KEY, strategy.id)

        self._logger.info(f"创建策略: {strategy.id} - {strategy.name}")

        # 自动订阅实时数据 (策略默认 active)
        if strategy.status == "active":
            self._subscribe_realtime(strategy.id, strategy.symbol)

        return strategy

    async def get_strategy(self, strategy_id: str) -> Optional[TTradingStrategy]:
        """获取策略详情"""
        redis = await self._get_redis()
        key = f"{self.REDIS_KEY_PREFIX}{strategy_id}"
        data = await redis.get(key)

        if data:
            return TTradingStrategy.model_validate_json(data)  # type: ignore[attr-defined, no-any-return]
        return None

    async def list_strategies(self) -> list[TTradingStrategy]:
        """获取所有策略列表"""
        redis = await self._get_redis()
        strategy_ids = await redis.smembers(self.REDIS_LIST_KEY)

        strategies = []
        for sid in strategy_ids:
            strategy = await self.get_strategy(sid)
            if strategy:
                strategies.append(strategy)

        # 按创建时间倒序
        strategies.sort(key=lambda s: s.created_at, reverse=True)
        return strategies

    async def update_strategy(
        self, strategy_id: str, updates: dict[str, Any]
    ) -> Optional[TTradingStrategy]:
        """更新策略"""
        strategy = await self.get_strategy(strategy_id)
        if not strategy:
            return None

        # 更新字段
        for key, value in updates.items():
            if hasattr(strategy, key) and key not in ("id", "created_at"):
                setattr(strategy, key, value)

        strategy.updated_at = datetime.now()

        redis = await self._get_redis()
        key = f"{self.REDIS_KEY_PREFIX}{strategy_id}"
        await redis.set(key, strategy.model_dump_json())  # type: ignore[attr-defined]

        self._logger.info(f"更新策略: {strategy_id}")
        return strategy

    async def delete_strategy(self, strategy_id: str) -> bool:
        """删除策略"""
        # 先获取策略信息用于取消订阅
        strategy = await self.get_strategy(strategy_id)

        redis = await self._get_redis()
        key = f"{self.REDIS_KEY_PREFIX}{strategy_id}"

        result = await redis.delete(key)
        await redis.srem(self.REDIS_LIST_KEY, strategy_id)

        if result:
            self._logger.info(f"删除策略: {strategy_id}")
            # 取消订阅实时数据
            if strategy and strategy.status == "active":
                self._unsubscribe_realtime(strategy_id, strategy.symbol)
        return bool(result)

    async def toggle_strategy(self, strategy_id: str) -> Optional[TTradingStrategy]:
        """切换策略状态 (active <-> paused)"""
        strategy = await self.get_strategy(strategy_id)
        if not strategy:
            return None

        old_status = strategy.status
        new_status = "paused" if strategy.status == "active" else "active"
        result = await self.update_strategy(strategy_id, {"status": new_status})

        # 订阅/取消订阅实时数据
        if result:
            if new_status == "active":
                self._subscribe_realtime(strategy_id, strategy.symbol)
            elif old_status == "active":
                self._unsubscribe_realtime(strategy_id, strategy.symbol)

        return result

    # ==================== 信号管理 ====================

    async def add_signal(
        self, strategy_id: str, signal: TradingSignal
    ) -> Optional[TTradingStrategy]:
        """添加买卖点信号"""
        strategy = await self.get_strategy(strategy_id)
        if not strategy:
            return None

        strategy.signals.append(signal)
        strategy.updated_at = datetime.now()

        redis = await self._get_redis()
        key = f"{self.REDIS_KEY_PREFIX}{strategy_id}"
        await redis.set(key, strategy.model_dump_json())  # type: ignore[attr-defined]

        return strategy

    async def remove_signal(self, strategy_id: str, signal_id: str) -> Optional[TTradingStrategy]:
        """移除买卖点信号"""
        strategy = await self.get_strategy(strategy_id)
        if not strategy:
            return None

        strategy.signals = [s for s in strategy.signals if s.id != signal_id]
        strategy.updated_at = datetime.now()

        redis = await self._get_redis()
        key = f"{self.REDIS_KEY_PREFIX}{strategy_id}"
        await redis.set(key, strategy.model_dump_json())  # type: ignore[attr-defined]

        return strategy

    async def update_signal(
        self, strategy_id: str, signal_id: str, updates: dict[str, Any]
    ) -> Optional[TTradingStrategy]:
        """更新买卖点信号"""
        strategy = await self.get_strategy(strategy_id)
        if not strategy:
            return None

        for signal in strategy.signals:
            if signal.id == signal_id:
                for key, value in updates.items():
                    if hasattr(signal, key) and key != "id":
                        setattr(signal, key, value)
                break

        strategy.updated_at = datetime.now()

        redis = await self._get_redis()
        key = f"{self.REDIS_KEY_PREFIX}{strategy_id}"
        await redis.set(key, strategy.model_dump_json())  # type: ignore[attr-defined]

        return strategy

    # ==================== 价格监控 ====================

    async def check_signals(self, strategy_id: str, current_price: float) -> list[TradingSignal]:
        """检查策略中的信号是否触发"""
        strategy = await self.get_strategy(strategy_id)
        if not strategy or strategy.status != "active":
            return []

        triggered_signals = []

        for signal in strategy.signals:
            if not signal.enabled or signal.triggered:
                continue

            should_trigger = False

            if signal.signal_type == "buy":
                # 买入信号：当前价格 <= 触发价格
                should_trigger = current_price <= signal.trigger_price
            else:
                # 卖出信号：当前价格 >= 触发价格
                should_trigger = current_price >= signal.trigger_price

            if should_trigger:
                signal.triggered = True
                signal.triggered_at = datetime.now()
                triggered_signals.append(signal)

                self._logger.info(
                    f"信号触发: {strategy.symbol} {signal.signal_type} "
                    f"at {current_price}, target: {signal.trigger_price}"
                )

        if triggered_signals:
            # 更新策略
            redis = await self._get_redis()
            key = f"{self.REDIS_KEY_PREFIX}{strategy_id}"
            await redis.set(key, strategy.model_dump_json())  # type: ignore[attr-defined]

            # 发送通知
            if strategy.notify_enabled and self._notification_callback:
                for signal in triggered_signals:
                    await self._send_signal_notification(strategy, signal, current_price)

        return triggered_signals

    async def _send_signal_notification(
        self,
        strategy: TTradingStrategy,
        signal: TradingSignal,
        current_price: float,
    ) -> None:
        """发送信号触发通知"""
        if not self._notification_callback:
            return

        signal_type_cn = "买入" if signal.signal_type == "buy" else "卖出"
        title = f"[做T提醒] {strategy.symbol} 触发{signal_type_cn}信号"
        content = (
            f"当前价格: {current_price:.2f}\n"
            f"触发价格: {signal.trigger_price:.2f}\n"
            f"建议仓位: {signal.position_ratio:.0f}%"
        )

        try:
            await self._notification_callback(title, content)
            self._logger.info(f"通知已发送: {title}")
        except Exception as e:
            self._logger.error(f"发送通知失败: {e}")

    # ==================== 测试通知 ====================

    async def send_test_notification(self, symbol: str = "测试股票") -> bool:
        """发送测试通知"""
        if not self._notification_callback:
            self._logger.warning("通知回调未配置")
            return False

        title = f"[做T提醒] {symbol} 测试通知"
        content = "这是一条测试通知，确认通知功能正常工作。"

        try:
            await self._notification_callback(title, content)
            self._logger.info("测试通知已发送")
            return True
        except Exception as e:
            self._logger.error(f"发送测试通知失败: {e}")
            return False


# 全局服务实例
_ttrading_service: Optional[TTradingService] = None


def get_ttrading_service() -> TTradingService:
    """获取 TTradingService 单例"""
    global _ttrading_service
    if _ttrading_service is None:
        _ttrading_service = TTradingService()
    return _ttrading_service


def set_ttrading_notification_callback(callback: Callable[[str, str], Any]) -> None:
    """设置通知回调函数"""
    service = get_ttrading_service()
    service._notification_callback = callback
