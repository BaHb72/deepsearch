"""Subscription orchestration for AmazingData providers."""

from __future__ import annotations

import asyncio
import contextlib
from datetime import datetime
from typing import Any, Callable, Mapping, Sequence, TYPE_CHECKING, cast

from deepsearch.infrastructure.providers.interfaces.base import DataProvider, DataProviderError
from .logging_utils import log_debug, log_error, log_info, log_warning
from .subscription import SubscriptionInfo, SubscriptionRegistry

if TYPE_CHECKING:
    from .amazingdata import AmazingDataProvider

class AmazingDataSubscriptionManager:
    """Manage AmazingData SubscribeData lifecycle and callback dispatch."""

    def __init__(self, owner: "AmazingDataProvider") -> None:
        from .amazingdata import AmazingDataProvider  # Local import to avoid circular import at module load time.

        if not isinstance(owner, AmazingDataProvider):
            if not isinstance(owner, DataProvider):
                raise TypeError("owner must be AmazingDataProvider")
        self._owner = cast(AmazingDataProvider, owner)
        self._registry = SubscriptionRegistry()
        self._subscription_data: Any | None = None
        self._subscription_runner: asyncio.Future[Any] | None = None
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    async def initialize(self) -> None:
        if self._owner._degraded_mode:
            log_warning("AmazingData 处于降级模式，跳过订阅初始化", action="subscription_init")
            return
        if self._subscription_data is not None:
            return
        sdk = self._owner._require_sdk()
        try:
            self._subscription_data = sdk.SubscribeData()
            log_info("AmazingData SubscribeData 初始化完成", action="subscription_init")
        except Exception as exc:
            log_error(f"AmazingData SubscribeData 初始化失败: {exc}", action="subscription_init")
            raise DataProviderError(f"AmazingData SubscribeData 初始化失败: {exc}") from exc

    async def shutdown(self) -> None:
        runner = self._subscription_runner
        if runner is not None:
            runner.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await runner
        self._subscription_runner = None

        subscription_data = self._subscription_data
        if subscription_data is not None and hasattr(subscription_data, "stop"):
            try:
                subscription_data.stop()
            except Exception:  # pragma: no cover - 安全起见忽略 stop 异常
                pass
        self._subscription_data = None
        self._registry.clear()
        self._update_subscription_stats()

    # ------------------------------------------------------------------
    # Public operations
    # ------------------------------------------------------------------
    async def subscribe(
            self,
            symbols: Sequence[str],
            callback: Callable[[Any], Any],
            data_type: str = "snapshot",
    ) -> bool:
        if not symbols:
            log_warning("订阅请求缺少股票代码", action="subscription")
            return False
        if self._owner._degraded_mode:
            log_warning("AmazingData 降级模式下无法订阅", action="subscription")
            return False

        self._owner._ensure_sdk_ready()
        await self.initialize()

        period_value = self._resolve_period(data_type)
        subscription_data = self._subscription_data
        if subscription_data is None:
            raise DataProviderError("SubscribeData 初始化失败，无法订阅")

        normalized = [symbol.strip().upper() for symbol in symbols if isinstance(symbol, str) and symbol.strip()]
        if not normalized:
            log_warning("经标准化后订阅列表为空，忽略", action="subscription")
            return False

        @subscription_data.register(code_list=normalized, period=period_value)
        def _on_data(payload: Any, period: int) -> None:
            self._owner._increment_stat("messages_received")
            asyncio.create_task(self._handle_subscription_event(payload, period, callback))

        async with self._lock:
            self._registry.add(normalized, callback, data_type)
            self._update_subscription_stats()

        await self._ensure_runner()
        log_info(
            "成功订阅 AmazingData 实时行情",
            action="subscription",
            metadata={"symbols": len(normalized), "type": data_type},
        )
        return True

    async def unsubscribe(self, symbols: Sequence[str]) -> bool:
        normalized = [symbol.strip().upper() for symbol in symbols if isinstance(symbol, str) and symbol.strip()]
        if not normalized:
            return True
        async with self._lock:
            removed = self._registry.remove(normalized)
            self._update_subscription_stats()
        log_info(
            "取消订阅完成",
            action="subscription_unsubscribe",
            metadata={"removed": len(removed), "requested": len(normalized)},
        )
        return True

    async def restore(self, snapshot: Mapping[str, SubscriptionInfo]) -> None:
        if not snapshot:
            return
        log_debug(
            "准备恢复订阅",
            action="subscription_restore",
            metadata={"count": len(snapshot)},
        )
        await self.initialize()
        for symbol, info in snapshot.items():
            callbacks = list(info.callbacks)
            if not callbacks:
                continue
            try:
                primary = callbacks[0]
                success = await self.subscribe([symbol], primary, info.data_type)
                if not success:
                    self._registry.restore({symbol: info})
                    continue
                if len(callbacks) > 1:
                    entry = self._registry.get(symbol)
                    if entry is not None:
                        entry.extend_callbacks(callbacks[1:])
                log_info(
                    "恢复订阅成功",
                    action="subscription_restore",
                    symbol=symbol,
                )
            except Exception as exc:
                log_error(
                    "恢复订阅失败",
                    action="subscription_restore",
                    symbol=symbol,
                    metadata={"error": repr(exc)},
                )
                self._registry.restore({symbol: info})
        self._update_subscription_stats()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def has_active(self) -> bool:
        return bool(self._registry)

    def snapshot(self) -> Mapping[str, SubscriptionInfo]:
        return self._registry.snapshot()

    def drain(self) -> Mapping[str, SubscriptionInfo]:
        snapshot = self._registry.drain()
        self._update_subscription_stats()
        return snapshot

    @property
    def subscription_count(self) -> int:
        return len(self._registry)

    async def _handle_subscription_event(
            self,
            data: Any,
            period: int,
            callback: Callable[[Any], Any],
    ) -> None:
        try:
            converted = self._convert_subscription_data(data, period)
            if asyncio.iscoroutinefunction(callback):
                await callback(converted)
            else:
                callback(converted)
        except Exception as exc:
            log_error(f"AmazingData 订阅回调执行失败: {exc}", action="subscription_dispatch")

    async def _ensure_runner(self) -> None:
        if self._subscription_data is None:
            return
        runner = self._subscription_runner
        if runner is not None and not runner.done():
            return
        loop = asyncio.get_event_loop()
        self._subscription_runner = loop.run_in_executor(None, self._subscription_data.run)

    def _resolve_period(self, data_type: str) -> Any:
        sdk = self._owner._require_sdk()
        constant = getattr(sdk, "constant", None)
        if constant is None:
            raise DataProviderError("AmazingData SDK 未提供 constant，无法解析订阅周期")
        period_map = {
            "snapshot": ("Period.snapshot", "snapshot"),
            "kline": ("Period.m1", "m1"),
            "tick": ("Period.tick", "tick"),
        }
        normalized = data_type.lower().strip()
        if normalized not in period_map:
            raise DataProviderError(f"不支持的订阅类型: {data_type}")
        attr_path, fallback = period_map[normalized]
        try:
            period = constant
            for attr in attr_path.split("."):
                period = getattr(period, attr)
            return getattr(period, "value", period)
        except AttributeError:
            log_warning(f"AmazingData 常量 {attr_path} 缺失，回退为 {fallback}", action="subscription_period")
            return fallback

    def _convert_subscription_data(self, data: Any, period: int) -> dict[str, Any]:
        try:
            timestamp = datetime.now()
            result: dict[str, Any] = {"period": period, "timestamp": timestamp, "raw_data": data}

            if hasattr(data, "__dict__"):
                data_dict: dict[str, Any] = {}
                common_fields = [
                    "code",
                    "name",
                    "time",
                    "price",
                    "open",
                    "high",
                    "low",
                    "close",
                    "volume",
                    "amount",
                    "bid",
                    "ask",
                    "bid_volume",
                    "ask_volume",
                    "pre_close",
                    "change",
                    "change_rate",
                    "turnover_rate",
                    "pe",
                    "pb",
                    "market_cap",
                    "circulation_market_cap",
                ]
                for field in common_fields:
                    if hasattr(data, field):
                        value = getattr(data, field)
                        if hasattr(value, "isoformat"):
                            data_dict[field] = value.isoformat()
                        elif isinstance(value, (list, tuple)):
                            if field in {"bid", "ask", "bid_volume", "ask_volume"}:
                                data_dict[field] = list(value)[:5]
                            else:
                                data_dict[field] = list(value)
                        else:
                            data_dict[field] = value

                for attr in dir(data):
                    if attr.startswith("_") or attr in common_fields:
                        continue
                    try:
                        value = getattr(data, attr)
                    except Exception:
                        continue
                    if not callable(value):
                        data_dict[attr] = value

                result["data"] = data_dict
                result["data_type"] = type(data).__name__
            elif isinstance(data, dict):
                result["data"] = data
                result["data_type"] = "dict"
            elif isinstance(data, (list, tuple)):
                result["data"] = list(data)
                result["data_type"] = "list"
            else:
                result["data"] = data
                result["data_type"] = type(data).__name__

            payload = result.get("data")
            if isinstance(payload, dict):
                if "change_rate" in payload:
                    result["change_direction"] = "up" if payload["change_rate"] > 0 else "down"
                required_fields = ["code", "price", "volume"]
                result["is_complete"] = all(field in payload for field in required_fields)

            return result
        except Exception as exc:
            log_error(f"订阅数据转换失败: {exc}", action="subscription_convert")
            return {
                "data": data,
                "period": period,
                "timestamp": datetime.now(),
                "error": str(exc),
            }

    def _update_subscription_stats(self) -> None:
        self._owner._stats["subscriptions"] = len(self._registry)
