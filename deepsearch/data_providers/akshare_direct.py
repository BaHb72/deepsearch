"""
AKShare直连数据提供者
直接使用AKShare获取实时股票数据，作为备用数据源
"""
import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, Optional, List

from loguru import logger

try:
    import akshare as ak

    HAS_AKSHARE = True
except ImportError:
    HAS_AKSHARE = False
    ak = None
    logger.warning("AKShare未安装，直连数据提供者不可用")

try:
    import pandas as pd

    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False
    pd = None


class AKShareDirectProvider:
    """AKShare直连数据提供者"""

    def __init__(self):
        self.session = None
        self._cache = {}
        self._cache_ttl = {
            'realtime': 10,  # 实时数据缓存10秒
            'hist': 300,  # 历史数据缓存5分钟
            'info': 3600  # 股票信息缓存1小时
        }
        self._executor = ThreadPoolExecutor(max_workers=3)
        self.initialized = False

    async def initialize(self):
        """初始化"""
        if not HAS_AKSHARE:
            logger.error("AKShare未安装，无法初始化直连数据提供者")
            return False

        logger.info("初始化AKShare直连数据提供者")
        self.initialized = True
        return True

    def _safe_float(self, value: Any, default: float = 0.0) -> float:
        """
        安全地将值转换为浮点数
        
        Args:
            value: 要转换的值
            default: 转换失败时的默认值
            
        Returns:
            转换后的浮点数
        """
        if value is None:
            return default

        # 处理字符串
        if isinstance(value, str):
            # 处理空字符串或特殊字符
            if value in ['', '-', '--', 'N/A', 'null', 'None']:
                return default

            # 移除可能的千分位分隔符和百分号
            value = value.replace(',', '').replace('%', '')

            try:
                return float(value)
            except (ValueError, TypeError) as e:
                logger.debug(f"无法转换为浮点数: {value}, 错误: {e}")
                return default

        # 处理数字类型
        try:
            return float(value)
        except (ValueError, TypeError) as e:
            logger.debug(f"无法转换为浮点数: {value}, 错误: {e}")
            return default

    async def get_realtime_quote(self, symbol: str) -> Dict[str, Any]:
        """
        获取实时行情
        
        Args:
            symbol: 股票代码
            
        Returns:
            实时行情数据
        """
        if not HAS_AKSHARE or not self.initialized:
            return {"error": "AKShare未安装或未初始化"}

        try:
            # 检查缓存
            cache_key = f"quote_{symbol}"
            if cache_key in self._cache:
                cached_time, cached_data = self._cache[cache_key]
                if time.time() - cached_time < self._cache_ttl['realtime']:
                    return cached_data

            # 在线程池中执行阻塞的AKShare调用
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self._executor,
                self._fetch_realtime_quote_sync,
                symbol
            )

            # 缓存结果
            if result and not result.get("error"):
                self._cache[cache_key] = (time.time(), result)

            return result

        except Exception as e:
            logger.error(f"获取实时行情失败: {e}")
            return {"error": str(e)}

    def _fetch_realtime_quote_sync(self, symbol: str) -> Dict[str, Any]:
        """同步获取实时行情（在线程池中执行）"""
        try:
            logger.info(f"[AKShare] 开始获取 {symbol} 实时行情")

            # 方法1: 尝试使用个股信息接口（更快）
            try:
                # 获取个股信息
                df_info = ak.stock_individual_info_em(symbol=symbol)
                if not df_info.empty:
                    info_dict = {}
                    for _, row in df_info.iterrows():
                        info_dict[row['item']] = row['value']

                    logger.info(f"[AKShare] 通过个股信息接口获取 {symbol} 成功")
                    return {
                        "symbol": symbol,
                        "name": info_dict.get('股票简称', ''),
                        "current": self._safe_float(info_dict.get('最新', 0)),
                        "prev_close": self._safe_float(info_dict.get('昨收', 0)),
                        "open": self._safe_float(info_dict.get('今开', 0)),
                        "high": self._safe_float(info_dict.get('最高', 0)),
                        "low": self._safe_float(info_dict.get('最低', 0)),
                        "volume": self._safe_float(info_dict.get('成交量', 0)),
                        "amount": self._safe_float(info_dict.get('成交额', 0)),
                        "change": self._safe_float(info_dict.get('涨跌', 0)),
                        "change_pct": self._safe_float(info_dict.get('涨跌幅', 0)),
                        "source": "akshare_direct_individual"
                    }
            except Exception as e:
                logger.debug(f"个股信息接口失败: {e}")

            # 方法2: 降级到全市场查询（慢，约20秒）
            logger.warning(f"[AKShare] 降级到全市场查询（慢）")
            df = ak.stock_zh_a_spot_em()

            # 查找指定股票
            stock_data = df[df['代码'] == symbol]

            if stock_data.empty:
                return {"error": f"未找到股票 {symbol}"}

            row = stock_data.iloc[0]

            return {
                "symbol": symbol,
                "name": row.get('名称', ''),
                "current": self._safe_float(row.get('最新价', 0)),
                "prev_close": self._safe_float(row.get('昨收', 0)),
                "open": self._safe_float(row.get('今开', 0)),
                "high": self._safe_float(row.get('最高', 0)),
                "low": self._safe_float(row.get('最低', 0)),
                "volume": self._safe_float(row.get('成交量', 0)),
                "amount": self._safe_float(row.get('成交额', 0)),
                "change": self._safe_float(row.get('涨跌额', 0)),
                "change_pct": self._safe_float(row.get('涨跌幅', 0)),
                "amplitude": self._safe_float(row.get('振幅', 0)),
                "turnover_rate": self._safe_float(row.get('换手率', 0)),
                "pe_ratio": self._safe_float(row.get('市盈率-动态', 0)),
                "pb_ratio": self._safe_float(row.get('市净率', 0)),
                "market_cap": self._safe_float(row.get('总市值', 0)),
                "float_market_cap": self._safe_float(row.get('流通市值', 0)),
                "source": "akshare_direct"
            }

        except Exception as e:
            logger.error(f"AKShare获取实时行情失败: {e}")
            return {"error": str(e)}

    async def get_stock_hist(
            self,
            symbol: str,
            period: str = "daily",
            start_date: Optional[str] = None,
            end_date: Optional[str] = None,
            adjust: str = ""
    ) -> Dict[str, Any]:
        """
        获取股票历史数据
        
        Args:
            symbol: 股票代码
            period: 周期类型
            start_date: 开始日期
            end_date: 结束日期
            adjust: 复权类型
            
        Returns:
            历史K线数据
        """
        if not HAS_AKSHARE or not self.initialized:
            return {"data": [], "error": "AKShare未安装或未初始化"}

        try:
            # 检查缓存
            cache_key = f"hist_{symbol}_{period}_{start_date}_{end_date}_{adjust}"
            if cache_key in self._cache:
                cached_time, cached_data = self._cache[cache_key]
                if time.time() - cached_time < self._cache_ttl['hist']:
                    return cached_data

            # 在线程池中执行
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self._executor,
                self._fetch_hist_sync,
                symbol, period, start_date, end_date, adjust
            )

            # 缓存结果
            if result and result.get("data"):
                self._cache[cache_key] = (time.time(), result)

            return result

        except Exception as e:
            logger.error(f"获取历史数据失败: {e}")
            return {"data": [], "error": str(e)}

    def _fetch_hist_sync(
            self,
            symbol: str,
            period: str,
            start_date: Optional[str],
            end_date: Optional[str],
            adjust: str
    ) -> Dict[str, Any]:
        """同步获取历史数据"""
        try:
            # 转换复权类型
            adjust_map = {
                "": "",  # 不复权
                "none": "",  # 不复权
                "qfq": "qfq",  # 前复权
                "hfq": "hfq"  # 后复权
            }
            adjust_type = adjust_map.get(adjust, "")

            # 获取历史数据
            df = ak.stock_zh_a_hist(
                symbol=symbol,
                period=period,
                start_date=start_date.replace("-", "") if start_date else "19900101",
                end_date=end_date.replace("-", "") if end_date else "20500101",
                adjust=adjust_type
            )

            if df.empty:
                return {"data": [], "source": "akshare_direct"}

            # 转换为标准格式
            result = []
            for _, row in df.iterrows():
                result.append({
                    "date": str(row.get('日期', '')),
                    "open": float(row.get('开盘', 0)),
                    "close": float(row.get('收盘', 0)),
                    "high": float(row.get('最高', 0)),
                    "low": float(row.get('最低', 0)),
                    "volume": float(row.get('成交量', 0)),
                    "amount": float(row.get('成交额', 0)),
                    "amplitude": float(row.get('振幅', 0)),
                    "pct_change": float(row.get('涨跌幅', 0)),
                    "change": float(row.get('涨跌额', 0)),
                    "turnover_rate": float(row.get('换手率', 0))
                })

            logger.info(f"成功获取 {symbol} 的 {len(result)} 条历史数据")
            return {"data": result, "source": "akshare_direct"}

        except Exception as e:
            logger.error(f"AKShare获取历史数据失败: {e}")
            return {"data": [], "error": str(e)}

    async def fetch_stock_info(self, symbol: str) -> Dict[str, Any]:
        """
        获取股票基础信息
        
        Args:
            symbol: 股票代码
            
        Returns:
            股票基础信息
        """
        if not HAS_AKSHARE or not self.initialized:
            return {"symbol": symbol, "name": f"股票{symbol}", "error": "AKShare未安装或未初始化"}

        try:
            # 检查缓存
            cache_key = f"info_{symbol}"
            if cache_key in self._cache:
                cached_time, cached_data = self._cache[cache_key]
                if time.time() - cached_time < self._cache_ttl['info']:
                    return cached_data

            # 在线程池中执行
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self._executor,
                self._fetch_stock_info_sync,
                symbol
            )

            # 缓存结果
            if result and not result.get("error"):
                self._cache[cache_key] = (time.time(), result)

            return result

        except Exception as e:
            logger.error(f"获取股票信息失败: {e}")
            return {"symbol": symbol, "name": f"股票{symbol}", "error": str(e)}

    def _fetch_stock_info_sync(self, symbol: str) -> Dict[str, Any]:
        """同步获取股票信息"""
        try:
            # 获取个股信息
            df = ak.stock_individual_info_em(symbol=symbol)

            if df.empty:
                return {"symbol": symbol, "name": f"股票{symbol}", "error": "未找到股票信息"}

            # 转换为字典
            info_dict = {}
            for _, row in df.iterrows():
                info_dict[row['item']] = row['value']

            return {
                "symbol": symbol,
                "name": info_dict.get('股票简称', f'股票{symbol}'),
                "full_name": info_dict.get('公司名称', ''),
                "industry": info_dict.get('行业', ''),
                "market": "SH" if symbol.startswith('6') else "SZ",
                "listed_date": str(info_dict.get('上市时间', '')),
                "total_shares": float(info_dict.get('总股本', 0)),
                "float_shares": float(info_dict.get('流通股', 0)),
                "market_cap": float(info_dict.get('总市值', 0)),
                "float_market_cap": float(info_dict.get('流通市值', 0)),
                "source": "akshare_direct"
            }

        except Exception as e:
            logger.error(f"AKShare获取股票信息失败: {e}")
            return {"symbol": symbol, "name": f"股票{symbol}", "error": str(e)}

    async def fetch_stock_list(self) -> List[Dict[str, str]]:
        """获取股票列表"""
        if not HAS_AKSHARE or not self.initialized:
            return []

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self._executor,
                self._fetch_stock_list_sync
            )
            return result

        except Exception as e:
            logger.error(f"获取股票列表失败: {e}")
            return []

    def _fetch_stock_list_sync(self) -> List[Dict[str, str]]:
        """同步获取股票列表"""
        try:
            # 获取A股列表
            df = ak.stock_info_a_code_name()

            if df.empty:
                return []

            stocks = []
            for _, row in df.iterrows():
                stocks.append({
                    '代码': row.get('code', ''),
                    '名称': row.get('name', '')
                })

            logger.info(f"获取到 {len(stocks)} 只股票")
            return stocks

        except Exception as e:
            logger.error(f"AKShare获取股票列表失败: {e}")
            return []

    def is_connected(self) -> bool:
        """检查是否连接"""
        return HAS_AKSHARE and self.initialized

    async def close(self):
        """关闭连接"""
        if self._executor:
            self._executor.shutdown(wait=False)
        self._cache.clear()
        self.initialized = False
        logger.info("AKShare直连数据提供者已关闭")
