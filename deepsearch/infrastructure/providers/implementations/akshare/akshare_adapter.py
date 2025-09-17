"""
AkShare 数据提供者适配器

为不同的AkShare实现（Direct和Proxy）提供统一的接口
"""
from typing import Dict, List, Optional, Any
import pandas as pd
from loguru import logger

from deepsearch.infrastructure.providers.interfaces.base import DataProvider as IAkShareProvider, DataRequest
from .akshare_direct import AKShareDirectProvider
from .akshare import AkShareProxyProvider


class AkShareAdapter(IAkShareProvider):
    """
    AkShare适配器 - 统一Direct和Proxy两种实现
    
    可以根据配置或运行时条件选择使用直连还是代理模式
    """
    
    def __init__(self, use_proxy: bool = False):
        """
        初始化适配器
        
        Args:
            use_proxy: 是否使用代理模式
        """
        self.use_proxy = use_proxy
        self.provider = None
        self.fallback_provider = None
        
    async def initialize(self):
        """初始化提供者"""
        if self.use_proxy:
            # 主用代理，备用直连
            self.provider = AkShareProxyProvider()
            self.fallback_provider = AKShareDirectProvider()
            logger.info("使用AkShare代理模式，备用直连模式")
        else:
            # 主用直连，备用代理
            self.provider = AKShareDirectProvider()
            self.fallback_provider = AkShareProxyProvider()
            logger.info("使用AkShare直连模式，备用代理模式")
        
        # 初始化主提供者
        if hasattr(self.provider, 'initialize'):
            await self.provider.initialize()
        
        # 初始化备用提供者
        if hasattr(self.fallback_provider, 'initialize'):
            try:
                await self.fallback_provider.initialize()
            except Exception as e:
                logger.warning(f"备用提供者初始化失败: {e}")
    
    async def get_realtime_quote(self, symbol: str) -> Dict[str, Any]:
        """获取实时行情"""
        try:
            result = await self.provider.get_realtime_quote(symbol)
            if result is not None and not result.get("error"):
                return result
        except Exception as e:
            logger.warning(f"主数据源获取失败: {e}")
        
        # 尝试备用源
        if self.fallback_provider:
            try:
                logger.info(f"切换到备用数据源获取 {symbol} 实时行情")
                result = await self.fallback_provider.get_realtime_quote(symbol)
                if result is not None and not result.get("error"):
                    result["fallback"] = True
                    return result
            except Exception as e:
                logger.error(f"备用数据源也失败: {e}")
        
        return {"error": "所有数据源都失败"}
    
    async def get_stock_hist(
        self,
        symbol: str,
        period: str = "daily",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        adjust: str = ""
    ) -> Dict[str, Any]:
        """获取历史K线数据"""
        try:
            result = await self.provider.get_stock_hist(
                symbol, period, start_date, end_date, adjust
            )
            if result is not None and not result.get("error"):
                return result
        except Exception as e:
            logger.warning(f"主数据源获取历史数据失败: {e}")
        
        # 尝试备用源
        if self.fallback_provider:
            try:
                logger.info(f"切换到备用数据源获取 {symbol} 历史数据")
                result = await self.fallback_provider.get_stock_hist(
                    symbol, period, start_date, end_date, adjust
                )
                if result is not None and not result.get("error"):
                    result["fallback"] = True
                    return result
            except Exception as e:
                logger.error(f"备用数据源也失败: {e}")
        
        return {"data": [], "error": "所有数据源都失败"}
    
    async def fetch_stock_list(self) -> List[Dict[str, str]]:
        """获取股票列表"""
        try:
            result = await self.provider.fetch_stock_list()
            if result is not None and not result.empty:
                return result
        except Exception as e:
            logger.warning(f"主数据源获取股票列表失败: {e}")
        
        # 尝试备用源
        if self.fallback_provider:
            try:
                logger.info("切换到备用数据源获取股票列表")
                result = await self.fallback_provider.fetch_stock_list()
                if result is not None and not result.empty:
                    return result
            except Exception as e:
                logger.error(f"备用数据源也失败: {e}")
        
        # 返回默认列表
        return [
            {'代码': '000001', '名称': '平安银行'},
            {'代码': '000002', '名称': '万科A'},
            {'代码': '600000', '名称': '浦发银行'},
            {'代码': '600036', '名称': '招商银行'},
        ]
    
    def is_connected(self) -> bool:
        """检查连接状态"""
        if self.provider and hasattr(self.provider, 'is_connected'):
            return self.provider.is_connected()
        return False
    
    async def fetch_with_api(
        self,
        api_name: str,
        params: Dict[str, Any],
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        调用AkShare API的统一接口
        
        对于代理模式，会调用 _fetch_with_fallback
        对于直连模式，会直接调用对应的方法
        """
        # 代理模式有 _fetch_with_fallback
        if isinstance(self.provider, AkShareProxyProvider):
            try:
                result = await self.provider._fetch_with_fallback(
                    api_name, params, max_retries
                )
                # 确保返回格式统一
                if result is not None and not result.empty:
                    result = {"data": result, "success": True}
                if result is not None and not result.empty:
                    result["success"] = True
                return result
            except Exception as e:
                logger.warning(f"代理模式API调用失败: {e}")
                # 尝试备用
                if self.fallback_provider:
                    try:
                        return await self._call_direct_api(
                            self.fallback_provider, api_name, params
                        )
                    except Exception as fallback_error:
                        logger.error(f"备用数据源也失败: {fallback_error}")
                        return {"error": str(e), "success": False, "data": []}
                return {"error": str(e), "success": False, "data": []}
        # 直连模式需要映射到具体方法
        else:
            return await self._call_direct_api(
                self.provider, api_name, params
            )
    
    async def _call_direct_api(
        self,
        provider: AKShareDirectProvider,
        api_name: str,
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        调用直连模式的API
        
        将API名称映射到具体的方法调用
        """
        try:
            # 对于特殊的API，直接调用akshare库
            if api_name == "stock_zh_index_spot_em":
                # 获取指数数据
                import akshare as ak
                import asyncio
                logger.info(f"直连调用 ak.stock_zh_index_spot_em")
                df = await asyncio.get_event_loop().run_in_executor(
                    None, ak.stock_zh_index_spot_em
                )
                if df is not None and not df.empty:
                    return {"data": df.to_dict('records'), "success": True}
                return {"data": [], "success": True}
                
            elif api_name == "stock_zh_a_spot_em":
                # 获取全市场行情
                if not params.get("symbol"):
                    import akshare as ak
                    import asyncio
                    logger.info(f"直连调用 ak.stock_zh_a_spot_em")
                    df = await asyncio.get_event_loop().run_in_executor(
                        None, ak.stock_zh_a_spot_em
                    )
                    if df is not None and not df.empty:
                        return {"data": df.to_dict('records'), "success": True}
                    return {"data": [], "success": True}
                else:
                    # 单个股票
                    result = await provider.get_realtime_quote(params["symbol"])
                    return {"data": result, "success": True}
                    
            # 映射API名称到方法
            api_mapping = {
                "stock_zh_a_hist": lambda: provider.get_stock_hist(
                    symbol=params.get("symbol", ""),
                    period=params.get("period", "daily"),
                    start_date=params.get("start_date"),
                    end_date=params.get("end_date"),
                    adjust=params.get("adjust", "")
                ),
                "stock_info_a_code_name": lambda: provider.fetch_stock_list(),
            }
            
            if api_name in api_mapping:
                result = await api_mapping[api_name]()
                # 检查result是否已经包含data字段（历史数据接口）
                if isinstance(result, dict) and "data" in result:
                    # 已经是正确格式，直接返回并添加success标记
                    result["success"] = True
                    return result
                else:
                    # 需要包装的数据
                    return {"data": result, "success": True}
            else:
                logger.warning(f"未实现的API: {api_name}")
                return {"error": f"API {api_name} not implemented", "success": False, "data": []}
                
        except Exception as e:
            logger.error(f"直连API调用失败 {api_name}: {e}")
            return {"error": str(e), "success": False, "data": []}
    
    async def fetch_market_overview(self) -> Dict[str, Any]:
        """获取市场概览"""
        # 使用通用API接口
        return await self.fetch_with_api(
            "stock_zh_index_spot_em",
            {"symbol": "上证系列指数"}
        )
    
    async def fetch_sector_data(self) -> List[Dict[str, Any]]:
        """获取板块数据"""
        # 使用通用API接口
        result = await self.fetch_with_api(
            "stock_board_industry_name_em",
            {}
        )
        if result.get("success") and "data" in result:
            return result["data"]
        return []
    
    # 实现抽象基类的必需方法
    async def _initialize_source(self) -> None:
        """初始化数据源特定配置"""
        await self.initialize()
    
    async def _start_source(self) -> None:
        """启动数据源特定服务"""
        if self.provider:
            if hasattr(self.provider, 'start'):
                await self.provider.start()
            logger.info("AkShare数据源已启动")
    
    async def _stop_source(self) -> None:
        """停止数据源特定服务"""
        if self.provider:
            if hasattr(self.provider, 'stop'):
                await self.provider.stop()
            logger.info("AkShare数据源已停止")
    
    async def _fetch_data(self, request: DataRequest) -> pd.DataFrame:
        """
        获取数据的具体实现
        
        Args:
            request: 数据请求对象
            
        Returns:
            包含数据的DataFrame
        """
        try:
            # 处理单个股票请求
            if request.symbol:
                result = await self.get_stock_hist(
                    symbol=request.symbol,
                    period=request.period or "daily",
                    start_date=str(request.start_date) if request.start_date else None,
                    end_date=str(request.end_date) if request.end_date else None,
                    adjust=request.adjust or ""
                )
                
                if result is not None and not result.empty:
                    df = pd.DataFrame(result['data'])
                    # 确保有日期列
                    if not df.empty and '日期' in df.columns:
                        df['date'] = pd.to_datetime(df['日期'])
                        df = df.set_index('date')
                    return df
            
            # 处理批量股票请求
            elif request.symbols:
                frames = []
                for symbol in request.symbols:
                    result = await self.get_stock_hist(
                        symbol=symbol,
                        period=request.period or "daily",
                        start_date=str(request.start_date) if request.start_date else None,
                        end_date=str(request.end_date) if request.end_date else None,
                        adjust=request.adjust or ""
                    )
                    
                    if result is not None and not result.empty:
                        df = pd.DataFrame(result['data'])
                        df['symbol'] = symbol
                        frames.append(df)
                
                if frames:
                    combined = pd.concat(frames, ignore_index=True)
                    if '日期' in combined.columns:
                        combined['date'] = pd.to_datetime(combined['日期'])
                    return combined
            
            # 无有效请求，返回空DataFrame
            return pd.DataFrame()
            
        except Exception as e:
            logger.error(f"获取数据失败: {e}")
            return pd.DataFrame()