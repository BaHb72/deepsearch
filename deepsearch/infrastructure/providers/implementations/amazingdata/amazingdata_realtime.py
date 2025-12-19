# encoding:utf-8
"""
AmazingData 实时数据接口实现
实现对实时行情的订阅

Author: DeepSearch Team
Version: 1.0.0
Date: 2025-09-18
"""

from __future__ import annotations

import asyncio
from typing import Any, Callable, Coroutine, Dict, List, Optional, cast

from loguru import logger

# AmazingData SDK
from ._sdk_loader import ad as _sdk_module

CallbackFunc = Callable[[Any, Any], Coroutine[Any, Any, None]]
SubscriptionHandler = Callable[[Any, Any], None]

if _sdk_module is None:
    raise RuntimeError("AmazingData SDK 未加载，无法使用实时订阅功能")

ad = cast(Any, _sdk_module)


class AmazingDataRealtime:
    """AmazingData 实时数据接口实现"""

    def __init__(self, parent: Any) -> None:
        """
        初始化实时行情接口

        Args:
            parent: AmazingDataExtended 实例
        """
        self.parent = parent
        self._subscription_data: Optional[Any] = None
        self._subscription_callbacks: Dict[str, SubscriptionHandler] = {}
        self._subscription_active = False
        self._subscription_lock = asyncio.Lock()

    def _resolve_callback(self, callback: Optional[CallbackFunc], log_prefix: str) -> CallbackFunc:
        """为订阅生成回调，如果用户未传入则提供默认实现"""

        if callback is not None:
            return callback

        async def default_callback(data: Any, period: Any) -> None:
            logger.info(f"{log_prefix} - {period}: {data}")

        return default_callback

    async def _init_subscription(self) -> None:
        """初始化实时订阅通道"""

        if self._subscription_data is not None:
            return

        if not getattr(self.parent, "_connected", False):
            logger.debug("AmazingData 未连接，跳过实时订阅初始化")
            return

        async with self._subscription_lock:
            if self._subscription_data is not None:
                return

            try:
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = asyncio.get_event_loop()

                self._subscription_data = await loop.run_in_executor(None, ad.SubscribeData)
                logger.info("实时行情订阅初始化成功")
            except Exception as exc:  # pragma: no cover - 网络或 SDK 异常
                logger.error(f"初始化实时订阅失败: {exc}")
                self._subscription_data = None

    async def _run_subscription(self) -> None:
        """拉起实时订阅事件循环"""

        if self._subscription_active:
            return

        subscription = self._subscription_data
        if subscription is None:
            return

        self._subscription_active = True
        try:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.get_event_loop()

            await loop.run_in_executor(None, subscription.run)
        except Exception as exc:  # pragma: no cover - SDK 内部异常
            logger.error(f"实时订阅循环执行失败: {exc}")
        finally:
            self._subscription_active = False

    async def _register_handler(
        self,
        *,
        key: str,
        code_list: List[str],
        period_value: Any,
        callback: Optional[CallbackFunc],
        success_message: str,
        error_message: str,
        log_prefix: str,
    ) -> bool:
        """公共的订阅注册逻辑"""

        cb = self._resolve_callback(callback, log_prefix)
        await self._init_subscription()

        subscription = self._subscription_data
        if subscription is None:
            logger.error("实时订阅尚未初始化，无法注册处理器")
            return False

        try:
            @subscription.register(code_list=code_list, period=period_value)
            def handler(data: Any, period: Any) -> None:
                asyncio.create_task(cb(data, period))

            self._subscription_callbacks[key] = handler
            logger.info(success_message)
            asyncio.create_task(self._run_subscription())
            return True
        except Exception as exc:  # pragma: no cover - SDK 注册异常
            logger.error(f"{error_message}: {exc}")
            return False

    # ================== 实时行情接口 ==================

    async def onSnapshotindex(
        self, code_list: List[str], callback: Optional[CallbackFunc] = None
    ) -> bool:
        """3.5.3.1 指数实时行情"""

        return await self._register_handler(
            key="index_snapshot",
            code_list=code_list,
            period_value=ad.constant.Period.snapshot.value,
            callback=callback,
            success_message=f"成功订阅{len(code_list)}个指数实时行情",
            error_message="订阅指数实时行情失败",
            log_prefix="指数实时行情",
        )

    async def onSnapshot(self, code_list: List[str], callback: Optional[CallbackFunc] = None) -> bool:
        """3.5.3.2 股票实时行情"""

        return await self._register_handler(
            key="stock_snapshot",
            code_list=code_list,
            period_value=ad.constant.Period.snapshot.value,
            callback=callback,
            success_message=f"成功订阅{len(code_list)}只股票实时行情",
            error_message="订阅股票实时行情失败",
            log_prefix="股票实时行情",
        )

    async def onSnapshotfuture(
        self, code_list: List[str], callback: Optional[CallbackFunc] = None
    ) -> bool:
        """3.5.3.3 期货实时行情"""

        return await self._register_handler(
            key="future_snapshot",
            code_list=code_list,
            period_value=ad.constant.Period.snapshot_future.value,
            callback=callback,
            success_message=f"成功订阅{len(code_list)}个期货实时行情",
            error_message="订阅期货实时行情失败",
            log_prefix="期货实时行情",
        )

    async def onSnapshotetf(
        self, code_list: List[str], callback: Optional[CallbackFunc] = None
    ) -> bool:
        """3.5.3.4 ETF 实时行情"""

        return await self._register_handler(
            key="etf_snapshot",
            code_list=code_list,
            period_value=ad.constant.Period.snapshot.value,
            callback=callback,
            success_message=f"成功订阅{len(code_list)}个 ETF 实时行情",
            error_message="订阅 ETF 实时行情失败",
            log_prefix="ETF 实时行情",
        )

    async def onSnapshotkzz(
        self, code_list: List[str], callback: Optional[CallbackFunc] = None
    ) -> bool:
        """3.5.3.5 可转债实时行情"""

        return await self._register_handler(
            key="kzz_snapshot",
            code_list=code_list,
            period_value=ad.constant.Period.snapshot.value,
            callback=callback,
            success_message=f"成功订阅{len(code_list)}个可转债实时行情",
            error_message="订阅可转债实时行情失败",
            log_prefix="可转债实时行情",
        )

    async def onSnapshothkt(
        self, code_list: List[str], callback: Optional[CallbackFunc] = None
    ) -> bool:
        """3.5.3.6 沪港通实时行情"""

        return await self._register_handler(
            key="hkt_snapshot",
            code_list=code_list,
            period_value=ad.constant.Period.snapshotHKT.value,
            callback=callback,
            success_message=f"成功订阅{len(code_list)}个沪港通实时行情",
            error_message="订阅沪港通实时行情失败",
            log_prefix="沪港通实时行情",
        )

    async def onSnapshotoption(
        self, code_list: List[str], callback: Optional[CallbackFunc] = None
    ) -> bool:
        """3.5.3.7 ETF期权实时快照"""

        return await self._register_handler(
            key="option_snapshot",
            code_list=code_list,
            period_value=ad.constant.Period.snapshotoption.value,
            callback=callback,
            success_message=f"成功订阅{len(code_list)}个ETF期权实时行情",
            error_message="订阅ETF期权实时行情失败",
            log_prefix="ETF期权实时行情",
        )


    async def OnKLine(
        self, code_list: List[str], period: Optional[str] = None, callback: Optional[CallbackFunc] = None
    ) -> bool:
        """3.5.3.8 实时 K 线"""

        effective_period = period or ad.constant.Period.min1.value
        return await self._register_handler(
            key=f"kline_{effective_period}",
            code_list=code_list,
            period_value=effective_period,
            callback=callback,
            success_message=f"成功订阅{len(code_list)}个 K 线数据，周期: {effective_period}",
            error_message="订阅 K 线数据失败",
            log_prefix="K 线数据",
        )

    async def stop_subscription(self) -> None:
        """停止实时行情订阅"""

        subscription = self._subscription_data
        if subscription is None or not self._subscription_active:
            return

        try:
            if hasattr(subscription, "stop"):
                subscription.stop()
            self._subscription_active = False
            self._subscription_callbacks.clear()
            logger.info("已停止实时行情订阅")
        except Exception as exc:  # pragma: no cover - SDK 停止异常
            logger.error(f"停止实时订阅失败: {exc}")

    def get_subscription_status(self) -> Dict[str, Any]:
        """获取订阅状态"""

        return {
            "active": self._subscription_active,
            "subscriptions": list(self._subscription_callbacks.keys()),
            "subscription_count": len(self._subscription_callbacks),
        }


