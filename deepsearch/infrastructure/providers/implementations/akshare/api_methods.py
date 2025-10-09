"""
AkShare API方法实现
提供各种金融数据API的具体实现
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
from loguru import logger

from deepsearch.observability.decorators.decorators import monitor_data_source
from deepsearch.observability.monitoring.data_source_monitor import DataAccessType, DataSourceType
from deepsearch.utils.time.market_time import MarketTimeUtil


class AkShareAPIMethods:
    """AkShare API方法集合"""

    def __init__(self, request_handler):
        """
        初始化API方法

        Args:
            request_handler: 请求处理器实例
        """
        self.request_handler = request_handler
        self.market_time_util = MarketTimeUtil()

    @monitor_data_source(source=DataSourceType.AKSHARE, access_type=DataAccessType.REALTIME_QUOTE)
    async def get_realtime_data(self, symbols: List[str]) -> Dict[str, Any]:
        """
        获取实时行情数据

        Args:
            symbols: 股票代码列表

        Returns:
            实时行情数据字典
        """
        try:
            # 处理输入参数
            if not symbols:
                return {"error": "No symbols provided", "data": {}}

            # 确保是列表
            if isinstance(symbols, str):
                symbols = [symbols]

            # 标准化股票代码
            normalized_symbols = []
            for symbol in symbols:
                # 移除市场后缀
                if "." in symbol:
                    symbol = symbol.split(".")[0]
                # 确保是6位代码
                if len(symbol) < 6:
                    symbol = symbol.zfill(6)
                normalized_symbols.append(symbol)

            logger.info(f"获取实时数据: {normalized_symbols}")

            # 调用 Worker API
            result = await self.request_handler.call_api(
                "stock_zh_a_spot_em", {"symbols": normalized_symbols}
            )

            if not result:
                return {"error": "Failed to fetch realtime data", "data": {}}

            # 处理返回数据
            processed_data = {}
            if isinstance(result, dict):
                # 直接返回字典格式
                processed_data = result
            elif isinstance(result, list):
                # 列表格式转换为字典
                for item in result:
                    if isinstance(item, dict) and "symbol" in item:
                        processed_data[item["symbol"]] = item

            return {
                "success": True,
                "data": processed_data,
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"获取实时数据失败: {e}")
            return {"error": str(e), "data": {}}

    @monitor_data_source(source=DataSourceType.AKSHARE, access_type=DataAccessType.HISTORICAL_KLINE)
    async def get_history_data(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        period: str = "daily",
        adjust: str = "",
    ) -> Optional[pd.DataFrame]:
        """
        获取历史K线数据

        Args:
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            period: 周期（daily, weekly, monthly）
            adjust: 复权类型（qfq, hfq, 空字符串表示不复权）

        Returns:
            历史数据DataFrame
        """
        try:
            # 标准化股票代码
            if "." in symbol:
                symbol = symbol.split(".")[0]
            if len(symbol) < 6:
                symbol = symbol.zfill(6)

            logger.info(f"获取历史数据: {symbol}, 周期: {period}, 复权: {adjust or '不复权'}")

            # 准备参数
            params = {"symbol": symbol, "period": period, "adjust": adjust}

            if start_date:
                params["start_date"] = start_date
            if end_date:
                params["end_date"] = end_date

            # 调用API
            result = await self.request_handler.call_api("stock_zh_a_hist", params)

            if not result:
                logger.warning(f"未获取到 {symbol} 的历史数据")
                return None

            # 转换为DataFrame
            if isinstance(result, list) and result:
                df = pd.DataFrame(result)
                # 标准化列名
                column_mapping = {
                    "date": "datetime",
                    "open": "open",
                    "high": "high",
                    "low": "low",
                    "close": "close",
                    "volume": "volume",
                    "amount": "amount",
                    "turnover": "turnover",
                }
                df.rename(columns=column_mapping, inplace=True)

                # 确保日期列为datetime类型
                if "datetime" in df.columns:
                    df["datetime"] = pd.to_datetime(df["datetime"])
                    df.set_index("datetime", inplace=True)

                return df

            return None

        except Exception as e:
            logger.error(f"获取历史数据失败: {e}")
            return None

    async def fetch_sector_data(self, api_name: str, params: Dict[str, Any]) -> Any:
        """获取板块数据"""
        return await self.request_handler.call_api(api_name, params)

    async def fetch_anomaly_data(self, api_name: str, params: Dict[str, Any]) -> Any:
        """获取异动数据"""
        return await self.request_handler.call_api(api_name, params)

    async def fetch_hsgt_data(self, api_name: str, params: Dict[str, Any]) -> Any:
        """
        获取沪深港通数据

        Args:
            api_name: API名称
            params: 请求参数

        Returns:
            沪深港通数据
        """
        return await self.request_handler.call_api(api_name, params)

    async def fetch_all_realtime_quotes(self) -> Any:
        """获取所有股票实时行情"""
        try:
            result = await self.request_handler.call_api("stock_zh_a_spot_em", {"fetch_all": True})
            return result
        except Exception as e:
            logger.error(f"获取全部实时行情失败: {e}")
            return None

    async def fetch_intraday_data(self, symbol: str) -> Any:
        """获取分时数据"""
        try:
            # 标准化股票代码
            if "." in symbol:
                symbol = symbol.split(".")[0]
            if len(symbol) < 6:
                symbol = symbol.zfill(6)

            result = await self.request_handler.call_api(
                "stock_zh_a_hist_min_em", {"symbol": symbol, "period": "1"}
            )
            return result
        except Exception as e:
            logger.error(f"获取分时数据失败: {e}")
            return None

    async def fetch_orderbook_data(self, symbol: str) -> Any:
        """获取盘口数据"""
        try:
            # 标准化股票代码
            if "." in symbol:
                symbol = symbol.split(".")[0]
            if len(symbol) < 6:
                symbol = symbol.zfill(6)

            result = await self.request_handler.call_api("stock_bid_ask_em", {"symbol": symbol})
            return result
        except Exception as e:
            logger.error(f"获取盘口数据失败: {e}")
            return None

    async def fetch_fund_flow_data(self, symbol: Optional[str] = None) -> Any:
        """
        获取资金流向数据

        Args:
            symbol: 股票代码（可选，不传则获取全市场）

        Returns:
            资金流向数据
        """
        try:
            if symbol:
                # 单个股票资金流
                if "." in symbol:
                    symbol = symbol.split(".")[0]
                if len(symbol) < 6:
                    symbol = symbol.zfill(6)

                result = await self.request_handler.call_api(
                    "stock_individual_fund_flow", {"symbol": symbol}
                )
            else:
                # 全市场资金流
                result = await self.request_handler.call_api("stock_market_fund_flow", {})

            return result
        except Exception as e:
            logger.error(f"获取资金流向数据失败: {e}")
            return None

    async def fetch_concept_data(self) -> Any:
        """获取概念板块数据"""
        try:
            result = await self.request_handler.call_api("stock_board_concept_em", {})
            return result
        except Exception as e:
            logger.error(f"获取概念板块失败: {e}")
            return None

    async def fetch_industry_data(self) -> Any:
        """获取行业板块数据"""
        try:
            result = await self.request_handler.call_api("stock_board_industry_em", {})
            return result
        except Exception as e:
            logger.error(f"获取行业板块失败: {e}")
            return None

    async def fetch_etf_data(self) -> Any:
        """获取ETF数据"""
        try:
            result = await self.request_handler.call_api("fund_etf_spot_em", {})
            return result
        except Exception as e:
            logger.error(f"获取ETF数据失败: {e}")
            return None

    async def fetch_index_data(self) -> Any:
        """获取指数数据"""
        try:
            result = await self.request_handler.call_api("stock_zh_index_spot", {})
            return result
        except Exception as e:
            logger.error(f"获取指数数据失败: {e}")
            return None

    async def fetch_futures_data(self, symbol: Optional[str] = None) -> Any:
        """
        获取期货数据

        Args:
            symbol: 期货代码（可选）

        Returns:
            期货数据
        """
        try:
            params = {}
            if symbol:
                params["symbol"] = symbol

            result = await self.request_handler.call_api("futures_zh_spot", params)
            return result
        except Exception as e:
            logger.error(f"获取期货数据失败: {e}")
            return None

    async def fetch_option_data(self, symbol: Optional[str] = None) -> Any:
        """
        获取期权数据

        Args:
            symbol: 期权代码（可选）

        Returns:
            期权数据
        """
        try:
            params = {}
            if symbol:
                params["symbol"] = symbol

            result = await self.request_handler.call_api("option_zh_spot", params)
            return result
        except Exception as e:
            logger.error(f"获取期权数据失败: {e}")
            return None

    async def fetch_financial_data(self, symbol: str, report_type: str = "main") -> Any:
        """
        获取财务数据

        Args:
            symbol: 股票代码
            report_type: 报表类型（main: 主要指标, balance: 资产负债表, income: 利润表, cashflow: 现金流量表）

        Returns:
            财务数据
        """
        try:
            # 标准化股票代码
            if "." in symbol:
                symbol = symbol.split(".")[0]
            if len(symbol) < 6:
                symbol = symbol.zfill(6)

            api_map = {
                "main": "stock_financial_main_indicator",
                "balance": "stock_financial_balance_sheet",
                "income": "stock_financial_income_statement",
                "cashflow": "stock_financial_cashflow_statement",
            }

            api_name = api_map.get(report_type, "stock_financial_main_indicator")

            result = await self.request_handler.call_api(api_name, {"symbol": symbol})
            return result
        except Exception as e:
            logger.error(f"获取财务数据失败: {e}")
            return None

    async def fetch_holder_data(self, symbol: str) -> Any:
        """
        获取股东数据

        Args:
            symbol: 股票代码

        Returns:
            股东数据
        """
        try:
            # 标准化股票代码
            if "." in symbol:
                symbol = symbol.split(".")[0]
            if len(symbol) < 6:
                symbol = symbol.zfill(6)

            result = await self.request_handler.call_api("stock_holder_em", {"symbol": symbol})
            return result
        except Exception as e:
            logger.error(f"获取股东数据失败: {e}")
            return None
