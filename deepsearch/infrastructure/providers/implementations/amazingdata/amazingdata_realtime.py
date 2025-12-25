# encoding:utf-8
"""
AmazingData 实时数据接口实现
实现对实时行情的订阅

Author: DeepSearch Team
Version: 1.1.0
Date: 2025-12-22
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional, Union, cast

from loguru import logger

# AmazingData SDK
from ._sdk_loader import ad as _sdk_module
from .amazingdata_types import KlineRecord

# 回调函数类型定义
KlineCallbackFunc = Callable[[KlineRecord, str], Coroutine[Any, Any, None]]
CallbackFunc = Callable[[Any, Any], Coroutine[Any, Any, None]]
SubscriptionHandler = Callable[[Any, Any], None]

if _sdk_module is None:
    raise RuntimeError("AmazingData SDK 未加载，无法使用实时订阅功能")

ad = cast(Any, _sdk_module)


class KlinePeriod(Enum):
    """
    实时K线周期枚举
    
    支持的周期:
    - MIN1: 1分钟线
    - MIN3: 3分钟线
    - MIN5: 5分钟线
    - MIN10: 10分钟线
    - MIN15: 15分钟线
    - MIN30: 30分钟线
    - MIN60: 60分钟线
    - MIN120: 120分钟线
    - DAY: 日线
    - WEEK: 周线
    - MONTH: 月线
    
    K线算法说明 (文档 4.3.2):
    
    1. 集合竞价的处理:
       - 对于分钟K线，开盘集合竞价数据的成交量包含在当日第一根K线
       - 收盘集合竞价数据的成交量包含在当日最后一根K线
    
    2. 前推算法:
       - 9:30 的 1 分钟 K 线，计算的是 9:30:00.000~9:30:59.999 期间的数据
       - 9:35 的 5 分钟 K 线，计算的是 9:35:00.000~9:39:59.999 期间的数据
       - 以此类推，K线时间戳表示该K线的起始时间
    """
    MIN1 = "min1"
    MIN3 = "min3"
    MIN5 = "min5"
    MIN10 = "min10"
    MIN15 = "min15"
    MIN30 = "min30"
    MIN60 = "min60"
    MIN120 = "min120"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


def parse_kline_data(raw_data: Any) -> Optional[KlineRecord]:
    """
    解析 SDK 返回的 K 线数据为标准 KlineRecord 格式
    
    根据文档 4.2.6 K线 Kline 数据结构:
    - code: str - 证券代码+市场
    - trade_time: datetime - 交易所行情数据时间
    - open: float - 今开盘价
    - high: float - 最高价
    - low: float - 最低价
    - close: float - 收盘价
    - volume: int - 成交总量
    - amount: float - 成交总金额
    
    Args:
        raw_data: SDK 返回的原始 K 线数据
        
    Returns:
        解析后的 KlineRecord，解析失败返回 None
    """
    if raw_data is None:
        return None
    
    try:
        # 如果是对象类型，尝试获取属性
        if hasattr(raw_data, 'code'):
            return KlineRecord(
                code=getattr(raw_data, 'code', ''),
                trade_time=getattr(raw_data, 'trade_time', datetime.now()),
                open=float(getattr(raw_data, 'open', 0)),
                high=float(getattr(raw_data, 'high', 0)),
                low=float(getattr(raw_data, 'low', 0)),
                close=float(getattr(raw_data, 'close', 0)),
                volume=int(getattr(raw_data, 'volume', 0)),
                amount=float(getattr(raw_data, 'amount', 0)),
            )
        # 如果是字典类型
        elif isinstance(raw_data, dict):
            return KlineRecord(
                code=raw_data.get('code', ''),
                trade_time=raw_data.get('trade_time', datetime.now()),
                open=float(raw_data.get('open', 0)),
                high=float(raw_data.get('high', 0)),
                low=float(raw_data.get('low', 0)),
                close=float(raw_data.get('close', 0)),
                volume=int(raw_data.get('volume', 0)),
                amount=float(raw_data.get('amount', 0)),
            )
        else:
            logger.warning(f"无法解析的 K 线数据类型: {type(raw_data)}")
            return None
    except Exception as e:
        logger.error(f"解析 K 线数据失败: {e}")
        return None


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
        self,
        code_list: List[str],
        period: Optional[Union[str, KlinePeriod]] = None,
        callback: Optional[CallbackFunc] = None
    ) -> bool:
        """
        3.5.3.8 实时 K 线订阅
        
        K线数据的实时订阅回调函数，支持北交所、上交所、深交所的可转债、
        股票、指数、ETF等品种，支持期货（中金所/上期所/大商所/郑商所/上海国际能源交易中心所）
        
        Args:
            code_list: 证券代码列表，如 ["000001.SZ", "600519.SH"]
            period: K线周期，可选值：
                - KlinePeriod.MIN1 / "min1": 1分钟线 (默认)
                - KlinePeriod.MIN3 / "min3": 3分钟线
                - KlinePeriod.MIN5 / "min5": 5分钟线
                - KlinePeriod.MIN10 / "min10": 10分钟线
                - KlinePeriod.MIN15 / "min15": 15分钟线
                - KlinePeriod.MIN30 / "min30": 30分钟线
                - KlinePeriod.MIN60 / "min60": 60分钟线
                - KlinePeriod.MIN120 / "min120": 120分钟线
                - KlinePeriod.DAY / "day": 日线
                - KlinePeriod.WEEK / "week": 周线
                - KlinePeriod.MONTH / "month": 月线
            callback: 回调函数，接收 (data: Kline, period: str) 参数
                - data.code: str - 证券代码+市场
                - data.trade_time: datetime - 交易所行情数据时间
                - data.open: float - 今开盘价
                - data.high: float - 最高价
                - data.low: float - 最低价
                - data.close: float - 收盘价
                - data.volume: int - 成交总量
                - data.amount: float - 成交总金额
                
        Returns:
            bool: 订阅是否成功
            
        Example:
            ```python
            async def on_kline(data, period):
                print(f"OnKLine: {data.code} {period} O:{data.open} H:{data.high} L:{data.low} C:{data.close}")
            
            await realtime.OnKLine(["000001.SZ"], KlinePeriod.MIN1, on_kline)
            ```
        """
        # 解析周期参数
        if isinstance(period, KlinePeriod):
            period_value = getattr(ad.constant.Period, period.value, ad.constant.Period.min1).value
        elif period is not None:
            # 尝试从 ad.constant.Period 获取对应值
            period_attr = period.lower().replace("-", "").replace("_", "")
            period_value = getattr(ad.constant.Period, period_attr, ad.constant.Period.min1).value
        else:
            period_value = ad.constant.Period.min1.value
        
        return await self._register_handler(
            key=f"kline_{period_value}",
            code_list=code_list,
            period_value=period_value,
            callback=callback,
            success_message=f"成功订阅{len(code_list)}个 K 线数据，周期: {period_value}",
            error_message="订阅 K 线数据失败",
            log_prefix="K 线数据",
        )

    # ================== 便捷的 K 线订阅方法 ==================

    async def OnKLineMin1(
        self, code_list: List[str], callback: Optional[CallbackFunc] = None
    ) -> bool:
        """订阅1分钟K线"""
        return await self.OnKLine(code_list, KlinePeriod.MIN1, callback)

    async def OnKLineMin5(
        self, code_list: List[str], callback: Optional[CallbackFunc] = None
    ) -> bool:
        """订阅5分钟K线"""
        return await self.OnKLine(code_list, KlinePeriod.MIN5, callback)

    async def OnKLineMin15(
        self, code_list: List[str], callback: Optional[CallbackFunc] = None
    ) -> bool:
        """订阅15分钟K线"""
        return await self.OnKLine(code_list, KlinePeriod.MIN15, callback)

    async def OnKLineMin30(
        self, code_list: List[str], callback: Optional[CallbackFunc] = None
    ) -> bool:
        """订阅30分钟K线"""
        return await self.OnKLine(code_list, KlinePeriod.MIN30, callback)

    async def OnKLineMin60(
        self, code_list: List[str], callback: Optional[CallbackFunc] = None
    ) -> bool:
        """订阅60分钟K线"""
        return await self.OnKLine(code_list, KlinePeriod.MIN60, callback)

    async def OnKLineDay(
        self, code_list: List[str], callback: Optional[CallbackFunc] = None
    ) -> bool:
        """订阅日K线"""
        return await self.OnKLine(code_list, KlinePeriod.DAY, callback)

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


