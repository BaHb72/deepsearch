"""
数据源 Fetcher 适配器

为各数据源提供统一的 fetcher 函数接口，
供 DataSyncPipeline 使用。

每个 fetcher 的签名为:
    async def fetcher(table: str, **kwargs) -> pd.DataFrame
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd

from deepsearch.observability import get_logger

logger = get_logger(__name__)


# ============ PostgreSQL Fetcher ============


class PostgreSQLFetcher:
    """PostgreSQL 数据拉取器

    从 PostgreSQL 读取数据供同步使用。
    """

    # 表名到 SQL 查询的映射
    TABLE_QUERIES = {
        "kline_history": """
            SELECT symbol, timestamp, open, high, low, close, volume,
                   amount, turnover_rate, change_pct, pre_close
            FROM kline_data
            WHERE 1=1
            {where_clause}
            ORDER BY timestamp
        """,
        "stock_info": """
            SELECT symbol, name, exchange, market, industry,
                   list_date, status, total_shares, float_shares,
                   pe_ratio, pb_ratio, market_cap
            FROM stock_info
            WHERE 1=1
            {where_clause}
        """,
    }

    # 字段映射（PostgreSQL 到标准字段）
    FIELD_MAPS = {
        "kline_history": {
            "symbol": "symbol",
            "timestamp": "timestamp",
            "open": "open",
            "high": "high",
            "low": "low",
            "close": "close",
            "volume": "volume",
            "amount": "amount",
            "turnover_rate": "turnover_rate",
            "change_pct": "change_pct",
            "pre_close": "pre_close",
        },
        "stock_info": {
            "symbol": "symbol",
            "name": "name",
            "exchange": "exchange",
            "market": "market",
            "industry": "industry",
            "list_date": "list_date",
            "status": "status",
            "total_shares": "total_shares",
            "float_shares": "float_shares",
            "pe_ratio": "pe_ratio",
            "pb_ratio": "pb_ratio",
            "market_cap": "market_cap",
        },
    }

    def __init__(self, database_component: Any):
        """初始化

        Args:
            database_component: DatabaseComponent 实例
        """
        self._db = database_component

    async def fetch(
        self,
        table: str,
        since: Optional[datetime] = None,
        symbols: Optional[List[str]] = None,
        **kwargs,
    ) -> pd.DataFrame:
        """拉取数据

        Args:
            table: 表名
            since: 增量起点时间
            symbols: 股票代码列表

        Returns:
            DataFrame
        """
        if not self._db or not self._db.is_connected():
            logger.warning("PostgreSQL 未连接，无法拉取数据")
            return pd.DataFrame()

        query_template = self.TABLE_QUERIES.get(table)
        if not query_template:
            logger.warning(f"不支持的表: {table}")
            return pd.DataFrame()

        # 构建 WHERE 子句
        where_parts = []
        params: Dict[str, Any] = {}

        if since:
            where_parts.append("AND timestamp >= :since")
            params["since"] = since

        if symbols:
            where_parts.append("AND symbol = ANY(:symbols)")
            params["symbols"] = symbols

        where_clause = " ".join(where_parts)
        query = query_template.format(where_clause=where_clause)

        try:
            async with self._db.get_session() as session:
                from sqlalchemy import text

                result = await session.execute(text(query), params)
                rows = result.fetchall()
                columns = result.keys()

                return pd.DataFrame(rows, columns=columns)

        except Exception as e:
            logger.error(f"PostgreSQL 查询失败: {e}")
            return pd.DataFrame()

    @classmethod
    def get_field_map(cls, table: str) -> Dict[str, str]:
        """获取表的字段映射"""
        return cls.FIELD_MAPS.get(table, {})


# ============ AmazingData Fetcher ============


class AmazingDataFetcher:
    """AmazingData 数据拉取器"""

    FIELD_MAPS = {
        "kline_history": {
            "SECURITY_CODE": "symbol",
            "TRADE_DATE": "timestamp",
            "OPEN_PRICE": "open",
            "HIGH_PRICE": "high",
            "LOW_PRICE": "low",
            "CLOSE_PRICE": "close",
            "TRADE_VOLUME": "volume",
            "TRADE_AMOUNT": "amount",
            "TURNOVER_RATE": "turnover_rate",
            "AMPLITUDE": "amplitude",
            "CHANGE_RATE": "change_pct",
            "PRE_CLOSE_PRICE": "pre_close",
        },
        "stock_info": {
            "SECURITY_CODE": "symbol",
            "SECURITY_NAME_ABBR": "name",
            "EXCHANGE": "exchange",
            "MARKET": "market",
            "INDUSTRY": "industry",
            "LIST_DATE": "list_date",
            "TOTAL_SHARES": "total_shares",
            "FLOAT_SHARES": "float_shares",
            "PE_RATIO": "pe_ratio",
            "PB_RATIO": "pb_ratio",
        },
    }

    def __init__(self, client: Any = None):
        """初始化

        Args:
            client: AmazingData 客户端实例
        """
        self._client = client

    async def fetch(
        self,
        table: str,
        since: Optional[datetime] = None,
        symbols: Optional[List[str]] = None,
        **kwargs,
    ) -> pd.DataFrame:
        """拉取数据"""
        if not self._client:
            logger.debug("AmazingData 客户端未配置")
            return pd.DataFrame()

        try:
            if table == "kline_history":
                return await self._fetch_kline(since, symbols, **kwargs)
            elif table == "stock_info":
                return await self._fetch_stock_info(**kwargs)
            else:
                logger.warning(f"AmazingData 不支持的表: {table}")
                return pd.DataFrame()

        except Exception as e:
            logger.error(f"AmazingData 查询失败: {e}")
            return pd.DataFrame()

    async def _fetch_kline(
        self,
        since: Optional[datetime],
        symbols: Optional[List[str]],
        **kwargs,
    ) -> pd.DataFrame:
        """拉取 K 线数据"""
        # 调用 AmazingData API
        # 这里需要根据实际 API 调整
        start_date = since.strftime("%Y%m%d") if since else None

        result = self._client.get_kline_history(
            start_date=start_date,
            symbols=symbols,
            **kwargs,
        )

        if hasattr(result, "__await__"):
            result = await result

        return result if isinstance(result, pd.DataFrame) else pd.DataFrame()

    async def _fetch_stock_info(self, **kwargs) -> pd.DataFrame:
        """拉取股票信息"""
        result = self._client.get_stock_info(**kwargs)

        if hasattr(result, "__await__"):
            result = await result

        return result if isinstance(result, pd.DataFrame) else pd.DataFrame()

    @classmethod
    def get_field_map(cls, table: str) -> Dict[str, str]:
        """获取表的字段映射"""
        return cls.FIELD_MAPS.get(table, {})


# ============ AkShare Fetcher ============


class AkShareFetcher:
    """AkShare 数据拉取器"""

    FIELD_MAPS = {
        "kline_history": {
            "日期": "timestamp",
            "股票代码": "symbol",
            "代码": "symbol",
            "开盘": "open",
            "最高": "high",
            "最低": "low",
            "收盘": "close",
            "成交量": "volume",
            "成交额": "amount",
            "换手率": "turnover_rate",
            "振幅": "amplitude",
            "涨跌幅": "change_pct",
            "涨跌额": "change",
        },
        "stock_info": {
            "代码": "symbol",
            "名称": "name",
            "行业": "industry",
            "市场": "market",
        },
    }

    def __init__(self):
        """初始化"""
        self._ak = None
        try:
            import akshare as ak

            self._ak = ak
        except ImportError:
            logger.debug("AkShare 未安装")

    async def fetch(
        self,
        table: str,
        since: Optional[datetime] = None,
        symbols: Optional[List[str]] = None,
        **kwargs,
    ) -> pd.DataFrame:
        """拉取数据"""
        if not self._ak:
            logger.debug("AkShare 未安装，跳过")
            return pd.DataFrame()

        try:
            if table == "kline_history":
                return await self._fetch_kline(since, symbols, **kwargs)
            elif table == "stock_info":
                return await self._fetch_stock_info(**kwargs)
            else:
                return pd.DataFrame()

        except Exception as e:
            logger.error(f"AkShare 查询失败: {e}")
            return pd.DataFrame()

    async def _fetch_kline(
        self,
        since: Optional[datetime],
        symbols: Optional[List[str]],
        **kwargs,
    ) -> pd.DataFrame:
        """拉取 K 线（AkShare 通常是同步的，这里包装成异步）"""
        import asyncio

        def _sync_fetch():
            dfs = []
            target_symbols = symbols or []

            for symbol in target_symbols[:10]:  # 限制数量避免请求过多
                try:
                    df = self._ak.stock_zh_a_hist(
                        symbol=symbol,
                        start_date=since.strftime("%Y%m%d") if since else None,
                        adjust="qfq",
                    )
                    if not df.empty:
                        df["股票代码"] = symbol
                        dfs.append(df)
                except Exception as e:
                    logger.warning(f"AkShare 获取 {symbol} 失败: {e}")
                    continue

            return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

        # 在线程池中执行同步函数
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _sync_fetch)

    async def _fetch_stock_info(self, **kwargs) -> pd.DataFrame:
        """拉取股票列表"""
        import asyncio

        def _sync_fetch():
            try:
                return self._ak.stock_info_a_code_name()
            except Exception as e:
                logger.error(f"AkShare 获取股票列表失败: {e}")
                return pd.DataFrame()

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _sync_fetch)

    @classmethod
    def get_field_map(cls, table: str) -> Dict[str, str]:
        """获取表的字段映射"""
        return cls.FIELD_MAPS.get(table, {})


# ============ 工厂函数 ============


def create_postgresql_fetcher(database_component: Any) -> PostgreSQLFetcher:
    """创建 PostgreSQL fetcher"""
    return PostgreSQLFetcher(database_component)


def create_amazingdata_fetcher(client: Any = None) -> AmazingDataFetcher:
    """创建 AmazingData fetcher"""
    return AmazingDataFetcher(client)


def create_akshare_fetcher() -> AkShareFetcher:
    """创建 AkShare fetcher"""
    return AkShareFetcher()
