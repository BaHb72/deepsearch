"""
AKShare直连数据提供者
直接使用AKShare获取实时股票数据，作为备用数据源
"""
import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, Optional, List

from loguru import logger

# 导入监控装饰器
from deepsearch.data_providers.unified_proxy import async_monitor_access
from deepsearch.observability.monitoring.data_source_monitor import DataSourceType, DataAccessType

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

        # 应用 AkShare 代理补丁，强制所有请求通过 CloudFlare
        try:
            from deepsearch.utils.network.akshare_proxy import patch_akshare
            patch_akshare()
            logger.info("已应用 AkShare CloudFlare 代理补丁")
        except Exception as e:
            logger.warning(f"应用 AkShare 代理补丁失败: {e}")
            # 即使补丁失败，仍然继续初始化

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

    @async_monitor_access(
        source=DataSourceType.AKSHARE,
        access_type=DataAccessType.REALTIME_QUOTE,
        module="akshare_direct"
    )
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

    @async_monitor_access(
        source=DataSourceType.AKSHARE,
        access_type=DataAccessType.HISTORICAL_KLINE,
        module="akshare_direct"
    )
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

    @async_monitor_access(
        source=DataSourceType.AKSHARE,
        access_type=DataAccessType.STOCK_LIST,
        module="akshare_direct"
    )
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
            # 尝试多种方式获取股票列表，提高容错性
            df = None
            
            # 方法1: 使用stock_zh_a_spot_em (东方财富实时行情)
            try:
                logger.debug("尝试使用东方财富接口获取股票列表...")
                df = ak.stock_zh_a_spot_em()
                if df is not None and not df.empty:
                    stocks = []
                    for _, row in df.iterrows():
                        stocks.append({
                            '代码': str(row.get('代码', '')),
                            '名称': str(row.get('名称', ''))
                        })
                    logger.info(f"通过东方财富接口获取到 {len(stocks)} 只股票")
                    return stocks
            except Exception as e1:
                logger.debug(f"东方财富接口失败: {e1}")
            
            # 方法2: 使用原来的stock_info_a_code_name
            try:
                logger.debug("尝试使用stock_info_a_code_name获取股票列表...")
                df = ak.stock_info_a_code_name()
                if df is not None and not df.empty:
                    stocks = []
                    for _, row in df.iterrows():
                        stocks.append({
                            '代码': str(row.get('code', '')),
                            '名称': str(row.get('name', ''))
                        })
                    logger.info(f"通过stock_info_a_code_name获取到 {len(stocks)} 只股票")
                    return stocks
            except Exception as e2:
                logger.debug(f"stock_info_a_code_name失败: {e2}")
            
            # 如果都失败了，返回一个基础的股票列表作为降级方案
            logger.warning("所有股票列表API都失败，使用默认股票列表")
            return [
                {'代码': '000001', '名称': '平安银行'},
                {'代码': '000002', '名称': '万科A'},
                {'代码': '600000', '名称': '浦发银行'},
                {'代码': '600036', '名称': '招商银行'},
            ]

        except Exception as e:
            logger.error(f"AKShare获取股票列表失败: {e}")
            # 返回基础股票列表
            return [
                {'代码': '000001', '名称': '平安银行'},
                {'代码': '000002', '名称': '万科A'},
            ]

    async def _fetch_with_fallback(
        self,
        api_name: str,
        params: Dict[str, Any],
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        带故障转移的数据获取（直连模式）
        
        Args:
            api_name: AkShare API函数名
            params: API参数
            max_retries: 最大重试次数
            
        Returns:
            API响应数据
        """
        if not HAS_AKSHARE or not self.initialized:
            return {"error": "AKShare未安装或未初始化"}
        
        # 检查缓存
        cache_key = f"api_{api_name}_{str(params)}"
        if cache_key in self._cache:
            cached_time, cached_data = self._cache[cache_key]
            cache_ttl = self._cache_ttl.get('api', 60)  # 默认60秒缓存
            if time.time() - cached_time < cache_ttl:
                logger.debug(f"从缓存返回 {api_name} 数据")
                return cached_data
        
        retries = 0
        last_error = None
        
        while retries < max_retries:
            try:
                # 在线程池中执行AkShare API调用
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    self._executor,
                    self._call_akshare_api,
                    api_name,
                    params
                )
                
                # 缓存成功的结果
                if result and not result.get("error"):
                    self._cache[cache_key] = (time.time(), result)
                
                return result
                
            except Exception as e:
                retries += 1
                last_error = e
                logger.warning(f"调用 {api_name} 失败 (尝试 {retries}/{max_retries}): {e}")
                
                if retries < max_retries:
                    # 指数退避
                    await asyncio.sleep(2 ** retries)
        
        # 所有重试都失败
        error_msg = f"调用 {api_name} 失败，已重试 {max_retries} 次: {last_error}"
        logger.error(error_msg)
        return {"error": error_msg}
    
    def _call_akshare_api(self, api_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        同步调用AkShare API（在线程池中执行）
        
        Args:
            api_name: AkShare API函数名
            params: API参数
            
        Returns:
            格式化的响应数据
        """
        try:
            logger.info(f"[AKShare Direct] 调用 {api_name} with params: {params}")
            
            # 获取AkShare函数
            if not hasattr(ak, api_name):
                # 尝试处理一些已知的API变更
                alternate_names = {
                    'stock_zh_a_hist_adj_factor': 'stock_zh_a_adjust',  # 复权因子新API
                    'stock_zh_a_daily': 'stock_zh_a_hist',  # 日线数据新API
                }
                
                if api_name in alternate_names:
                    new_api_name = alternate_names[api_name]
                    logger.info(f"API {api_name} 不存在，尝试使用替代API: {new_api_name}")
                    api_name = new_api_name
                
                if not hasattr(ak, api_name):
                    return {"error": f"AkShare不存在函数: {api_name}"}
            
            func = getattr(ak, api_name)
            
            # 调用API
            result = func(**params) if params else func()
            
            # 处理返回结果
            if pd and isinstance(result, pd.DataFrame):
                # 转换DataFrame为字典
                return {
                    "success": True,
                    "data": result.to_dict('records'),
                    "columns": result.columns.tolist(),
                    "count": len(result)
                }
            elif pd and isinstance(result, pd.Series):
                # 转换Series为字典
                return {
                    "success": True,
                    "data": result.to_dict(),
                    "count": len(result)
                }
            else:
                # 其他类型直接返回
                return {
                    "success": True,
                    "data": result
                }
            
        except Exception as e:
            logger.error(f"调用AkShare API {api_name} 失败: {e}")
            return {"error": str(e)}

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
