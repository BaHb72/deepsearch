"""
重构后的AkShare代理提供者
通过模块化设计提高可维护性和可测试性
"""

import asyncio
from typing import Any, Dict, List, Optional

import pandas as pd
from loguru import logger

from deepsearch.config import get_config
from deepsearch.infrastructure.providers.interfaces.base import (
    DataProviderConfig,
    DataProviderError,
    DataRequest,
    DataResponse,
    DataSourceType,
)
from deepsearch.infrastructure.providers.interfaces.capabilities import DataCapability
from deepsearch.utils.network.akshare_proxy import patch_akshare

from .api_methods import AkShareAPIMethods
from .async_wrapper import get_async_wrapper
from .cache_manager import get_cache_manager
from .request_handler import RequestHandler
from .request_optimizer import RequestOptimizer
from .worker_manager import WorkerManager


class AkShareProxyProvider:
    """
    重构后的AkShare代理提供者

    通过Cloudflare Workers提供稳定的数据访问
    采用模块化设计，分离职责：
    - WorkerManager: 管理Worker节点健康和负载均衡
    - RequestHandler: 处理请求和重试逻辑
    - AkShareAPIMethods: 实现具体的API方法
    - CacheManager: 管理缓存策略
    - RequestOptimizer: 优化请求队列和优先级
    """

    def __init__(self):
        """初始化AkShare代理提供者"""
        self.name = "akshare_proxy"
        self.display_name = "AkShare 代理提供者"

        self.config = DataProviderConfig(
            name="akshare",
            source_type=DataSourceType.AKSHARE,
            enabled=True,
            priority=3,
        )
        self.status = "inactive"

        # 延迟初始化标记
        self._initialized = False
        self._patch_applied = False

        # 获取配置
        config = get_config()

        # 从配置读取Worker URLs
        worker_urls = self._load_worker_urls(config)

        # 确定负载均衡策略
        strategy = "round_robin" if len(worker_urls) > 1 else "single"

        # 初始化核心组件
        self.worker_manager = WorkerManager(worker_urls, strategy)
        self.request_handler = RequestHandler(self.worker_manager)
        self.api_methods = AkShareAPIMethods(self.request_handler)

        # 缓存管理器
        self.cache_manager = get_cache_manager()

        # 请求优化器
        self.request_optimizer = RequestOptimizer()

        # 异步包装器（用于兼容同步调用）
        self._async_wrapper = None

        # 监控任务
        self._monitor_task = None

        logger.info(f"AkShare代理提供者初始化完成，Worker数量: {len(worker_urls)}")

    def get_capabilities(self) -> set[DataCapability]:
        """返回数据能力集合。"""

        return {
            DataCapability.REALTIME_QUOTE,
            DataCapability.REALTIME_QUOTES,
            DataCapability.KLINE_DATA,
            DataCapability.MINUTE_DATA,
            DataCapability.TICK_DATA,
            DataCapability.ORDER_BOOK,
            DataCapability.SECTOR_DATA,
            DataCapability.ANOMALY_DETECTION,
            DataCapability.CAPITAL_FLOW,
            DataCapability.NORTH_FLOW,
        }

    @staticmethod
    def _normalize_symbol(symbol: Optional[str]) -> str:
        """标准化股票代码为 6 位数字字符串。"""

        if not symbol:
            return ""
        normalized = symbol.split(".")[0]
        if len(normalized) < 6:
            normalized = normalized.zfill(6)
        return normalized

    def _load_worker_urls(self, config) -> List[str]:
        """
        从配置加载Worker URLs

        Args:
            config: 配置对象

        Returns:
            Worker URL列表
        """
        worker_urls = []

        if config and hasattr(config, "cloudflare_workers") and config.cloudflare_workers:
            # 读取单个URL配置
            if hasattr(config.cloudflare_workers, "url") and config.cloudflare_workers.url:
                url = config.cloudflare_workers.url
                if not url.startswith(("http://", "https://")):
                    url = f"https://{url}"
                worker_urls.append(url)
                logger.info(f"使用配置的Worker URL: {url}")

            # 支持多个workers
            elif (
                hasattr(config.cloudflare_workers, "workers") and config.cloudflare_workers.workers
            ):
                for url in config.cloudflare_workers.workers:
                    if not url.startswith(("http://", "https://")):
                        url = f"https://{url}"
                    worker_urls.append(url)
                logger.info(f"使用配置的Workers列表: {worker_urls}")

        # 使用默认值
        if not worker_urls:
            worker_urls = ["https://akshare-proxy.934073514.workers.dev"]
            logger.info("使用默认Worker URL")

        return worker_urls

    async def initialize(self):
        """
        初始化提供者

        执行异步初始化任务：
        1. 初始化Worker管理器
        2. 初始化请求处理器
        3. 检查Worker健康状态
        4. 应用AkShare补丁
        5. 启动健康监控
        """
        if self._initialized:
            return

        try:
            logger.info("开始初始化AkShare代理提供者...")

            # 初始化Worker管理器
            await self.worker_manager.initialize()

            # 初始化请求处理器
            await self.request_handler.initialize()

            # 应用补丁（如果需要）
            if not self._patch_applied:
                try:
                    if hasattr(patch_akshare, "__call__"):
                        patch_akshare()
                        self._patch_applied = True
                        logger.info("AkShare补丁应用成功")
                except Exception as e:
                    logger.warning(f"应用AkShare补丁失败: {e}")

            # 启动健康监控任务
            if not self._monitor_task:
                self._monitor_task = asyncio.create_task(self._run_health_monitor())
                logger.info("健康监控任务已启动")

            # 初始化异步包装器
            self._async_wrapper = get_async_wrapper()

            self._initialized = True
            self.status = "running"
            logger.info("AkShare代理提供者初始化完成")

        except Exception as e:
            logger.error(f"初始化失败: {e}")
            raise

    async def _run_health_monitor(self):
        """运行健康监控任务"""
        try:
            await self.worker_manager.monitor_health(interval=60)
        except asyncio.CancelledError:
            logger.info("健康监控任务已取消")
        except Exception as e:
            logger.error(f"健康监控任务异常: {e}")

    # ==================== API方法代理 ====================

    async def get_data(self, request: DataRequest) -> DataResponse:
        """根据 `DataRequest` 获取数据并封装响应。"""

        metadata = {
            "source": self.config.name or self.name,
            "request_type": request.request_type,
        }

        try:
            if not self._initialized:
                await self.initialize()

            request_type = (request.request_type or "").lower()

            if request_type == "realtime_quotes":
                symbols = request.symbols or ([] if request.symbol is None else [request.symbol])
                result = await self.get_realtime_data(symbols)

                if isinstance(result, dict):
                    data_block = result.get("data")
                    if isinstance(data_block, dict):
                        dataframe = pd.DataFrame.from_dict(data_block, orient="index")
                        dataframe.reset_index(drop=True, inplace=True)
                        return DataResponse(success=True, data=dataframe, metadata=metadata)
                    if isinstance(data_block, list):
                        return DataResponse(
                            success=True,
                            data=pd.DataFrame(data_block),
                            metadata=metadata,
                        )
                    error_msg = result.get("error") or "未返回实时行情"
                    return DataResponse(success=False, error=str(error_msg), metadata=metadata)

                if isinstance(result, pd.DataFrame):
                    return DataResponse(success=True, data=result, metadata=metadata)

                if result:
                    return DataResponse(success=True, data=result, metadata=metadata)

                raise DataProviderError("未获取到实时行情数据")

            if request_type == "historical_kline":
                symbol = self._normalize_symbol(request.symbol)
                if not symbol:
                    raise DataProviderError("historical_kline 请求缺少 symbol")

                period_alias = (request.period or "1d").lower()
                period_mapping = {
                    "1d": "daily",
                    "1w": "weekly",
                    "1m": "monthly",
                    "1mo": "monthly",
                    "1y": "yearly",
                }
                period = period_mapping.get(period_alias, "daily")

                dataframe = await self.get_history_data(
                    symbol=symbol,
                    start_date=request.start_date,
                    end_date=request.end_date,
                    period=period,
                    adjust=request.adjust or "",
                )

                if dataframe is None:
                    raise DataProviderError("未获取到历史数据")

                return DataResponse(success=True, data=dataframe, metadata=metadata)

            if request_type == "minute_kline":
                symbol = self._normalize_symbol(request.symbol)
                if not symbol:
                    raise DataProviderError("minute_kline 请求缺少 symbol")

                period_token = (request.period or "1m").lower()
                if period_token.endswith("m"):
                    period_token = period_token[:-1]
                if not period_token.isdigit():
                    period_token = "1"

                params = {"symbol": symbol, "period": period_token}
                if request.start_date:
                    params["start_date"] = request.start_date
                if request.end_date:
                    params["end_date"] = request.end_date

                payload = await self.request_handler.call_api(
                    "stock_zh_a_hist_min_em",
                    params,
                )

                if isinstance(payload, list):
                    dataframe = pd.DataFrame(payload)
                    return DataResponse(success=True, data=dataframe, metadata=metadata)
                if isinstance(payload, dict) and payload.get("data"):
                    dataframe = pd.DataFrame(payload["data"])
                    return DataResponse(success=True, data=dataframe, metadata=metadata)
                if payload is not None:
                    return DataResponse(success=True, data=payload, metadata=metadata)

                raise DataProviderError("未获取到分钟数据")

            raise DataProviderError(f"AkShare 不支持的请求类型: {request.request_type}")

        except DataProviderError as exc:
            return DataResponse(success=False, error=str(exc), metadata=metadata)
        except Exception as exc:  # pragma: no cover - 防御日志
            logger.exception("AkShare 获取数据异常: %s", exc)
            return DataResponse(success=False, error=str(exc), metadata=metadata)

    async def get_realtime_data(self, symbols: List[str]) -> Dict[str, Any]:
        """获取实时行情数据"""
        if not self._initialized:
            await self.initialize()
        return await self.api_methods.get_realtime_data(symbols)

    async def get_history_data(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        period: str = "daily",
        adjust: str = "",
    ) -> Optional[pd.DataFrame]:
        """获取历史K线数据"""
        if not self._initialized:
            await self.initialize()
        return await self.api_methods.get_history_data(symbol, start_date, end_date, period, adjust)

    async def fetch_sector_data(self, api_name: str, params: Dict[str, Any]) -> Any:
        """获取板块数据"""
        if not self._initialized:
            await self.initialize()
        return await self.api_methods.fetch_sector_data(api_name, params)

    async def fetch_anomaly_data(self, api_name: str, params: Dict[str, Any]) -> Any:
        """获取异动数据"""
        if not self._initialized:
            await self.initialize()
        return await self.api_methods.fetch_anomaly_data(api_name, params)

    async def fetch_hsgt_data(self, api_name: str, params: Dict[str, Any]) -> Any:
        """获取沪深港通数据"""
        if not self._initialized:
            await self.initialize()
        return await self.api_methods.fetch_hsgt_data(api_name, params)

    async def fetch_all_realtime_quotes(self) -> Any:
        """获取所有股票实时行情"""
        if not self._initialized:
            await self.initialize()
        return await self.api_methods.fetch_all_realtime_quotes()

    async def fetch_intraday_data(self, symbol: str) -> Any:
        """获取分时数据"""
        if not self._initialized:
            await self.initialize()
        return await self.api_methods.fetch_intraday_data(symbol)

    async def fetch_orderbook_data(self, symbol: str) -> Any:
        """获取盘口数据"""
        if not self._initialized:
            await self.initialize()
        return await self.api_methods.fetch_orderbook_data(symbol)

    async def fetch_fund_flow_data(self, symbol: Optional[str] = None) -> Any:
        """获取资金流向数据"""
        if not self._initialized:
            await self.initialize()
        return await self.api_methods.fetch_fund_flow_data(symbol)

    async def fetch_concept_data(self) -> Any:
        """获取概念板块数据"""
        if not self._initialized:
            await self.initialize()
        return await self.api_methods.fetch_concept_data()

    async def fetch_industry_data(self) -> Any:
        """获取行业板块数据"""
        if not self._initialized:
            await self.initialize()
        return await self.api_methods.fetch_industry_data()

    async def fetch_etf_data(self) -> Any:
        """获取ETF数据"""
        if not self._initialized:
            await self.initialize()
        return await self.api_methods.fetch_etf_data()

    async def fetch_index_data(self) -> Any:
        """获取指数数据"""
        if not self._initialized:
            await self.initialize()
        return await self.api_methods.fetch_index_data()

    async def fetch_futures_data(self, symbol: Optional[str] = None) -> Any:
        """获取期货数据"""
        if not self._initialized:
            await self.initialize()
        return await self.api_methods.fetch_futures_data(symbol)

    async def fetch_option_data(self, symbol: Optional[str] = None) -> Any:
        """获取期权数据"""
        if not self._initialized:
            await self.initialize()
        return await self.api_methods.fetch_option_data(symbol)

    async def fetch_financial_data(self, symbol: str, report_type: str = "main") -> Any:
        """获取财务数据"""
        if not self._initialized:
            await self.initialize()
        return await self.api_methods.fetch_financial_data(symbol, report_type)

    async def fetch_holder_data(self, symbol: str) -> Any:
        """获取股东数据"""
        if not self._initialized:
            await self.initialize()
        return await self.api_methods.fetch_holder_data(symbol)

    # ==================== 通用API调用 ====================

    async def call_api(self, api_name: str, params: Dict[str, Any]) -> Any:
        """
        通用API调用接口

        Args:
            api_name: API名称
            params: 请求参数

        Returns:
            API响应数据
        """
        if not self._initialized:
            await self.initialize()
        return await self.request_handler.call_api(api_name, params)

    # ==================== 管理方法 ====================

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取统计信息

        Returns:
            包含Worker状态、缓存命中率等统计信息
        """
        stats = {
            "provider": self.name,
            "initialized": self._initialized,
            "worker_stats": self.worker_manager.get_statistics() if self._initialized else {},
            "cache_stats": self.cache_manager.get_stats() if self.cache_manager else {},
            "optimizer_stats": self.request_optimizer.get_stats() if self.request_optimizer else {},
        }
        return stats

    async def cleanup(self):
        """清理资源"""
        try:
            logger.info("开始清理AkShare代理提供者资源...")

            # 取消监控任务
            if self._monitor_task:
                self._monitor_task.cancel()
                try:
                    await self._monitor_task
                except asyncio.CancelledError:
                    pass
                self._monitor_task = None

            # 清理请求处理器
            if self.request_handler:
                await self.request_handler.cleanup()

            # 清理Worker管理器
            if self.worker_manager:
                await self.worker_manager.cleanup()

            # 清理请求优化器
            if self.request_optimizer:
                await self.request_optimizer.cleanup()

            self._initialized = False
            logger.info("AkShare代理提供者资源清理完成")

        except Exception as e:
            logger.error(f"清理资源时发生错误: {e}")

    def __str__(self):
        """字符串表示"""
        return f"AkShareProxyProvider(workers={len(self.worker_manager.worker_urls) if self.worker_manager else 0})"

    def __repr__(self):
        """详细表示"""
        return (
            f"AkShareProxyProvider("
            f"name='{self.name}', "
            f"initialized={self._initialized}, "
            f"workers={self.worker_manager.worker_urls if self.worker_manager else []}"
            f")"
        )
