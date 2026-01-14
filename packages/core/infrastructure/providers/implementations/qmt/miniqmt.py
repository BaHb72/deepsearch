"""
MiniQMT 数据提供者

提供 MiniQMT 量化终端的数据接入功能
"""

import asyncio
import inspect
import json
import socket
import struct
import time
from typing import Any, Awaitable, Callable, Dict, List, Optional, cast

import pandas as pd

# Arrow Cache for high-performance file-based caching
from core.infrastructure.cache import ArrowCacheManager
from core.infrastructure.providers.interfaces.base import (
    DataProvider,
    DataProviderConfig,
    DataProviderError,
    DataRequest,
    DataResponse,
    DataSourceType,
)
from core.infrastructure.providers.interfaces.capabilities import DataCapability
from loguru import logger

# 模块级别导入 xtquant，避免在每个函数中重复导入（会导致重复的连接消息）
try:
    from xtquant import xtdata

    XTDATA_AVAILABLE = True
except ImportError:
    xtdata = None  # type: ignore[assignment]
    XTDATA_AVAILABLE = False


class MiniQMTProvider(DataProvider):
    """
    MiniQMT 数据提供者

    功能：
    - 连接 MiniQMT 终端获取实时和历史数据
    - 支持股票、期货、期权等多品种
    - 自动重连和错误恢复
    - 数据缓存和性能优化
    """

    def __init__(self, config: Optional[DataProviderConfig] = None):
        """初始化 MiniQMT 提供者"""
        if config is None:
            # 创建默认配置
            config = DataProviderConfig(
                name="miniqmt",
                source_type=DataSourceType.QMT,
                enabled=True,
                timeout=10,
                config={
                    "max_concurrent": 10,
                    "rate_limit": 100,  # MiniQMT 每秒最多 100 个请求
                    "retry_times": 3,
                    "retry_delay": 1.0,
                    "cache_enabled": True,
                    "cache_ttl": 60,  # 1分钟缓存
                },
            )

        super().__init__(config)

        # MiniQMT 特定配置
        self.host = "127.0.0.1"
        self.port = 7777  # MiniQMT 默认端口
        self.username = ""
        self.password = ""

        # 连接状态
        self.socket: Optional[socket.socket] = None
        self.connected = False
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5

        # 订阅管理
        self.subscribed_symbols: set[str] = set()
        self.symbol_callbacks: dict[
            str, list[Callable[[Dict[str, Any]], Awaitable[None] | None]]
        ] = {}

        # 心跳管理
        self.last_heartbeat = time.time()
        self.heartbeat_interval = 30  # 30秒心跳
        self.heartbeat_task: Optional[asyncio.Task[None]] = None

        # 数据接收
        self.receive_task: Optional[asyncio.Task[None]] = None
        self.data_queue: "asyncio.Queue[Dict[str, Any]]" = asyncio.Queue(maxsize=10000)

        # Arrow IPC 文件缓存，支持跨进程共享
        cache_ttl_raw = config.config.get("cache_ttl", 60) if config.config else 60
        cache_ttl = int(str(cache_ttl_raw)) if cache_ttl_raw is not None else 60
        self.cache = ArrowCacheManager(namespace="miniqmt", ttl=cache_ttl)

    def get_capabilities(self) -> set[DataCapability]:
        """返回 MiniQMT 支持的数据能力集合。

        基于 xtquant SDK 官方文档，MiniQMT 支持以下能力：
        - 实时行情：tick数据、分钟数据、快照等
        - 历史行情：K线数据、历史行情
        - 基础信息：合约信息、板块成分股、交易日历
        - 特色数据：资金流向、龙虎榜、北向资金、财务数据
        - 扩展数据：指数、行业、订单流
        """

        return {
            # 基础行情能力
            DataCapability.REALTIME_QUOTE,
            DataCapability.REALTIME_QUOTES,
            DataCapability.TICK_DATA,
            DataCapability.MINUTE_DATA,
            DataCapability.KLINE_DATA,
            # 基础信息能力
            DataCapability.STOCK_LIST,
            DataCapability.STOCK_INFO,
            DataCapability.ORDER_BOOK,
            DataCapability.TRADING_CALENDAR,
            # 特色数据能力
            DataCapability.CAPITAL_FLOW,
            DataCapability.DRAGON_TIGER,
            DataCapability.NORTH_FLOW,
            DataCapability.FINANCIAL_DATA,
            DataCapability.SECTOR_DATA,
            # 扩展数据能力
            DataCapability.INDEX_DATA,
            DataCapability.INDUSTRY_DATA,
            DataCapability.ORDER_FLOW,
        }

    # ==================== IDataFeed 接口兼容层 ====================

    @property
    def name(self) -> str:
        """数据源名称 (IDataFeed)"""
        return "miniqmt"

    @property
    def is_connected(self) -> bool:
        """是否已连接 (IDataFeed)"""
        return self.connected

    @staticmethod
    def normalize_symbol(symbol: str) -> str:
        """将任意格式转为 SDK 需要的格式 (IDataFeed)

        MiniQMT 使用后缀格式 (000001.SZ)
        """
        if not symbol:
            return symbol
        # 如果是前缀格式 (SH.600000)，转换为后缀格式
        if "." in symbol:
            parts = symbol.split(".")
            if len(parts) == 2 and parts[0].upper() in ("SH", "SZ", "BJ"):
                return f"{parts[1]}.{parts[0].upper()}"
        return symbol

    @staticmethod
    def standardize_symbol(symbol: str) -> str:
        """将 SDK 返回的格式转为标准后缀格式 (IDataFeed)"""
        return symbol  # 已是标准格式

    async def get_calendar(
        self,
        start: int | None = None,
        end: int | None = None,
    ) -> list[dict]:
        """获取交易日历 (IDataFeed)

        代理到 get_trading_calendar 方法。
        """
        start_str = str(start) if start else None
        end_str = str(end) if end else None
        result = await self.get_trading_calendar(start_date=start_str, end_date=end_str)
        if result:
            return [{"date": d} for d in result]
        return []

    async def get_kline(
        self,
        symbols: list[str],
        start: int,
        end: int,
        period: str = "daily",
        adjust: str | None = None,
    ) -> dict[str, list]:
        """获取K线数据 (IDataFeed)

        代理到 get_kline_data 方法。
        """
        result: dict[str, list] = {}
        period_map = {"daily": "1d", "1d": "1d", "weekly": "1w", "monthly": "1mo"}
        mapped_period = period_map.get(period, period)

        for symbol in symbols:
            data = await self.get_kline_data(
                symbol=self.normalize_symbol(symbol),
                period=mapped_period,
                start_date=str(start),
                end_date=str(end),
            )
            if data:
                result[symbol] = data
        return result

    async def get_realtime_quote(self, symbols: list[str]) -> dict[str, dict]:
        """获取实时行情 (IDataFeed)

        代理到 get_realtime_quotes 方法。
        """
        data = await self.get_realtime_quotes(symbols)
        if data:
            return {item["symbol"]: item for item in data}
        return {}

    # ==================== DataProvider 抽象方法实现 ====================

    async def initialize(self) -> bool:
        """
        初始化 MiniQMT 提供者

        实现 DataProvider 抽象方法，执行初始化和启动流程

        Returns:
            bool: 初始化是否成功
        """
        try:
            await self._initialize_source()
            await self._start_source()
            return True
        except DataProviderError as e:
            logger.error(f"MiniQMT 初始化失败: {e}")
            return False
        except Exception as e:
            logger.error(f"MiniQMT 初始化异常: {e}")
            return False

    async def get_stock_list(
        self, limit: Optional[int] = None, **kwargs: Any
    ) -> Optional[List[Dict[str, Any]]]:
        """
        获取股票列表

        实现 DataProvider 抽象方法

        Args:
            limit: 限制返回数量
            **kwargs: 其他参数

        Returns:
            股票列表，失败返回 None
        """
        if not self.connected:
            if not await self._connect():
                logger.error("MiniQMT 未连接，无法获取股票列表")
                return None

        # 发送股票列表请求
        query_msg = {"type": "QUERY_STOCK_LIST", "limit": limit or 0}

        if not await self._send_message(query_msg):
            logger.error("发送股票列表请求失败")
            return None

        try:
            response = await asyncio.wait_for(
                self._wait_for_response("STOCK_LIST"), timeout=self.config.timeout
            )

            if response and "data" in response:
                data = response["data"]
                if limit and limit > 0:
                    return cast(List[Dict[str, Any]], data[:limit])
                return cast(List[Dict[str, Any]], data)

        except asyncio.TimeoutError:
            logger.error("获取股票列表超时")

        return None

    async def get_kline_data(
        self,
        symbol: str,
        period: str = "1d",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100,
        **kwargs: Any,
    ) -> Optional[List[Dict[str, Any]]]:
        """
        获取 K 线数据

        实现 DataProvider 抽象方法

        Args:
            symbol: 股票代码
            period: 周期（1m, 5m, 15m, 30m, 60m, 1d, 1w）
            start_date: 开始日期
            end_date: 结束日期
            limit: 限制数量
            **kwargs: 其他参数

        Returns:
            K 线数据列表，失败返回 None
        """
        try:
            request = DataRequest(
                symbol=symbol,
                period=period,
                start_date=start_date,
                end_date=end_date,
            )

            df = await self._fetch_data(request)

            if df.empty:
                return None

            # 转换 DataFrame 为字典列表
            records = cast(List[Dict[str, Any]], df.reset_index().to_dict("records"))

            # 应用限制
            if limit and limit > 0:
                records = records[:limit]

            return records

        except DataProviderError as e:
            logger.error(f"获取 K 线数据失败: {e}")
            return None
        except Exception as e:
            logger.error(f"获取 K 线数据异常: {e}")
            return None

    async def get_realtime_quotes(
        self,
        symbols: List[str],
        **kwargs: Any,
    ) -> Optional[List[Dict[str, Any]]]:
        """
        获取实时行情数据

        Args:
            symbols: 股票代码列表
            **kwargs: 其他参数

        Returns:
            实时行情数据列表，失败返回 None
        """
        if not self.connected:
            if not await self._connect():
                logger.error("MiniQMT 未连接，无法获取实时行情")
                return None

        # 发送实时行情请求
        query_msg = {"type": "QUERY_REALTIME_QUOTES", "symbols": symbols}

        if not await self._send_message(query_msg):
            logger.error("发送实时行情请求失败")
            return None

        try:
            response = await asyncio.wait_for(
                self._wait_for_response("REALTIME_QUOTES"), timeout=self.config.timeout
            )

            if response and "data" in response:
                data = response["data"]
                # 标准化返回格式
                result = []
                for item in data:
                    result.append(
                        {
                            "symbol": item.get("code", ""),
                            "name": item.get("name", ""),
                            "price": float(item.get("lastPrice", 0) or 0),
                            "open": float(item.get("open", 0) or 0),
                            "high": float(item.get("high", 0) or 0),
                            "low": float(item.get("low", 0) or 0),
                            "prev_close": float(item.get("lastClose", 0) or 0),
                            "volume": float(item.get("volume", 0) or 0),
                            "amount": float(item.get("amount", 0) or 0),
                            "bid_price": float(item.get("bidPrice", 0) or 0),
                            "ask_price": float(item.get("askPrice", 0) or 0),
                            "timestamp": item.get("time", ""),
                            "source": "miniqmt",
                        }
                    )
                return result

        except asyncio.TimeoutError:
            logger.error("获取实时行情超时")

        return None

    async def get_order_book(
        self,
        symbol: str,
        depth: int = 5,
        **kwargs: Any,
    ) -> Optional[Dict[str, Any]]:
        """
        获取盘口数据

        Args:
            symbol: 股票代码
            depth: 盘口深度 (默认5档)
            **kwargs: 其他参数

        Returns:
            盘口数据，失败返回 None
        """
        if not self.connected:
            if not await self._connect():
                logger.error("MiniQMT 未连接，无法获取盘口数据")
                return None

        # 发送盘口请求
        query_msg = {"type": "QUERY_ORDER_BOOK", "symbol": symbol, "depth": depth}

        if not await self._send_message(query_msg):
            logger.error("发送盘口请求失败")
            return None

        try:
            response = await asyncio.wait_for(
                self._wait_for_response("ORDER_BOOK"), timeout=self.config.timeout
            )

            if response and "data" in response:
                data = response["data"]
                return {
                    "symbol": symbol,
                    "bids": data.get("bids", []),  # [[price, volume], ...]
                    "asks": data.get("asks", []),  # [[price, volume], ...]
                    "timestamp": data.get("time", ""),
                    "source": "miniqmt",
                }

        except asyncio.TimeoutError:
            logger.error("获取盘口数据超时")

        return None

    # ==================== xtquant SDK 扩展接口 ====================

    async def get_stock_info(
        self,
        symbol: str,
        **kwargs: Any,
    ) -> Optional[Dict[str, Any]]:
        """
        获取股票详细信息（合约基础信息）

        使用 xtdata.get_instrument_detail() 获取合约详情，包括：
        - 上市日期、退市日期
        - 涨跌停价格
        - 流通股本、总股本
        - 价格最小变动单位

        Args:
            symbol: 股票代码（如 000001.SZ）
            **kwargs: 其他参数

        Returns:
            股票信息字典，失败返回 None
        """
        if not XTDATA_AVAILABLE:
            logger.warning("xtquant SDK 未安装，回退到 socket 连接")
        else:
            try:
                # 获取合约详情
                detail = xtdata.get_instrument_detail(symbol)

                if detail:
                    return {
                        "symbol": symbol,
                        "name": detail.get("InstrumentName", ""),
                        "exchange": detail.get("ExchangeID", ""),
                        "open_date": detail.get("OpenDate", ""),
                        "expire_date": detail.get("ExpireDate"),
                        "prev_close": float(detail.get("PreClose", 0) or 0),
                        "up_limit": float(detail.get("UpStopPrice", 0) or 0),
                        "down_limit": float(detail.get("DownStopPrice", 0) or 0),
                        "float_volume": float(detail.get("FloatVolume", 0) or 0),
                        "total_volume": float(detail.get("TotalVolume", 0) or 0),
                        "price_tick": float(detail.get("PriceTick", 0.01) or 0.01),
                        "volume_multiple": int(detail.get("VolumeMultiple", 1) or 1),
                        "is_trading": detail.get("IsTrading", False),
                        "source": "miniqmt",
                    }

            except Exception as e:
                logger.error(f"获取股票信息失败: {e}")

        # 如果 xtquant 不可用，使用 socket 连接
        if not self.connected:
            if not await self._connect():
                logger.error("MiniQMT 未连接，无法获取股票信息")
                return None

        query_msg = {"type": "QUERY_STOCK_INFO", "symbol": symbol}
        if not await self._send_message(query_msg):
            return None

        try:
            response = await asyncio.wait_for(
                self._wait_for_response("STOCK_INFO"), timeout=self.config.timeout
            )
            if response and "data" in response:
                return cast(Dict[str, Any], response["data"])
        except asyncio.TimeoutError:
            logger.error("获取股票信息超时")

        return None

    async def get_capital_flow(
        self,
        symbol: str,
        period: str = "1d",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        **kwargs: Any,
    ) -> Optional[List[Dict[str, Any]]]:
        """
        获取股票资金流向数据

        使用 xtdata.get_market_data_ex() 获取资金流向：
        - period='transactioncount1d' 日级别资金流向
        - period='transactioncount1m' 分钟级别资金流向

        Args:
            symbol: 股票代码
            period: 周期 ('1d' 或 '1m')
            start_date: 开始日期
            end_date: 结束日期
            **kwargs: 其他参数

        Returns:
            资金流向数据列表，失败返回 None
        """
        try:
            # 映射周期参数
            period_map = {
                "1d": "transactioncount1d",
                "1m": "transactioncount1m",
            }
            xt_period = period_map.get(period, "transactioncount1d")

            # 获取资金流向数据
            data = xtdata.get_market_data_ex(
                fields=[],
                stock_list=[symbol],
                period=xt_period,
                start_time=start_date or "",
                end_time=end_date or "",
            )

            if data and symbol in data:
                df = data[symbol]
                if not df.empty:
                    records = df.reset_index().to_dict("records")
                    # 标准化返回格式
                    result = []
                    for item in records:
                        result.append(
                            {
                                "symbol": symbol,
                                "date": item.get("time", item.get("index", "")),
                                "large_inflow": float(item.get("largeInflow", 0) or 0),
                                "large_outflow": float(item.get("largeOutflow", 0) or 0),
                                "medium_inflow": float(item.get("mediumInflow", 0) or 0),
                                "medium_outflow": float(item.get("mediumOutflow", 0) or 0),
                                "small_inflow": float(item.get("smallInflow", 0) or 0),
                                "small_outflow": float(item.get("smallOutflow", 0) or 0),
                                "source": "miniqmt",
                            }
                        )
                    return result

        # xtquant SDK 检查已在模块导入时完成
        except Exception as e:
            logger.error(f"获取资金流向失败: {e}")

        return None

    async def get_dragon_tiger(
        self,
        date: Optional[str] = None,
        symbols: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> Optional[List[Dict[str, Any]]]:
        """
        获取龙虎榜数据

        由于 xtquant SDK 没有标准的龙虎榜 API，此方法通过 AkShare 获取数据

        Args:
            date: 查询日期 (格式: YYYYMMDD)，为空获取最新数据
            symbols: 股票代码列表（可选，用于过滤结果）
            **kwargs: 其他参数

        Returns:
            龙虎榜数据列表，失败返回 None

        Note:
            数据来源于 AkShare，非 xtquant SDK 原生数据
        """
        try:
            logger.info(f"龙虎榜查询: date={date}, symbols={len(symbols) if symbols else 'all'}")

            # 尝试从 AkShare 获取龙虎榜数据
            try:
                # 延迟导入避免循环依赖
                from apps.api.api.providers import DataProviderFactory, DataSourceType

                akshare_provider = await DataProviderFactory.get_provider_async(
                    DataSourceType.AKSHARE
                )

                # 调用 AkShare 的龙虎榜接口
                # stock_lhb_detail_em - 东方财富龙虎榜详情
                params: Dict[str, Any] = {}
                if date:
                    # 转换日期格式: YYYYMMDD -> YYYY-MM-DD
                    formatted_date = f"{date[:4]}-{date[4:6]}-{date[6:8]}"
                    params["start_date"] = formatted_date
                    params["end_date"] = formatted_date

                result = await akshare_provider.call_api(
                    api_name="stock_lhb_detail_em",
                    params=params,
                )

                if result is not None:
                    # 将 DataFrame 转换为字典列表
                    if hasattr(result, "to_dict"):
                        records = result.to_dict("records")
                    elif isinstance(result, list):
                        records = result
                    elif isinstance(result, dict) and "data" in result:
                        records = result["data"]
                    else:
                        records = []

                    # 如果指定了股票代码，过滤结果
                    if symbols and records:
                        # 尝试匹配股票代码字段
                        filtered = []
                        for record in records:
                            code = record.get("代码") or record.get("symbol") or record.get("code")
                            if code and any(s in str(code) for s in symbols):
                                filtered.append(record)
                        records = filtered

                    # 添加数据来源标记
                    for record in records:
                        record["source"] = "akshare"
                        record["data_type"] = "dragon_tiger"

                    logger.info(f"获取龙虎榜成功: {len(records)} 条记录 (来源: AkShare)")
                    return records

            except ImportError:
                logger.warning("AkShare 模块未找到，无法获取龙虎榜数据")
            except Exception as akshare_err:
                logger.warning(f"从 AkShare 获取龙虎榜失败: {akshare_err}")

            # 如果 AkShare 失败，返回空列表
            logger.warning("龙虎榜数据获取失败，xtquant SDK 不支持此功能")
            return []

        except Exception as e:
            logger.error(f"获取龙虎榜失败: {e}")

        return None

    async def get_limit_up_performance(
        self,
        symbols: List[str],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        **kwargs: Any,
    ) -> Optional[List[Dict[str, Any]]]:
        """
        获取涨跌表现数据（连板、封板等）

        使用 xtdata.get_market_data_ex() 获取涨跌表现数据
        period='limitupperformance'

        返回字段说明:
        - openVol: 开盘集合竞价成交量
        - closeVol: 收盘集合竞价成交量
        - startUp: 涨停开始时间
        - endUp: 涨停结束时间
        - breakUp: 炸板次数
        - upAmount: 涨停金额
        - startDn: 跌停开始时间
        - endDn: 跌停结束时间
        - breakDn: 跌停开板次数
        - dnAmount: 跌停金额
        - direct: 涨跌方向 (0-无, 1-涨停, 2-跌停)
        - sealVolRatio: 封成比
        - sealFreeRatio: 封流比
        - sealCount: 连板数

        Args:
            symbols: 股票代码列表
            start_date: 开始日期 (格式: YYYYMMDD)
            end_date: 结束日期 (格式: YYYYMMDD)
            **kwargs: 其他参数

        Returns:
            涨跌表现数据列表，失败返回 None

        Note:
            此功能需要 MiniQMT 投研版 VIP 权限
        """
        try:
            logger.info(f"涨跌表现查询: symbols={len(symbols)}, start={start_date}, end={end_date}")

            # 获取涨跌表现数据
            data = xtdata.get_market_data_ex(
                fields=[],  # 空列表获取所有字段
                stock_list=symbols,
                period="limitupperformance",
                start_time=start_date or "",
                end_time=end_date or "",
            )

            if data:
                result = []
                for symbol, df in data.items():
                    if df is not None and not df.empty:
                        # 转换 DataFrame 为字典列表
                        records = df.reset_index().to_dict("records")
                        for record in records:
                            record["symbol"] = symbol
                            record["source"] = "miniqmt"
                            record["data_type"] = "limit_up_performance"
                        result.extend(records)

                if result:
                    logger.info(f"获取涨跌表现成功: {len(result)} 条记录")
                    return result

            # 如果无法获取数据，返回空列表
            logger.warning("涨跌表现数据为空，可能需要 VIP 权限")
            return []

        except Exception as e:
            logger.error(f"获取涨跌表现失败: {e}")

        return None

    async def get_north_flow(
        self,
        symbols: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        period: str = "1d",
        **kwargs: Any,
    ) -> Optional[List[Dict[str, Any]]]:
        """
        获取北向资金流向数据（沪港通/深港通）

        使用 xtdata.get_market_data_ex() 获取北向资金数据
        period='northfinancechange1d' (日级) 或 'northfinancechange1m' (分钟级)

        Args:
            symbols: 股票代码列表（可选，为空获取市场整体数据）
            start_date: 开始日期 (格式: YYYYMMDD)
            end_date: 结束日期 (格式: YYYYMMDD)
            period: 周期类型 ('1m' 分钟级, '1d' 日级)
            **kwargs: 其他参数

        Returns:
            北向资金数据列表，失败返回 None

        Note:
            此功能需要 MiniQMT 投研版 VIP 权限
        """
        try:
            # 周期映射
            period_map = {
                "1m": "northfinancechange1m",
                "1d": "northfinancechange1d",
            }
            xt_period = period_map.get(period, "northfinancechange1d")

            # 如果没有指定股票，获取沪深A股前100只作为示例
            if not symbols:
                symbols = xtdata.get_stock_list_in_sector("沪深A股")[:100]

            # 获取北向资金数据
            data = xtdata.get_market_data_ex(
                fields=[],  # 空列表获取所有字段
                stock_list=symbols,
                period=xt_period,
                start_time=start_date or "",
                end_time=end_date or "",
            )

            if data:
                result = []
                for symbol, df in data.items():
                    if df is not None and not df.empty:
                        # 转换 DataFrame 为字典列表
                        records = df.reset_index().to_dict("records")
                        for record in records:
                            record["symbol"] = symbol
                            record["source"] = "miniqmt"
                            record["period"] = period
                        result.extend(records)

                if result:
                    logger.info(f"获取北向资金成功: {len(result)} 条记录")
                    return result

            # 如果无法获取数据，返回空列表（表示功能可用但无数据或无权限）
            logger.warning("北向资金数据为空，可能需要 VIP 权限")
            return []

        except Exception as e:
            logger.error(f"获取北向资金失败: {e}")

        return None

    async def get_trading_calendar(
        self,
        market: str = "SH",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        **kwargs: Any,
    ) -> Optional[List[str]]:
        """
        获取交易日历

        使用 xtdata.get_trading_dates() 获取交易日历

        Args:
            market: 市场 ('SH'上海, 'SZ'深圳, 'HGT'沪港通等)
            start_date: 开始日期
            end_date: 结束日期
            **kwargs: 其他参数

        Returns:
            交易日列表，失败返回 None
        """
        try:
            trading_dates = xtdata.get_trading_dates(
                market=market,
                start_time=start_date or "",
                end_time=end_date or "",
            )

            if trading_dates:
                # 转换时间戳为日期字符串
                from datetime import datetime

                result = []
                for ts in trading_dates:
                    if isinstance(ts, int):
                        dt = datetime.fromtimestamp(ts / 1000)
                        result.append(dt.strftime("%Y%m%d"))
                    else:
                        result.append(str(ts))
                return result

        # xtquant SDK 检查已在模块导入时完成
        except Exception as e:
            logger.error(f"获取交易日历失败: {e}")

        return None

    async def get_sector_stocks(
        self,
        sector_name: str = "沪深A股",
        **kwargs: Any,
    ) -> Optional[List[str]]:
        """
        获取板块成分股列表

        使用 xtdata.get_stock_list_in_sector() 获取板块成分股

        Args:
            sector_name: 板块名称（如"沪深A股"、"上证50"等）
            **kwargs: 其他参数

        Returns:
            股票代码列表，失败返回 None
        """
        try:
            stocks = xtdata.get_stock_list_in_sector(sector_name)
            if stocks:
                return list(stocks)

        # xtquant SDK 检查已在模块导入时完成
        except Exception as e:
            logger.error(f"获取板块成分股失败: {e}")

        return None

    async def get_financial_data(
        self,
        symbols: List[str],
        tables: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        report_type: str = "report_time",
        auto_download: bool = True,
        **kwargs: Any,
    ) -> Optional[Dict[str, Dict[str, Any]]]:
        """
        获取财务数据

        使用 xtdata.get_financial_data() 获取财务数据

        支持的财务表:
        - Balance: 资产负债表
        - Income: 利润表
        - CashFlow: 现金流量表
        - Capital: 股本结构表
        - Holdernum: 股东数
        - Top10holder: 十大股东
        - Top10flowholder: 十大流通股东
        - Pershareindex: 每股指标

        Args:
            symbols: 股票代码列表
            tables: 财务表列表（为空获取全部）
            start_date: 开始日期 (格式: YYYYMMDD)
            end_date: 结束日期 (格式: YYYYMMDD)
            report_type: 报告类型 ('report_time'截止日期, 'announce_time'披露日期)
            auto_download: 是否自动下载数据到本地缓存
            **kwargs: 其他参数

        Returns:
            财务数据字典，格式: {symbol: {table_name: DataFrame_dict}}
            失败返回 None

        Note:
            此功能需要 MiniQMT 投研版 VIP 权限
        """
        try:
            # 默认获取三大财务报表
            table_list = tables or ["Balance", "Income", "CashFlow"]

            logger.info(
                f"财务数据查询: symbols={len(symbols)}, tables={table_list}, "
                f"start={start_date}, end={end_date}, report_type={report_type}"
            )

            # 自动下载财务数据到本地缓存
            if auto_download:
                try:
                    # 转换为 list 避免类型问题
                    symbol_list_copy = list(symbols)
                    table_list_copy = list(table_list)
                    await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: xtdata.download_financial_data(symbol_list_copy, table_list_copy),
                    )
                    logger.debug(f"财务数据下载完成: {len(symbols)} 只股票")
                except Exception as download_err:
                    logger.warning(f"财务数据下载失败（将尝试读取缓存）: {download_err}")

            # 获取财务数据
            symbol_list_final = list(symbols)
            table_list_final = list(table_list) if table_list else None
            start_time_param = start_date or ""
            end_time_param = end_date or ""
            report_type_param = report_type

            data = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: xtdata.get_financial_data(
                    stock_list=symbol_list_final,
                    table_list=table_list_final,
                    start_time=start_time_param,
                    end_time=end_time_param,
                    report_type=report_type_param,
                ),
            )

            if data:
                # 转换结果格式
                result: Dict[str, Dict[str, Any]] = {}
                for symbol, tables_data in data.items():
                    if tables_data:
                        result[symbol] = {}
                        for table_name, df in tables_data.items():
                            if df is not None and not df.empty:
                                # 将 DataFrame 转换为可序列化的字典
                                result[symbol][table_name] = {
                                    "columns": list(df.columns),
                                    "data": df.values.tolist(),
                                    "index": [str(idx) for idx in df.index.tolist()],
                                    "count": len(df),
                                }
                            else:
                                result[symbol][table_name] = {
                                    "columns": [],
                                    "data": [],
                                    "index": [],
                                    "count": 0,
                                }

                if result:
                    logger.info(f"获取财务数据成功: {len(result)} 只股票")
                    return result

            # 如果无法获取数据，返回空字典
            logger.warning("财务数据为空，可能需要 VIP 权限或数据未下载")
            return {}

        except Exception as e:
            logger.error(f"获取财务数据失败: {e}")

        return None

    async def get_index_weight(
        self,
        index_code: str,
        **kwargs: Any,
    ) -> Optional[Dict[str, float]]:
        """
        获取指数成分股权重

        使用 xtdata.get_index_weight() 获取指数成分股权重

        Args:
            index_code: 指数代码（如 000300.SH 沪深300）
            **kwargs: 其他参数

        Returns:
            字典，key 为成分股代码，value 为权重
        """
        try:
            weight = xtdata.get_index_weight(index_code)
            if weight:
                return dict(weight)

        # xtquant SDK 检查已在模块导入时完成
        except Exception as e:
            logger.error(f"获取指数权重失败: {e}")

        return None

    async def get_sector_list(
        self,
        **kwargs: Any,
    ) -> Optional[List[str]]:
        """
        获取板块分类列表

        使用 xtdata.get_sector_list() 获取所有板块列表

        Args:
            **kwargs: 其他参数

        Returns:
            板块名称列表
        """
        try:
            sectors = xtdata.get_sector_list()
            if sectors:
                return list(sectors)

        # xtquant SDK 检查已在模块导入时完成
        except Exception as e:
            logger.error(f"获取板块列表失败: {e}")

        return None

    async def get_order_flow(
        self,
        symbol: str,
        period: str = "1m",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        **kwargs: Any,
    ) -> Optional[List[Dict[str, Any]]]:
        """
        获取股票订单流数据

        使用 xtdata.get_market_data_ex() 获取订单流数据
        period='orderflow1m' 或 'orderflow1d'

        Args:
            symbol: 股票代码
            period: 周期 ('1m' 或 '1d')
            start_date: 开始日期
            end_date: 结束日期
            **kwargs: 其他参数

        Returns:
            订单流数据列表
        """
        try:
            period_map = {"1m": "orderflow1m", "1d": "orderflow1d"}
            xt_period = period_map.get(period, "orderflow1m")

            data = xtdata.get_market_data_ex(
                fields=[],
                stock_list=[symbol],
                period=xt_period,
                start_time=start_date or "",
                end_time=end_date or "",
            )

            if data and symbol in data:
                df = data[symbol]
                if not df.empty:
                    return cast(List[Dict[str, Any]], df.reset_index().to_dict("records"))

        # xtquant SDK 检查已在模块导入时完成
        except Exception as e:
            logger.error(f"获取订单流数据失败: {e}")

        return None

    async def download_sector_data(self, **kwargs: Any) -> bool:
        """
        下载板块分类信息

        使用 xtdata.download_sector_data() 下载板块数据

        Returns:
            是否下载成功
        """
        try:
            xtdata.download_sector_data()
            logger.info("板块分类数据下载完成")
            return True

        # xtquant SDK 检查已在模块导入时完成
        except Exception as e:
            logger.error(f"下载板块数据失败: {e}")

        return False

    async def _initialize_source(self) -> None:
        """初始化 MiniQMT 数据源"""
        # 从配置加载连接参数
        from core.config import get_config

        config = get_config()

        miniqmt_config: Any = getattr(config, "miniqmt", None)
        connection: Any = None

        if isinstance(miniqmt_config, dict):
            connection = miniqmt_config.get("connection")
            self.host = str(miniqmt_config.get("host", self.host))
            self.port = int(miniqmt_config.get("port", self.port))
        elif miniqmt_config is not None:
            connection = getattr(miniqmt_config, "connection", None)

        if connection is not None:
            self.host = str(getattr(connection, "host", self.host))
            self.port = int(getattr(connection, "port", self.port))
            self.username = str(getattr(connection, "username", self.username))
            self.password = str(getattr(connection, "password", self.password))

        logger.info(f"MiniQMT 配置: {self.host}:{self.port}")

    async def _start_source(self) -> None:
        """启动 MiniQMT 连接"""
        # 连接到 MiniQMT
        if not await self._connect():
            raise DataProviderError(
                f"无法连接到 MiniQMT 终端 ({self.host}:{self.port})，"
                "请确保 QMT 量化终端已启动并监听正确端口"
            )

        # 启动心跳任务
        self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        # 启动数据接收任务
        self.receive_task = asyncio.create_task(self._receive_loop())

        logger.info("MiniQMT 数据源已启动")

    async def _stop_source(self) -> None:
        """停止 MiniQMT 连接"""
        # 取消任务
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
            try:
                await self.heartbeat_task
            except asyncio.CancelledError:
                pass

        if self.receive_task:
            self.receive_task.cancel()
            try:
                await self.receive_task
            except asyncio.CancelledError:
                pass

        # 断开连接
        await self._disconnect()

        logger.info("MiniQMT 数据源已停止")

    async def _connect(self) -> bool:
        """连接到 MiniQMT 服务器"""
        try:
            if self.socket:
                self.socket.close()

            # 创建 socket 连接
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(5.0)

            # 连接到服务器
            await asyncio.get_event_loop().run_in_executor(
                None, self.socket.connect, (self.host, self.port)
            )

            # 发送认证信息
            if self.username:
                auth_msg = {
                    "type": "AUTH",
                    "username": self.username,
                    "password": self.password,
                    "client": "DeepSearch",
                    "version": "1.0.0",
                }

                if await self._send_message(auth_msg):
                    # 等待认证响应
                    response = await self._receive_message()
                    if response and response.get("status") == "OK":
                        self.connected = True
                        self.reconnect_attempts = 0
                        logger.info(f"成功连接到 MiniQMT 服务器 {self.host}:{self.port}")
                        return True
                    else:
                        logger.error(f"MiniQMT 认证失败: {response}")
                        return False
            else:
                # 无需认证
                self.connected = True
                self.reconnect_attempts = 0
                logger.info(f"成功连接到 MiniQMT 服务器 {self.host}:{self.port}")
                return True

        except Exception as e:
            logger.error(f"连接 MiniQMT 失败: {e}")
            self.connected = False
            return False

        return False

    async def _disconnect(self) -> None:
        """断开 MiniQMT 连接"""
        if self.socket:
            try:
                # 发送断开消息
                disconnect_msg = {"type": "DISCONNECT"}
                await self._send_message(disconnect_msg)
            except Exception:
                pass

            self.socket.close()
            self.socket = None

        self.connected = False
        logger.info("已断开 MiniQMT 连接")

    async def _reconnect(self) -> bool:
        """重新连接 MiniQMT"""
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            logger.error("达到最大重连次数，停止重连")
            return False

        self.reconnect_attempts += 1
        logger.info(f"尝试重新连接 MiniQMT (第{self.reconnect_attempts}次)")

        # 断开现有连接
        await self._disconnect()

        # 等待一段时间
        await asyncio.sleep(self.config.retry_delay * self.reconnect_attempts)

        # 尝试重新连接
        if await self._connect():
            # 重新订阅
            if self.subscribed_symbols:
                await self._subscribe_symbols(list(self.subscribed_symbols))
            return True

        return False

    async def _send_message(self, msg: Dict) -> bool:
        """发送消息到 MiniQMT"""
        if not self.socket:
            return False

        try:
            data = json.dumps(msg).encode("utf-8")
            length = struct.pack("!I", len(data))

            await asyncio.get_event_loop().run_in_executor(None, self.socket.sendall, length + data)

            return True

        except Exception as e:
            logger.error(f"发送消息失败: {e}")
            self.connected = False
            return False

    async def _receive_message(self) -> Optional[Dict]:
        """接收 MiniQMT 消息"""
        if not self.socket:
            return None

        try:
            # 读取消息长度
            length_data = await asyncio.get_event_loop().run_in_executor(None, self.socket.recv, 4)
            if not length_data:
                return None

            length = struct.unpack("!I", length_data)[0]

            # 读取消息内容
            data = await asyncio.get_event_loop().run_in_executor(None, self.socket.recv, length)

            return cast(Dict[str, Any], json.loads(data.decode("utf-8")))

        except Exception as e:
            logger.error(f"接收消息失败: {e}")
            return None

    async def _heartbeat_loop(self) -> None:
        """心跳循环"""
        while True:
            try:
                await asyncio.sleep(self.heartbeat_interval)

                if self.connected:
                    # 发送心跳
                    heartbeat_msg = {"type": "HEARTBEAT", "timestamp": time.time()}

                    if not await self._send_message(heartbeat_msg):
                        # 心跳失败，尝试重连
                        await self._reconnect()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"心跳异常: {e}")

    async def _receive_loop(self) -> None:
        """数据接收循环"""
        while True:
            try:
                if not self.connected:
                    await asyncio.sleep(1)
                    continue

                # 接收消息
                msg = await self._receive_message()
                if msg:
                    await self._process_message(msg)
                else:
                    # 连接可能断开
                    if self.connected:
                        logger.warning("接收到空消息，尝试重连")
                        await self._reconnect()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"接收数据异常: {e}")
                await asyncio.sleep(1)

    async def _process_message(self, msg: Dict[str, Any]) -> None:
        """处理接收到的消息"""
        msg_type = msg.get("type")

        if msg_type == "TICK":
            # 处理 tick 数据
            data = msg.get("data")
            if isinstance(data, dict):
                await self._process_tick_data(data)
        elif msg_type == "KLINE":
            # 处理 K线数据
            data = msg.get("data")
            if isinstance(data, dict):
                await self._process_kline_data(data)
        elif msg_type == "ORDERBOOK":
            # 处理盘口数据
            data = msg.get("data")
            if isinstance(data, dict):
                await self._process_orderbook_data(data)
        elif msg_type == "HEARTBEAT":
            # 心跳响应
            self.last_heartbeat = time.time()
        elif msg_type == "ERROR":
            # 错误消息
            logger.error(f"MiniQMT 错误: {msg.get('message')}")

    async def _process_tick_data(self, data: Dict[str, Any]) -> None:
        """处理 tick 数据"""
        if not data:
            return

        # 将数据放入队列
        await self.data_queue.put({"type": "tick", "data": data, "timestamp": time.time()})

        # 触发回调
        symbol = data.get("symbol")
        if symbol in self.symbol_callbacks:
            for callback in self.symbol_callbacks[symbol]:
                result = callback(data)
                if inspect.isawaitable(result):
                    await result

    async def _process_kline_data(self, data: Dict[str, Any]) -> None:
        """处理 K线数据"""
        if not data:
            return

        # 将数据放入队列
        await self.data_queue.put({"type": "kline", "data": data, "timestamp": time.time()})

    async def _process_orderbook_data(self, data: Dict[str, Any]) -> None:
        """处理盘口数据"""
        if not data:
            return

        # 将数据放入队列
        await self.data_queue.put({"type": "orderbook", "data": data, "timestamp": time.time()})

    async def _subscribe_symbols(self, symbols: List[str]) -> bool:
        """订阅股票行情"""
        if not self.connected:
            return False

        # 发送订阅请求
        subscribe_msg = {
            "type": "SUBSCRIBE",
            "symbols": symbols,
            "data_types": ["tick", "orderbook"],  # 订阅 tick 和盘口数据
        }

        if await self._send_message(subscribe_msg):
            # 更新订阅列表
            self.subscribed_symbols.update(symbols)
            logger.info(f"订阅 MiniQMT 行情: {symbols}")
            return True

        return False

    async def _unsubscribe_symbols(self, symbols: List[str]) -> bool:
        """取消订阅股票行情"""
        if not self.connected:
            return False

        # 发送取消订阅请求
        unsubscribe_msg = {"type": "UNSUBSCRIBE", "symbols": symbols}

        if await self._send_message(unsubscribe_msg):
            # 更新订阅列表
            for symbol in symbols:
                self.subscribed_symbols.discard(symbol)
            logger.info(f"取消订阅 MiniQMT 行情: {symbols}")
            return True

        return False

    async def _fetch_data(self, request: DataRequest) -> pd.DataFrame:
        """
        获取数据的具体实现

        Args:
            request: 数据请求

        Returns:
            数据 DataFrame
        """
        if not self.connected:
            # 尝试连接
            if not await self._connect():
                raise DataProviderError("无法连接到 MiniQMT")

        # 根据请求类型获取数据
        if request.period == "tick":
            # 获取实时数据
            return await self._fetch_realtime_data(request)
        elif request.period in ["1m", "5m", "15m", "30m", "60m"]:
            # 获取分钟数据
            return await self._fetch_minute_data(request)
        else:
            # 获取日线数据
            return await self._fetch_daily_data(request)

    async def _fetch_realtime_data(self, request: DataRequest) -> pd.DataFrame:
        """获取实时数据"""
        symbols = request.symbols or [request.symbol] if request.symbol else []
        if not symbols:
            return pd.DataFrame()

        # 发送实时数据请求
        query_msg = {"type": "QUERY_REALTIME", "symbols": symbols}

        if not await self._send_message(query_msg):
            raise DataProviderError("发送请求失败")

        # 等待响应（超时处理）
        try:
            response = await asyncio.wait_for(
                self._wait_for_response("REALTIME_DATA"), timeout=self.config.timeout
            )

            if response and "data" in response:
                # 转换为 DataFrame
                df = pd.DataFrame(response["data"])
                return df

        except asyncio.TimeoutError:
            raise DataProviderError("获取实时数据超时")

        return pd.DataFrame()

    async def _fetch_minute_data(self, request: DataRequest) -> pd.DataFrame:
        """获取分钟数据"""
        if not request.symbol:
            return pd.DataFrame()

        # 发送分钟数据请求
        query_msg = {
            "type": "QUERY_MINUTE",
            "symbol": request.symbol,
            "period": request.period,
            "start_date": str(request.start_date) if request.start_date else None,
            "end_date": str(request.end_date) if request.end_date else None,
        }

        if not await self._send_message(query_msg):
            raise DataProviderError("发送请求失败")

        # 等待响应
        try:
            response = await asyncio.wait_for(
                self._wait_for_response("MINUTE_DATA"), timeout=self.config.timeout
            )

            if response and "data" in response:
                # 转换为 DataFrame
                df = pd.DataFrame(response["data"])
                if "datetime" in df.columns:
                    df["datetime"] = pd.to_datetime(df["datetime"])
                    df.set_index("datetime", inplace=True)
                return df

        except asyncio.TimeoutError:
            raise DataProviderError("获取分钟数据超时")

        return pd.DataFrame()

    async def _fetch_daily_data(self, request: DataRequest) -> pd.DataFrame:
        """获取日线数据"""
        if not request.symbol:
            return pd.DataFrame()

        # 发送日线数据请求
        query_msg = {
            "type": "QUERY_DAILY",
            "symbol": request.symbol,
            "start_date": str(request.start_date) if request.start_date else None,
            "end_date": str(request.end_date) if request.end_date else None,
            "adjust": request.adjust,
        }

        if not await self._send_message(query_msg):
            raise DataProviderError("发送请求失败")

        # 等待响应
        try:
            response = await asyncio.wait_for(
                self._wait_for_response("DAILY_DATA"), timeout=self.config.timeout
            )

            if response and "data" in response:
                # 转换为 DataFrame
                df = pd.DataFrame(response["data"])
                if "date" in df.columns:
                    df["date"] = pd.to_datetime(df["date"])
                    df.set_index("date", inplace=True)
                return df

        except asyncio.TimeoutError:
            raise DataProviderError("获取日线数据超时")

        return pd.DataFrame()

    async def _wait_for_response(self, response_type: str) -> Optional[Dict]:
        """等待特定类型的响应"""
        start_time = time.time()

        while time.time() - start_time < self.config.timeout:
            if not self.connected:
                return None

            # 接收消息
            msg = await self._receive_message()
            if msg and msg.get("type") == response_type:
                return msg

            await asyncio.sleep(0.1)

        return None

    # 公共 API 方法

    async def subscribe(self, symbols: List[str]) -> bool:
        """
        订阅股票行情

        Args:
            symbols: 股票代码列表

        Returns:
            是否成功
        """
        return await self._subscribe_symbols(symbols)

    async def unsubscribe(self, symbols: List[str]) -> bool:
        """
        取消订阅股票行情

        Args:
            symbols: 股票代码列表

        Returns:
            是否成功
        """
        return await self._unsubscribe_symbols(symbols)

    async def get_data(self, request: DataRequest) -> DataResponse:
        """按照 `DataRequest` 获取数据并封装响应。"""

        metadata = {
            "source": self.config.name or "miniqmt",
            "request_type": request.request_type,
        }

        try:
            dataframe = await self._fetch_data(request)
        except DataProviderError as exc:
            return DataResponse(success=False, error=str(exc), metadata=metadata)
        except Exception as exc:  # pragma: no cover - 防御日志
            logger.exception("MiniQMT 获取数据异常: {}", exc)
            return DataResponse(success=False, error=str(exc), metadata=metadata)

        return DataResponse(success=True, data=dataframe, metadata=metadata)

    def add_symbol_callback(self, symbol: str, callback) -> None:
        """
        添加股票数据回调

        Args:
            symbol: 股票代码
            callback: 回调函数
        """
        if symbol not in self.symbol_callbacks:
            self.symbol_callbacks[symbol] = []
        self.symbol_callbacks[symbol].append(callback)

    def remove_symbol_callback(self, symbol: str, callback) -> None:
        """
        移除股票数据回调

        Args:
            symbol: 股票代码
            callback: 回调函数
        """
        if symbol in self.symbol_callbacks:
            try:
                self.symbol_callbacks[symbol].remove(callback)
            except ValueError:
                pass

    def get_connection_status(self) -> Dict[str, Any]:
        """获取连接状态"""
        return {
            "connected": self.connected,
            "host": self.host,
            "port": self.port,
            "subscribed_symbols": list(self.subscribed_symbols),
            "last_heartbeat": self.last_heartbeat,
            "reconnect_attempts": self.reconnect_attempts,
            "queue_size": self.data_queue.qsize(),
        }
