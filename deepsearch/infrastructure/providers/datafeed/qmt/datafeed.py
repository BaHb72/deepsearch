"""
QMT DataFeed 实现

实现 IDataFeed 接口，提供统一的数据访问接口
"""
from typing import Any, Dict, List

from loguru import logger

from deepsearch.infrastructure.providers.datafeed.base import IDataFeed, KlineParams
from .provider import QMTDataProvider

try:
    import pandas as pd

    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False
    pd = None


class QMTDataFeed(IDataFeed):
    """QMT 数据源实现"""

    def __init__(self):
        """初始化 QMT DataFeed"""
        self.provider = QMTDataProvider()
        self.initialized = False

    async def initialize(self):
        """初始化连接"""
        if not self.initialized:
            await self.provider.initialize()
            self.initialized = True
            logger.info("QMT DataFeed 初始化完成")

    async def get_kline(self, params: KlineParams):
        """
        获取K线数据
        
        Args:
            params: K线参数
            
        Returns:
            DataFrame 或 List[Dict] 格式的K线数据
        """
        if not self.initialized:
            await self.initialize()

        # 转换周期格式
        period_map = {
            "1m": "1",
            "3m": "3",
            "5m": "5",
            "15m": "15",
            "30m": "30",
            "60m": "60",
            "1d": "daily",
            "1w": "weekly",
            "1mo": "monthly"
        }

        period = period_map.get(params.timeframe, params.timeframe)

        # 调用provider获取数据
        result = await self.provider.get_stock_hist(
            symbol=params.symbol,
            period=period,
            start_date=params.start_date,
            end_date=params.end_date,
            adjust=params.adjust
        )

        if result.get("error"):
            logger.error(f"QMT 获取K线失败: {result['error']}")
            return []

        data = result.get("data", [])

        # 标准化数据格式
        return self.normalize_bars(data)

    async def get_realtime(self, symbols: List[str]) -> Dict[str, Any]:
        """
        获取实时行情
        
        Args:
            symbols: 股票代码列表
            
        Returns:
            实时行情数据字典
        """
        if not self.initialized:
            await self.initialize()

        quotes = {}

        for symbol in symbols:
            try:
                quote = await self.provider.get_realtime_quote(symbol)
                if not quote.get("error"):
                    quotes[symbol] = {
                        "symbol": symbol,
                        "name": quote.get("name", ""),
                        "price": quote.get("current", 0),
                        "open": quote.get("open", 0),
                        "high": quote.get("high", 0),
                        "low": quote.get("low", 0),
                        "prev_close": quote.get("prev_close", 0),
                        "volume": quote.get("volume", 0),
                        "amount": quote.get("amount", 0),
                        "time": quote.get("time", ""),
                        "change": quote.get("current", 0) - quote.get("prev_close", 0),
                        "change_pct": ((quote.get("current", 0) - quote.get("prev_close", 0)) /
                                       quote.get("prev_close", 1) * 100) if quote.get("prev_close") else 0
                    }
            except Exception as e:
                logger.error(f"获取 {symbol} 实时行情失败: {e}")
                quotes[symbol] = {"error": str(e)}

        return quotes

    def normalize_bars(self, data: List[Dict[str, Any]]):
        """
        标准化K线数据格式
        
        Args:
            data: 原始K线数据
            
        Returns:
            标准化后的数据
        """
        if not data:
            return [] if not HAS_PANDAS else pd.DataFrame()

        # 标准化字段映射
        field_map = {
            "日期": "date",
            "时间": "time",
            "开盘": "open",
            "最高": "high",
            "最低": "low",
            "收盘": "close",
            "成交量": "volume",
            "成交额": "amount",
            "涨跌幅": "change_pct",
            "涨跌额": "change",
            "换手率": "turnover",
            "振幅": "amplitude"
        }

        normalized = []
        for bar in data:
            normalized_bar = {}

            # 映射字段
            for old_key, new_key in field_map.items():
                if old_key in bar:
                    normalized_bar[new_key] = bar[old_key]

            # 添加其他字段
            for key, value in bar.items():
                if key not in field_map and key not in normalized_bar:
                    normalized_bar[key] = value

            normalized.append(normalized_bar)

        # 如果有pandas，返回DataFrame
        if HAS_PANDAS:
            df = pd.DataFrame(normalized)
            # 设置日期为索引
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'])
                df.set_index('date', inplace=True)
            return df

        return normalized

    async def get_stock_info(self, symbol: str) -> Dict[str, Any]:
        """
        获取股票信息
        
        Args:
            symbol: 股票代码
            
        Returns:
            股票信息字典
        """
        if not self.initialized:
            await self.initialize()

        return await self.provider.fetch_stock_info(symbol)

    async def get_stock_list(self) -> List[Dict[str, str]]:
        """
        获取股票列表
        
        Returns:
            股票列表
        """
        if not self.initialized:
            await self.initialize()

        return await self.provider.fetch_stock_list()

    async def subscribe(self, symbols: List[str]):
        """
        订阅股票行情
        
        Args:
            symbols: 股票代码列表
        """
        if not self.initialized:
            await self.initialize()

        await self.provider.subscribe_symbols(symbols)

    async def unsubscribe(self, symbols: List[str]):
        """
        取消订阅
        
        Args:
            symbols: 股票代码列表
        """
        if not self.initialized:
            await self.initialize()

        await self.provider.unsubscribe_symbols(symbols)

    def is_connected(self) -> bool:
        """检查连接状态"""
        return self.provider.is_connected() if self.provider else False

    async def close(self):
        """关闭连接"""
        if self.provider:
            await self.provider.close()
        self.initialized = False
        logger.info("QMT DataFeed 已关闭")
