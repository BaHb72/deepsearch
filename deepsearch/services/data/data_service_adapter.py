"""
数据服务适配器

为服务层提供统一的数据访问接口，隔离对具体数据提供者的依赖
"""
from typing import Dict, Any, Optional
from loguru import logger

from deepsearch.data_providers.implementations.akshare.akshare_adapter import AkShareAdapter
from deepsearch.data_providers.interfaces.base import DataProvider as IAkShareProvider


class DataServiceAdapter:
    """
    数据服务适配器
    
    为MarketService、ChartService等服务提供统一的数据访问接口
    """
    
    def __init__(self, provider: Optional[IAkShareProvider] = None):
        """
        初始化适配器
        
        Args:
            provider: 数据提供者实例，如果为None则创建默认实例
        """
        if provider is None:
            # 创建默认的适配器
            self.provider = AkShareAdapter(use_proxy=True)  # 默认使用代理模式
            logger.info("创建默认的AkShare适配器（代理模式）")
        else:
            self.provider = provider
            
        self.initialized = False
    
    async def initialize(self):
        """初始化适配器"""
        if self.initialized:
            return
            
        if hasattr(self.provider, 'initialize'):
            await self.provider.initialize()
            
        self.initialized = True
        logger.info("数据服务适配器初始化完成")
    
    async def fetch_api(
        self,
        api_name: str,
        params: Dict[str, Any],
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        调用API的统一接口
        
        Args:
            api_name: API名称
            params: 参数
            max_retries: 最大重试次数
            
        Returns:
            API返回数据
        """
        if not self.initialized:
            await self.initialize()
        
        # 如果provider实现了fetch_with_api方法，使用它
        if hasattr(self.provider, 'fetch_with_api'):
            return await self.provider.fetch_with_api(api_name, params, max_retries)
        
        # 否则，尝试映射到具体方法
        return await self._map_api_call(api_name, params)
    
    async def _map_api_call(
        self,
        api_name: str,
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        将API名称映射到具体的方法调用
        
        这是为了兼容不同的Provider实现
        """
        try:
            # 首先检查是否有对应的API映射
            from deepsearch.data_providers.implementations.akshare.akshare_api_mapping import AkShareAPIMapping
            api_info = AkShareAPIMapping.get_api_info(api_name)
            
            # 如果找到API映射，尝试直接调用provider的通用方法
            if api_info:
                # 应用参数转换
                transformed_params = AkShareAPIMapping.transform_params(api_name, params)
                
                # 如果provider有通用的API调用方法，使用它
                if hasattr(self.provider, 'call_api'):
                    result = await self.provider.call_api(api_name, transformed_params)
                    return {"data": result, "success": True}
                
                # 根据API类别进行特殊处理
                category = api_info.get("category", "")
                
                # 市场概览相关API
                if api_name == "stock_zh_index_spot_em":
                    if hasattr(self.provider, 'fetch_market_overview'):
                        result = await self.provider.fetch_market_overview()
                        return {"data": result, "success": True}
                
                # 板块数据相关API
                elif category == "sector" or api_name in ["stock_board_industry_name_em", "stock_board_concept_name_em"]:
                    if hasattr(self.provider, 'fetch_sector_data'):
                        result = await self.provider.fetch_sector_data(api_name, transformed_params)
                        return {"data": result, "success": True}
                
                # 涨跌停和异动数据
                elif category == "anomaly" or api_name in ["stock_zt_pool_em", "stock_zt_pool_dtgc_em"]:
                    if hasattr(self.provider, 'fetch_anomaly_data'):
                        result = await self.provider.fetch_anomaly_data(api_name, transformed_params)
                        return {"data": result, "success": True}
                
                # 沪深港通数据
                elif category == "hsgt" or "hsgt" in api_name or "em_hsgt" in api_name:
                    if hasattr(self.provider, 'fetch_hsgt_data'):
                        result = await self.provider.fetch_hsgt_data(api_name, transformed_params)
                        return {"data": result, "success": True}
                
                # 实时行情相关API
                elif api_name == "stock_zh_a_spot_em":
                    if not params.get("symbol"):
                        # 获取全市场数据
                        if hasattr(self.provider, 'fetch_all_realtime_quotes'):
                            result = await self.provider.fetch_all_realtime_quotes()
                            return {"data": result, "success": True}
                    else:
                        # 获取单个股票数据
                        if hasattr(self.provider, 'get_realtime_quote'):
                            result = await self.provider.get_realtime_quote(params["symbol"])
                            return {"data": result, "success": True}
                
                # 历史数据相关API
                elif api_name in ["stock_zh_a_hist", "stock_zh_a_hist_min_em"]:
                    if hasattr(self.provider, 'get_stock_hist'):
                        result = await self.provider.get_stock_hist(
                            symbol=transformed_params.get("symbol", ""),
                            period=transformed_params.get("period", "daily"),
                            start_date=transformed_params.get("start_date"),
                            end_date=transformed_params.get("end_date"),
                            adjust=transformed_params.get("adjust", "")
                        )
                        return result
                
                # 股票列表相关API
                elif api_name == "stock_info_a_code_name":
                    if hasattr(self.provider, 'fetch_stock_list'):
                        result = await self.provider.fetch_stock_list()
                        return {"data": result, "success": True}
                
                # 分时数据
                elif category == "intraday" or api_name == "stock_intraday_em":
                    if hasattr(self.provider, 'fetch_intraday_data'):
                        result = await self.provider.fetch_intraday_data(transformed_params.get("symbol"))
                        return {"data": result, "success": True}
                
                # 买卖盘口数据
                elif category == "orderbook" or api_name == "stock_bid_ask_em":
                    if hasattr(self.provider, 'fetch_orderbook_data'):
                        result = await self.provider.fetch_orderbook_data(transformed_params.get("symbol"))
                        return {"data": result, "success": True}
            
            # 如果没有找到映射，记录警告
            logger.warning(f"API映射未实现或provider不支持: {api_name}")
            return {"error": f"API {api_name} not supported by current provider", "success": False}
            
        except Exception as e:
            logger.error(f"API调用失败 {api_name}: {e}")
            return {"error": str(e), "success": False}
    
    def is_connected(self) -> bool:
        """检查连接状态"""
        if hasattr(self.provider, 'is_connected'):
            return self.provider.is_connected()
        return False
    
    async def close(self):
        """关闭连接"""
        if hasattr(self.provider, 'close'):
            await self.provider.close()
        self.initialized = False