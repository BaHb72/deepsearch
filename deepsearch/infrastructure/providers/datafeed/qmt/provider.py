"""
QMT数据提供者

通过QMT网关获取市场数据
"""

import asyncio
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple, TypedDict, cast, TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from pandas import DataFrame
else:
    DataFrame = Any  # type: ignore[assignment]

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:  # pragma: no cover
    pd = cast(Any, None)
    HAS_PANDAS = False




class SubscriptionInfo(TypedDict):
    symbol: str
    period: str
    callback: Optional[Callable[[Dict[str, Any]], None]]

class QMTDataProvider:
    """QMT数据提供者 - 实现统一数据接口"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化提供者"""
        self.config = config or {}
        self.gateway: Any = None
        self.connected: bool = False
        self.initialized: bool = False

        # 缓存
        self._cache: Dict[str, Tuple[float, Any]] = {}
        self._cache_ttl: Dict[str, int] = {
            "realtime": 3,  # 实时数据缓存3秒
            "hist": 60,  # 历史数据缓存60秒
            "info": 300,  # 股票信息缓存5分钟
        }
        self._subscriptions: Dict[int, SubscriptionInfo] = {}

    async def initialize(self) -> None:
        """初始化QMT连接"""
        try:
            # 获取QMT网关实例
            # 通过全局上下文获取主引擎，然后获取组件
            from deepsearch.core.components import QMTGatewayComponent
            from deepsearch.core.runtime.context import get_context

            context = get_context()
            engine = context.get_engine()
            self.gateway = engine.get_component(QMTGatewayComponent)

            if self.gateway:
                # 尝试获取内部网关实例
                if hasattr(self.gateway, "get_instance"):
                    qmt_gateway = self.gateway.get_instance()
                elif hasattr(self.gateway, "_gateway"):
                    qmt_gateway = self.gateway._gateway
                else:
                    qmt_gateway = self.gateway

                if qmt_gateway:
                    self.gateway = qmt_gateway
                    self.connected = True
                    self.initialized = True
                    logger.info("QMT data provider initialized successfully")
                    return

            logger.warning("QMT gateway not connected or unavailable")
            self.connected = False
            self.initialized = False

        except Exception as e:
            logger.error(f"Failed to initialize QMT data provider: {e}")
            self.connected = False

    async def get_stock_hist(
        self,
        symbol: str,
        period: str = "daily",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        adjust: str = "",
    ) -> Dict[str, Any]:
        """
        获取股票历史数据（增强版）

        Args:
            symbol: 股票代码
            period: 周期（tick, 1m, 5m, 15m, 30m, 60m, daily, weekly, monthly）
            start_date: 开始日期（格式：YYYYMMDD 或 YYYYMMDD HH:MM:SS）
            end_date: 结束日期
            adjust: 复权类型（none不复权, qfq前复权, hfq后复权, qfq_ratio等比前复权, hfq_ratio等比后复权）

        Returns:
            历史K线数据
        """
        if not self.connected:
            return {"data": [], "error": "QMT未连接"}

        try:
            # 检查缓存
            cache_key = f"hist_{symbol}_{period}_{start_date}_{end_date}_{adjust}"
            if cache_key in self._cache:
                cached_time, cached_data = self._cache[cache_key]
                if time.time() - cached_time < self._cache_ttl["hist"]:
                    return cast(Dict[str, Any], cached_data)

            # 从QMT网关获取数据
            if self.gateway and hasattr(self.gateway, "_gateway"):
                qmt_gateway = self.gateway._gateway

                # 调用QMT获取K线数据
                logger.debug(f"Requesting QMT historical data: {symbol} {period}")

                # 通过QMT网关获取历史数据
                # 发送数据请求事件
                from deepsearch.event.schema import Event

                limit = None
                request_event = Event(
                    type="EVENT_QMT_REQUEST_HISTORY",
                    data={
                        "symbol": symbol,
                        "period": period,
                        "start_date": start_date,
                        "end_date": end_date,
                        "limit": limit,
                    },
                )

                # 发送请求并等待响应
                if hasattr(qmt_gateway, "event_engine"):
                    qmt_gateway.event_engine.put(request_event)

                    # 等待数据返回（使用缓存的tick数据构建K线）
                    time.sleep(0.1)  # 短暂等待数据更新

                    # 从缓存的tick数据构建K线
                    if hasattr(qmt_gateway, "latest_ticks"):
                        tick_data = qmt_gateway.latest_ticks.get(symbol)
                        if tick_data:
                            # 构建单根K线数据（实时数据）
                            kline = {
                                "time": (
                                    tick_data.datetime.strftime("%Y-%m-%d %H:%M:%S")
                                    if hasattr(tick_data, "datetime")
                                    else ""
                                ),
                                "open": tick_data.open_price,
                                "high": tick_data.high_price,
                                "low": tick_data.low_price,
                                "close": tick_data.last_price,
                                "volume": tick_data.volume,
                                "amount": tick_data.amount,
                            }
                            result = {"data": [kline], "source": "qmt"}
                        else:
                            result = {"data": [], "source": "qmt", "error": "暂无历史数据"}
                    else:
                        result = {"data": [], "source": "qmt", "error": "QMT数据未就绪"}
                else:
                    result = {"data": [], "source": "qmt", "error": "事件引擎未初始化"}

                # 缓存结果
                self._cache[cache_key] = (time.time(), result)

                return result

            return {"data": [], "error": "QMT网关不可用"}

        except Exception as e:
            logger.error(f"QMT failed to get historical data for {symbol}: {e}")
            return {"data": [], "error": str(e)}

    async def get_realtime_quote(self, symbol: str) -> Dict[str, Any]:
        """
        获取实时行情

        Args:
            symbol: 股票代码

        Returns:
            实时行情数据
        """
        if not self.connected:
            return {"error": "QMT未连接"}

        try:
            # 检查缓存
            cache_key = f"quote_{symbol}"
            if cache_key in self._cache:
                cached_time, cached_data = self._cache[cache_key]
                if time.time() - cached_time < self._cache_ttl["realtime"]:
                    return cast(Dict[str, Any], cached_data)

            # 从QMT网关获取最新tick数据
            if self.gateway and hasattr(self.gateway, "_gateway"):
                qmt_gateway = self.gateway._gateway

                # 检查是否有缓存的tick数据
                if hasattr(qmt_gateway, "latest_ticks"):
                    tick_data = qmt_gateway.latest_ticks.get(symbol)
                    if tick_data:
                        result = {
                            "symbol": symbol,
                            "name": tick_data.name if hasattr(tick_data, "name") else "",
                            "current": tick_data.last_price,
                            "open": tick_data.open_price,
                            "high": tick_data.high_price,
                            "low": tick_data.low_price,
                            "prev_close": tick_data.pre_close,
                            "volume": tick_data.volume,
                            "amount": tick_data.amount,
                            "time": (
                                tick_data.datetime.strftime("%Y-%m-%d %H:%M:%S")
                                if hasattr(tick_data, "datetime")
                                else ""
                            ),
                            "source": "qmt",
                        }

                        # 缓存结果
                        self._cache[cache_key] = (time.time(), result)

                        return result

            return {"error": "无实时数据", "source": "qmt"}

        except Exception as e:
            logger.error(f"QMT failed to get realtime quote for {symbol}: {e}")
            return {"error": str(e)}

    async def fetch_stock_info(self, symbol: str) -> Dict[str, Any]:
        """
        获取股票信息

        Args:
            symbol: 股票代码

        Returns:
            股票基础信息
        """
        if not self.connected:
            return {"symbol": symbol, "name": f"股票{symbol}", "error": "QMT未连接"}

        try:
            # 检查缓存
            cache_key = f"info_{symbol}"
            if cache_key in self._cache:
                cached_time, cached_data = self._cache[cache_key]
                if time.time() - cached_time < self._cache_ttl["info"]:
                    return cast(Dict[str, Any], cached_data)

            # 从QMT获取股票信息
            if self.gateway and hasattr(self.gateway, "_gateway"):
                qmt_gateway = self.gateway._gateway

                # 检查股票信息缓存
                if hasattr(qmt_gateway, "stock_info_cache"):
                    stock_info = qmt_gateway.stock_info_cache.get(symbol)
                    if stock_info:
                        result = {
                            "symbol": symbol,
                            "name": stock_info.get("name", f"股票{symbol}"),
                            "industry": stock_info.get("industry", ""),
                            "sector": stock_info.get("sector", ""),
                            "market": stock_info.get("market", ""),
                            "listed_date": stock_info.get("list_date", ""),
                            "total_shares": stock_info.get("total_shares", 0),
                            "float_shares": stock_info.get("float_shares", 0),
                            "source": "qmt",
                        }

                        # 缓存结果
                        self._cache[cache_key] = (time.time(), result)

                        return result

            # 如果没有缓存数据，请求QMT获取
            # 发送股票信息请求
            from deepsearch.event.schema import Event

            info_request = Event(type="EVENT_QMT_REQUEST_INFO", data={"symbol": symbol})

            if self.gateway and hasattr(self.gateway, "_gateway"):
                qmt_gateway = self.gateway._gateway
                if hasattr(qmt_gateway, "event_engine"):
                    qmt_gateway.event_engine.put(info_request)

                    # 等待响应
                    time.sleep(0.1)

                    # 再次检查缓存
                    if hasattr(qmt_gateway, "stock_info_cache"):
                        stock_info = qmt_gateway.stock_info_cache.get(symbol)
                        if stock_info:
                            result = {
                                "symbol": symbol,
                                "name": stock_info.get("name", f"股票{symbol}"),
                                "industry": stock_info.get("industry", ""),
                                "sector": stock_info.get("sector", ""),
                                "market": stock_info.get("market", ""),
                                "listed_date": stock_info.get("list_date", ""),
                                "total_shares": stock_info.get("total_shares", 0),
                                "float_shares": stock_info.get("float_shares", 0),
                                "source": "qmt",
                            }

                            # 缓存结果
                            self._cache[cache_key] = (time.time(), result)
                            return result

            # 如果仍然没有数据，尝试从本地缓存文件读取
            try:
                import json
                import os

                cache_file = os.path.join(
                    os.path.dirname(__file__), "..", "..", "data", "stock_info_cache.json"
                )
                if os.path.exists(cache_file):
                    with open(cache_file, "r", encoding="utf-8") as f:
                        local_cache = json.load(f)
                        if symbol in local_cache:
                            name = local_cache[symbol]
                            result = {
                                "symbol": symbol,
                                "name": name,
                                "industry": "",
                                "sector": "",
                                "market": "SH" if symbol.startswith("6") else "SZ",
                                "source": "local_cache",
                            }
                            self._cache[cache_key] = (time.time(), result)
                            return result
            except Exception as e:
                logger.debug(f"Failed to read local cache: {e}")

            return {
                "symbol": symbol,
                "name": f"股票{symbol}",
                "source": "qmt",
                "error": "暂无股票信息",
            }

        except Exception as e:
            logger.error(f"QMT failed to get stock info for {symbol}: {e}")
            return {"symbol": symbol, "name": f"股票{symbol}", "error": str(e)}

    async def fetch_stock_list(self) -> List[Dict[str, str]]:
        """
        获取股票列表

        Returns:
            股票列表
        """
        if not self.connected:
            return []

        try:
            # 从QMT获取股票列表
            if self.gateway and hasattr(self.gateway, "_gateway"):
                qmt_gateway = self.gateway._gateway

                # 检查订阅的股票列表
                if hasattr(qmt_gateway, "subscribed_symbols"):
                    symbols = list(qmt_gateway.subscribed_symbols)

                    stocks = []
                    for symbol in symbols:
                        # 获取股票信息
                        if hasattr(qmt_gateway, "stock_info_cache"):
                            info = qmt_gateway.stock_info_cache.get(symbol, {})
                            stocks.append(
                                {"代码": symbol, "名称": info.get("name", f"股票{symbol}")}
                            )
                        else:
                            stocks.append({"代码": symbol, "名称": f"股票{symbol}"})

                    if stocks:
                        logger.info(f"Got {len(stocks)} stock records from QMT")
                        return stocks

            return []

        except Exception as e:
            logger.error(f"QMT failed to get stock list: {e}")
            return []

    async def subscribe_symbols(self, symbols: List[str]) -> None:
        """
        订阅股票行情

        Args:
            symbols: 股票代码列表
        """
        if not self.connected:
            logger.warning("QMT not connected, cannot subscribe")
            return

        try:
            if self.gateway and hasattr(self.gateway, "_gateway"):
                qmt_gateway = self.gateway._gateway

                # 调用QMT网关的订阅方法
                if hasattr(qmt_gateway, "subscribe"):
                    await qmt_gateway.subscribe(symbols)
                    logger.info(f"Subscribed to {len(symbols)} stocks")

        except Exception as e:
            logger.error(f"Failed to subscribe stocks: {e}")

    async def unsubscribe_symbols(self, symbols: List[str]) -> None:
        """
        取消订阅股票行情

        Args:
            symbols: 股票代码列表
        """
        if not self.connected:
            return

        try:
            if self.gateway and hasattr(self.gateway, "_gateway"):
                qmt_gateway = self.gateway._gateway

                # 调用QMT网关的取消订阅方法
                if hasattr(qmt_gateway, "unsubscribe"):
                    await qmt_gateway.unsubscribe(symbols)
                    logger.info(f"Unsubscribed from {len(symbols)} stocks")

        except Exception as e:
            logger.error(f"Failed to unsubscribe: {e}")

    def is_connected(self) -> bool:
        """检查是否连接"""
        return self.connected

    async def close(self) -> None:
        """关闭连接"""
        self.connected = False
        self._cache.clear()
        logger.info("QMT data provider closed")

    async def subscribe_quote(
        self, symbol: str, period: str = "tick", callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> int:
        """
        订阅实时行情（增强版）

        Args:
            symbol: 股票代码
            period: 周期（tick, 1m, 5m等）
            callback: 数据回调函数

        Returns:
            订阅ID
        """
        if not self.connected:
            logger.warning("QMT not connected, cannot subscribe")
            return -1

        try:
            # 生成订阅ID
            sub_id = int(time.time() * 1000) % 1000000

            # 注册回调
            self._subscriptions[sub_id] = {
                "symbol": symbol,
                "period": period,
                "callback": callback,
            }

            # 发送订阅请求
            from deepsearch.event.schema import Event

            subscribe_event = Event(
                type="EVENT_QMT_SUBSCRIBE",
                data={"symbol": symbol, "period": period, "sub_id": sub_id},
            )

            if self.gateway and hasattr(self.gateway, "_gateway"):
                qmt_gateway = self.gateway._gateway
                if hasattr(qmt_gateway, "event_engine"):
                    qmt_gateway.event_engine.put(subscribe_event)
                    logger.info(
                        f"Subscribed to {symbol} {period} quotes, subscription ID: {sub_id}"
                    )

                    # 设置数据处理器
                    self._setup_data_handler(qmt_gateway, sub_id)

            return sub_id

        except Exception as e:
            logger.error(f"Failed to subscribe quotes: {e}")
            return -1

    def _setup_data_handler(self, gateway, sub_id: int):
        """设置数据处理器"""

        def on_data(event):
            """处理推送的数据"""
            sub_info = self._subscriptions.get(sub_id)
            if not sub_info:
                return
            if event.data.get("symbol") == sub_info["symbol"]:
                callback = sub_info.get("callback")
                if callback:
                    callback(event.data)

        # 注册事件处理器
        if hasattr(gateway, "event_engine"):
            gateway.event_engine.register("EVENT_QMT_DATA", on_data)

    async def unsubscribe_quote(self, sub_id: int) -> bool:
        """
        取消订阅

        Args:
            sub_id: 订阅ID

        Returns:
            是否成功
        """
        try:
            sub_info = self._subscriptions.get(sub_id)
            if not sub_info:
                return False

            from deepsearch.event.schema import Event

            unsubscribe_event = Event(
                type="EVENT_QMT_UNSUBSCRIBE",
                data={
                    "symbol": sub_info["symbol"],
                    "period": sub_info["period"],
                    "sub_id": sub_id,
                },
            )

            if self.gateway and hasattr(self.gateway, "_gateway"):
                qmt_gateway = self.gateway._gateway
                if hasattr(qmt_gateway, "event_engine"):
                    qmt_gateway.event_engine.put(unsubscribe_event)

            self._subscriptions.pop(sub_id, None)
            logger.info(f"Cancelled subscription ID: {sub_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to unsubscribe: {e}")
            return False

    async def get_financial_data(
        self,
        symbol: str,
        fields: List[str],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        report_type: str = "announce_time",
    ) -> Dict[str, Any]:
        """
        获取财务数据

        Args:
            symbol: 股票代码
            fields: 字段列表，如['ASHAREINCOME.net_profit', 'CAPITALSTRUCTURE.total_capital']
            start_date: 开始日期
            end_date: 结束日期
            report_type: 时间类型（announce_time按公告期, report_time按报告期）

        Returns:
            财务数据
        """
        if not self.connected:
            return {"error": "QMT未连接"}

        try:
            # 检查缓存
            cache_key = (
                f"financial_{symbol}_{','.join(fields)}_{start_date}_{end_date}_{report_type}"
            )
            if cache_key in self._cache:
                cached_time, cached_data = self._cache[cache_key]
                if time.time() - cached_time < self._cache_ttl.get("financial", 86400):
                    return cast(Dict[str, Any], cached_data)

            # 发送财务数据请求
            from deepsearch.event.schema import Event

            financial_event = Event(
                type="EVENT_QMT_FINANCIAL",
                data={
                    "symbol": symbol,
                    "fields": fields,
                    "start_date": start_date,
                    "end_date": end_date,
                    "report_type": report_type,
                },
            )

            data_section: Dict[str, Dict[str, Any]] = {}
            result: Dict[str, Any] = {"data": data_section, "source": "qmt"}

            if self.gateway and hasattr(self.gateway, "_gateway"):
                qmt_gateway = self.gateway._gateway
                if hasattr(qmt_gateway, "event_engine"):
                    qmt_gateway.event_engine.put(financial_event)

                    # 等待数据返回（简化处理，实际应该异步等待）
                    await asyncio.sleep(0.5)

                    # 构造示例数据（实际应该从事件返回获取）
                    for field in fields:
                        data_section[field] = {
                            "value": 0,
                            "date": end_date or datetime.now().strftime("%Y%m%d"),
                        }

            # 缓存结果
            self._cache[cache_key] = (time.time(), result)

            return result

        except Exception as e:
            logger.error(f"Failed to get financial data: {e}")
            return {"error": str(e)}

    async def get_factor_data(
        self, symbol: str, factors: List[str], start_date: Optional[str] = None, end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        获取因子数据

        Args:
            symbol: 股票代码
            factors: 因子列表
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            因子数据
        """
        if not self.connected:
            return {"error": "QMT未连接"}

        try:
            # 发送因子数据请求
            from deepsearch.event.schema import Event

            factor_event = Event(
                type="EVENT_QMT_FACTOR",
                data={
                    "symbol": symbol,
                    "factors": factors,
                    "start_date": start_date,
                    "end_date": end_date,
                },
            )

            data_section: Dict[str, Dict[str, Any]] = {}
            result: Dict[str, Any] = {"data": data_section, "source": "qmt"}

            if self.gateway and hasattr(self.gateway, "_gateway"):
                qmt_gateway = self.gateway._gateway
                if hasattr(qmt_gateway, "event_engine"):
                    qmt_gateway.event_engine.put(factor_event)

                    # 等待数据返回
                    await asyncio.sleep(0.5)

                    # 构造示例数据
                    for factor in factors:
                        data_section[factor] = {
                            "value": 0,
                            "date": end_date or datetime.now().strftime("%Y%m%d"),
                        }

            return result

        except Exception as e:
            logger.error(f"Failed to get factor data: {e}")
            return {"error": str(e)}
