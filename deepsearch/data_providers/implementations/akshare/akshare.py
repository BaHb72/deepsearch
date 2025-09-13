"""
通过 Cloudflare Workers 代理的 AkShare 数据提供者
规避 IP 封锁，提高数据获取稳定性
"""
import asyncio
import base64
import json
import time
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any, Union

try:
    import aiohttp

    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False
    aiohttp = None

try:
    import pandas as pd

    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False
    pd = None

from loguru import logger

from deepsearch.config import get_config
from deepsearch.observability.decorators.decorators import monitor_data_source
from deepsearch.observability.monitoring.data_source_monitor import DataAccessType, DataSourceType
from deepsearch.utils.network.akshare_proxy import patch_akshare
from .akshare_api_mapping import AkShareAPIMapping
from deepsearch.utils.time.market_time import MarketTimeUtil
from deepsearch.data_providers.api_config import APIConfigManager
from deepsearch.data_providers.batch_processor import BatchProcessor
from .request_optimizer import RequestOptimizer, RequestPriority
from .cache_manager import get_cache_manager
from .async_wrapper import get_async_wrapper, AkShareAsync


class WorkerState(Enum):
    """Worker 节点状态枚举"""
    HEALTHY = "healthy"         # 健康状态
    SUSPICIOUS = "suspect"       # 可疑状态（有失败但仍可尝试）
    UNHEALTHY = "unhealthy"     # 不健康状态（熔断）


class AkShareProxyProvider:
    """通过代理的 AkShare 数据提供者
    
    注意：这是一个独立的实现，不继承 DataProvider 基类，
    因为它使用 Cloudflare Workers 代理而不是传统的代理池
    """

    def __init__(self):
        self.name = "akshare_proxy"
        self.display_name = "AkShare 代理提供者"
        
        # 缓存相关配置
        self._cache_ttl = 300  # 默认5分钟缓存
        self._cache = {}  # 内存缓存

        # 延迟初始化标记
        self._patch_applied = False

        # Worker 节点池（从配置文件读取）
        # 读取 cloudflare_workers 配置
        config = get_config()
        if config and hasattr(config, 'cloudflare_workers') and config.cloudflare_workers:
            # 读取单个 URL 配置
            if hasattr(config.cloudflare_workers, 'url') and config.cloudflare_workers.url:
                url = config.cloudflare_workers.url
                # 自动添加 https:// 前缀（如果缺失）
                if not url.startswith(('http://', 'https://')):
                    url = f"https://{url}"
                self.worker_urls = [url]
                logger.info(f"使用配置的 Worker URL: {self.worker_urls[0]}")
            # 支持多个 workers（未来扩展）
            elif hasattr(config.cloudflare_workers, 'workers') and config.cloudflare_workers.workers:
                self.worker_urls = []
                for url in config.cloudflare_workers.workers:
                    if not url.startswith(('http://', 'https://')):
                        url = f"https://{url}"
                    self.worker_urls.append(url)
                logger.info(f"使用配置的 Workers 列表: {self.worker_urls}")
            else:
                # 使用实际可用的默认值
                self.worker_urls = ["https://akshare-proxy.934073514.workers.dev"]
                logger.info("使用默认 Worker URL")
        else:
            self.worker_urls = ["https://akshare-proxy.934073514.workers.dev"]
            logger.info("未找到 Cloudflare Workers 配置，使用默认 Worker URL")

        # 根据 Worker 数量选择策略
        self.strategy = "round_robin" if len(self.worker_urls) > 1 else "single"
        logger.info(f"Worker 策略: {self.strategy}, 节点数: {len(self.worker_urls)}")

        # 节点健康状态（熔断器状态机）
        self.worker_health = {url: True for url in self.worker_urls}
        self.worker_stats = {
            url: {
                "total_requests": 0,
                "success_count": 0,
                "fail_count": 0,
                "avg_latency": 0,
                "last_check": None,
                # 熔断器状态
                "state": "healthy",  # healthy, suspect, unhealthy
                "fail_streak": 0,  # 连续失败次数
                "success_streak": 0,  # 连续成功次数
                "last_transition": time.time(),  # 最后状态转换时间
                "next_retry_time": 0  # 下次半开探测时间
            } for url in self.worker_urls
        }

        # 配置
        config = get_config()
        cloudflare_config = getattr(config, 'cloudflare_workers', None)
        if cloudflare_config:
            self.api_key = getattr(cloudflare_config, 'api_key', 'default-api-key')
            self.secret_key = getattr(cloudflare_config, 'secret_key', 'default-secret-key')
        else:
            self.api_key = 'default-api-key'
            self.secret_key = 'default-secret-key'

        # 本地缓存
        self._cache = {}
        # 动态缓存TTL将根据市场状态调整

        # 轮询索引（用于负载均衡）
        self._current_worker_index = 0

        # 记忆最近成功的Worker
        self._last_successful_worker = None
        self._last_successful_time = None
        
        # 记录无效的API路径，避免重复尝试
        self._invalid_paths = set()
        
        # 批量处理器
        self.batch_processor = BatchProcessor(
            batch_timeout=0.2,
            max_batch_size=20,
            enabled=True
        )
        
        # 请求优化器（并发控制和批处理）
        self.request_optimizer = RequestOptimizer(
            max_concurrent=5,  # 限制并发为5个请求
            batch_window=0.1   # 100ms批处理窗口
        )
        self.request_optimizer.executor = self._optimized_fetch
        
        # 获取全局缓存管理器
        self.cache_manager = get_cache_manager()
        
        # 异步包装器（带超时控制）
        self.async_wrapper = get_async_wrapper(timeout=10.0)
        self.ak_async = AkShareAsync(timeout=10.0)
        
        # 配置管理器
        from deepsearch.config.data_source_config import get_config_manager
        self.config_manager = get_config_manager()

    async def initialize(self):
        """初始化并测试所有 Worker 节点"""
        logger.info(f"初始化 {self.display_name}")
        
        # 注册配置变更回调
        self._register_config_callback()

        # 检查依赖
        if not HAS_AIOHTTP:
            logger.warning("aiohttp 未安装，AkShare 代理提供者将无法正常工作")
            logger.warning("请运行: pip install aiohttp")
            return

        if not HAS_PANDAS:
            logger.warning("pandas 未安装，数据处理功能将受限")
            logger.warning("请运行: pip install pandas")

        # 测试所有节点
        health_tasks = []
        for url in self.worker_urls:
            health_tasks.append(self._check_worker_health(url))

        results = await asyncio.gather(*health_tasks, return_exceptions=True)

        for url, result in zip(self.worker_urls, results):
            if isinstance(result, Exception):
                logger.error(f"Worker {url} 健康检查失败: {result}")
                self.worker_health[url] = False
            else:
                self.worker_health[url] = result
                logger.info(f"Worker {url}: {'健康' if result else '异常'}")

        # 启动健康监控任务
        asyncio.create_task(self.monitor_worker_health())
        
        # 启动请求优化器
        await self.request_optimizer.start()
        logger.info("请求优化器已启动")

        # 检查是否有可用节点
        if not any(self.worker_health.values()):
            logger.warning("没有可用的 Worker 节点，将尝试直接访问")

    async def _check_worker_health(self, url: str) -> bool:
        """检查 Worker 节点健康状态"""
        try:
            async with aiohttp.ClientSession() as session:
                # 首先检查基础健康端点
                headers = self._generate_auth_headers()

                # 使用真实业务路径进行健康检查
                # 测试一个轻量级的查询，比如获取测试股票的信息
                test_url = self._build_url(url, "/eastmoney/test")

                async with session.get(
                        test_url,
                        headers=headers,
                        params={"symbol": "000001"},  # 平安银行作为测试
                        timeout=aiohttp.ClientTimeout(total=3)  # 健康检查使用短超时
                ) as response:
                    if response.status == 200:
                        try:
                            data = await response.json()
                            # 验证响应格式
                            if data and (isinstance(data, dict) or isinstance(data, list)):
                                self.worker_stats[url]["last_check"] = datetime.now()
                                self._update_worker_state(url, True)
                                logger.debug(f"Worker {url} 健康检查成功")
                                return True
                        except json.JSONDecodeError:
                            logger.warning(f"Worker {url} 返回无效JSON")
                            return False
                    elif response.status == 404:
                        # 如果测试端点不存在，尝试基础健康检查
                        health_url = self._build_url(url, "/health")
                        async with session.get(
                                health_url,
                                headers=headers,
                                timeout=aiohttp.ClientTimeout(total=3)
                        ) as health_response:
                            if health_response.status == 200:
                                self.worker_stats[url]["last_check"] = datetime.now()
                                logger.debug(f"Worker {url} 基础健康检查成功")
                                return True

                    logger.debug(f"Worker {url} 健康检查失败: HTTP {response.status}")
                    return False

        except asyncio.TimeoutError:
            logger.debug(f"Worker {url} 健康检查超时")
            return False
        except Exception as e:
            logger.debug(f"Worker {url} 健康检查失败: {e}")
            return False

    def _build_url(self, base: str, path: str) -> str:
        """构建URL，确保正确的斜杠处理"""
        # 移除base末尾的斜杠，移除path开头的斜杠
        base = base.rstrip('/')
        path = path.lstrip('/')
        return f"{base}/{path}"

    def _generate_auth_headers(self) -> Dict[str, str]:
        """生成认证头"""
        timestamp = str(int(time.time() * 1000))

        # 生成签名（简化版，与 Worker 中的验证对应）
        signature_data = f"{self.api_key}{timestamp}"
        signature = base64.b64encode(
            (signature_data + self.secret_key).encode()
        ).decode()

        return {
            "X-API-Key": self.api_key,
            "X-Timestamp": timestamp,
            "X-Signature": signature
        }

    def _update_worker_state(self, url: str, state: Union[bool, WorkerState]) -> None:
        """更新Worker状态（熔断器逻辑）
        
        Args:
            url: Worker URL
            state: 可以是布尔值（成功/失败）或 WorkerState 枚举（直接设置状态）
        """
        stats = self.worker_stats[url]

        # 如果传入的是 WorkerState 枚举，直接设置状态
        if isinstance(state, WorkerState):
            old_state = stats["state"]
            new_state = state.value
            
            if old_state != new_state:
                logger.info(f"Worker {url} 状态变更: {old_state} -> {new_state}")
                stats["state"] = new_state
                stats["last_transition"] = time.time()
                
                # 更新健康标记
                if new_state == "unhealthy":
                    self.worker_health[url] = False
                    stats["next_retry_time"] = time.time() + 10  # 10秒后半开探测（优化恢复速度）
                    stats["fail_streak"] = 5  # 设置失败计数以保持一致性
                elif new_state == "suspect":
                    stats["fail_streak"] = 3  # 设置失败计数以保持一致性
                elif new_state == "healthy":
                    self.worker_health[url] = True
                    stats["fail_streak"] = 0
                    stats["success_streak"] = 0
            return

        # 原有的布尔值逻辑
        success = state
        if success:
            stats["success_streak"] += 1
            stats["fail_streak"] = 0

            # 成功后的状态转换
            if stats["state"] in ["suspect", "unhealthy"]:
                # 半开成功，恢复健康
                logger.info(f"Worker {url} 恢复健康状态")
                stats["state"] = "healthy"
                stats["last_transition"] = time.time()
                self.worker_health[url] = True
        else:
            stats["fail_streak"] += 1
            stats["success_streak"] = 0

            # 失败后的状态转换
            if stats["state"] == "healthy":
                if stats["fail_streak"] >= 3:
                    # 连续3次失败，进入可疑状态
                    logger.warning(f"Worker {url} 进入可疑状态")
                    stats["state"] = "suspect"
                    stats["last_transition"] = time.time()
            elif stats["state"] == "suspect":
                if stats["fail_streak"] >= 5:
                    # 再失败2次，进入不健康状态
                    logger.error(f"Worker {url} 进入不健康状态")
                    stats["state"] = "unhealthy"
                    stats["last_transition"] = time.time()
                    stats["next_retry_time"] = time.time() + 10  # 10秒后半开探测（优化恢复速度）
                    self.worker_health[url] = False

    def _can_use_worker(self, url: str) -> bool:
        """判断是否可以使用该Worker"""
        stats = self.worker_stats[url]

        if stats["state"] == "healthy":
            return True
        elif stats["state"] == "suspect":
            # 可疑状态仍可尝试，但优先级降低
            return True
        elif stats["state"] == "unhealthy":
            # 检查是否可以半开探测
            if time.time() >= stats["next_retry_time"]:
                logger.info(f"Worker {url} 进行半开探测")
                return True
            return False
        return False

    def _select_worker(self) -> Optional[str]:
        """智能选择 Worker 节点"""
        # 获取可用的节点（包括健康和可疑状态）
        available_workers = [
            url for url in self.worker_urls
            if self._can_use_worker(url)
        ]

        # 优先选择健康的节点
        healthy_workers = [
            url for url in available_workers
            if self.worker_stats[url]["state"] == "healthy"
        ]

        # 如果有最近成功的Worker且仍然健康，优先使用
        if (self._last_successful_worker and
                self._last_successful_worker in healthy_workers and
                self._last_successful_time and
                time.time() - self._last_successful_time < 60):  # 60秒内优先使用
            logger.debug(f"使用最近成功的 Worker: {self._last_successful_worker}")
            return self._last_successful_worker

        # 如果没有健康节点，但有可疑节点，使用可疑节点
        if not healthy_workers and available_workers:
            logger.warning("没有健康节点，使用可疑/半开节点")
            healthy_workers = available_workers

        if not healthy_workers:
            logger.error("没有可用的 Worker 节点")
            return None

        # 根据策略选择节点
        if self.strategy == "single" or len(healthy_workers) == 1:
            # 单节点模式或只有一个健康节点
            return healthy_workers[0]
        elif self.strategy == "round_robin":
            # 轮询负载均衡
            self._current_worker_index = (self._current_worker_index + 1) % len(healthy_workers)
            selected = healthy_workers[self._current_worker_index % len(healthy_workers)]
            logger.debug(f"轮询选择 Worker [{self._current_worker_index}]: {selected}")
            return selected
        else:
            # 智能选择：基于成功率和延迟
            best_worker = None
            best_score = -1

            for url in healthy_workers:
                stats = self.worker_stats[url]
                total = stats["total_requests"]
                if total == 0:
                    # 新节点，给予尝试机会
                    score = 1.0
                else:
                    # 计算成功率和延迟综合评分
                    success_rate = stats["success_count"] / total
                    latency_score = 1.0 / (1 + stats["avg_latency"] / 1000)  # 延迟越低分数越高
                    score = success_rate * 0.7 + latency_score * 0.3

                if score > best_score:
                    best_score = score
                    best_worker = url

            return best_worker

    async def _optimized_fetch(self, api_name: str, params: Dict[str, Any]) -> Any:
        """
        优化的获取方法，供RequestOptimizer调用
        
        Args:
            api_name: API名称
            params: 请求参数
        
        Returns:
            API响应结果
        """
        # 直接调用原有的fetch方法
        return await self._fetch_with_fallback(api_name, params)
    
    async def _fetch_with_fallback(
            self,
            path: str,
            params: Dict[str, Any],
            max_retries: int = 3
    ) -> Dict[str, Any]:
        """带故障转移的数据获取"""
        # 先检查缓存
        cached_data = self.cache_manager.get(path, params)
        if cached_data is not None:
            logger.debug(f"缓存命中: {path}")
            return cached_data
            
        from deepsearch.utils.patterns.retry_handler import RetryHandler, RetryConfig, RetryStrategy

        # 创建重试处理器（在 DeepSearch 端控制重试）
        retry_config = RetryConfig(
            max_retries=max_retries,
            strategy=RetryStrategy.ADAPTIVE,  # 自适应策略
            base_delay=1.0,
            max_delay=30.0,
            jitter=True,
            error_configs={
                429: {"max_retries": 5, "base_delay": 2.0},  # CloudFlare 限流
                503: {"max_retries": 3, "base_delay": 1.0},  # 服务不可用
                502: {"max_retries": 2, "base_delay": 0.5},  # 网关错误
            }
        )
        retry_handler = RetryHandler(retry_config)

        last_error = None
        tried_workers = set()

        # 内部函数，用于执行实际请求
        async def _do_fetch():
            nonlocal last_error, tried_workers

            # 直接使用 akshare，它会自动通过已配置的代理
            # 不需要手动构建HTTP请求到Worker
            return await self._fetch_direct(path, params)

        # 使用重试处理器执行请求（重试逻辑在 DeepSearch 端）
        try:
            result = await retry_handler.retry_async(
                _do_fetch,
                source_name=f"CloudFlare-{path}"
            )
            # 缓存成功的结果
            if result and not result.get("error"):
                self.cache_manager.set(path, params, result)
                logger.debug(f"数据已缓存: {path}")
            return result
        except Exception as e:
            logger.error(f"所有尝试失败（包括重试）: {e}")
            # 记录重试统计
            stats = retry_handler.get_stats()
            logger.info(f"重试统计: {stats}")
            raise Exception(f"请求失败: {last_error or str(e)}")

    async def _fetch_direct(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """直接访问数据源（备用方案）"""
        # 延迟应用补丁（第一次使用时才应用）
        if not self._patch_applied:
            try:
                patch_akshare()
                self._patch_applied = True
                logger.info("AkShare proxy patch applied on first use")
            except Exception as e:
                logger.warning(f"Failed to apply akshare patch: {e}")
                # 继续执行，即使补丁失败也可以尝试直连
        
        # 检查是否启用直连回退
        config = get_config()
        cloudflare_config = getattr(config, 'cloudflare_workers', None)
        if cloudflare_config:
            fallback_enabled = getattr(cloudflare_config, 'fallback_to_direct', True)
        else:
            fallback_enabled = True

        if not fallback_enabled:
            # 未启用直连，抛出明确异常
            error_msg = "All Workers unavailable and direct access is disabled"
            logger.error(error_msg)
            raise Exception(error_msg)

        logger.info(f"使用直连模式访问 AkShare，函数: {path}")

        # 如果启用了直连，尝试使用AkShare
        try:
            # 检查是否安装了akshare
            try:
                import akshare as ak
            except ImportError:
                logger.error("AkShare not installed for direct access")
                raise Exception("AkShare library not available for direct access")

            # 标准化路径和参数
            function_name = AkShareAPIMapping.normalize_path(path)
            params = AkShareAPIMapping.transform_params(function_name, params)
            
            # 根据函数名调用对应的 AkShare API
            if function_name == "stock_zh_a_spot_em":
                # 获取所有股票实时数据
                logger.info(f"调用 ak.stock_zh_a_spot_em")
                # 所有 akshare 调用都会通过 Worker 代理（如果配置了）
                df = await asyncio.get_event_loop().run_in_executor(
                    None, ak.stock_zh_a_spot_em
                )
                if df is not None and not df.empty:
                    # 重命名列以避免编码问题
                    df = df.rename(columns={
                        '序号': 'index',
                        '代码': 'code',
                        '名称': 'name',
                        '最新价': 'price',
                        '涨跌幅': 'change_pct',
                        '涨跌额': 'change',
                        '成交量': 'volume',
                        '成交额': 'amount',
                        '振幅': 'amplitude',
                        '最高': 'high',
                        '最低': 'low',
                        '今开': 'open',
                        '昨收': 'prev_close',
                        '换手率': 'turnover_rate',
                        '市盈率-动态': 'pe_dynamic',
                        '市净率': 'pb',
                        '总市值': 'total_value',
                        '流通市值': 'circulating_value',
                        '涨速': 'rise_speed',
                        '5分钟涨跌': 'five_min_change',
                        '60日涨跌幅': 'sixty_day_change',
                        '年初至今涨跌幅': 'year_to_date'
                    })
                    result = {"data": df.to_dict('records'), "_data_source": "direct:akshare"}
                    return result
                return {"data": [], "_data_source": "direct:akshare"}

            elif function_name == "stock_individual_info_em":
                symbol = params.get("symbol")
                if symbol:
                    logger.info(f"调用 ak.stock_individual_info_em: {symbol}")
                    df = await asyncio.get_event_loop().run_in_executor(
                        None, ak.stock_individual_info_em, symbol
                    )
                    if df is not None and not df.empty:
                        return {"data": df.to_dict('records'), "_data_source": "direct:akshare"}
                    return {"data": [], "_data_source": "direct:akshare"}
            
            elif function_name == "stock_info_a_code_name":
                logger.info(f"调用 ak.stock_info_a_code_name")
                df = await asyncio.get_event_loop().run_in_executor(
                    None, ak.stock_info_a_code_name
                )
                if df is not None and not df.empty:
                    return {"data": df.to_dict('records'), "_data_source": "direct:akshare"}
                return {"data": [], "_data_source": "direct:akshare"}
            
            elif function_name == "stock_cyq_em":
                symbol = params.get("symbol")
                adjust = params.get("adjust", "qfq")
                if symbol:
                    logger.info(f"调用 ak.stock_cyq_em: {symbol} {adjust}")
                    df = await asyncio.get_event_loop().run_in_executor(
                        None, ak.stock_cyq_em, symbol, adjust
                    )
                    if df is not None and not df.empty:
                        return {"data": df.to_dict('records'), "_data_source": "direct:akshare"}
                    return {"data": [], "_data_source": "direct:akshare"}
            
            elif function_name == "stock_zh_index_spot_em":
                # 注意：stock_zh_index_spot_em 不接受参数，忽略任何传入的参数
                logger.info(f"调用 ak.stock_zh_index_spot_em (无参数)")
                df = await asyncio.get_event_loop().run_in_executor(
                    None, ak.stock_zh_index_spot_em  # 不传递任何参数
                )
                if df is not None and not df.empty:
                    # 重命名列以避免编码问题
                    df = df.rename(columns={
                        '序号': 'index',
                        '代码': 'code',
                        '名称': 'name',
                        '最新价': 'price',
                        '涨跌幅': 'change_pct',
                        '涨跌额': 'change',
                        '成交量': 'volume',
                        '成交额': 'amount',
                        '振幅': 'amplitude',
                        '最高': 'high',
                        '最低': 'low',
                        '今开': 'open',
                        '昨收': 'prev_close',
                        '量比': 'volume_ratio'
                    })
                    return {"data": df.to_dict('records'), "_data_source": "direct:akshare"}
                return {"data": [], "_data_source": "direct:akshare"}
            
            elif function_name == "stock_zh_b_spot_em":
                logger.info(f"调用 ak.stock_zh_b_spot_em")
                df = await asyncio.get_event_loop().run_in_executor(
                    None, ak.stock_zh_b_spot_em
                )
                if df is not None and not df.empty:
                    return {"data": df.to_dict('records'), "_data_source": "direct:akshare"}
                return {"data": [], "_data_source": "direct:akshare"}
            
            elif function_name == "stock_kc_a_spot_em":
                logger.info(f"调用 ak.stock_kc_a_spot_em")
                df = await asyncio.get_event_loop().run_in_executor(
                    None, ak.stock_kc_a_spot_em
                )
                if df is not None and not df.empty:
                    return {"data": df.to_dict('records'), "_data_source": "direct:akshare"}
                return {"data": [], "_data_source": "direct:akshare"}
            
            elif function_name == "stock_zh_a_st_em":
                logger.info(f"调用 ak.stock_zh_a_st_em")
                df = await asyncio.get_event_loop().run_in_executor(
                    None, ak.stock_zh_a_st_em
                )
                if df is not None and not df.empty:
                    return {"data": df.to_dict('records'), "_data_source": "direct:akshare"}
                return {"data": [], "_data_source": "direct:akshare"}
            
            # 保留原有的 eastmoney 路径兼容性（已废弃）
            elif path == "/eastmoney/realtime":
                symbol = params.get("symbol")
                if symbol:
                    logger.warning(f"使用已废弃的路径 /eastmoney/realtime，建议改用 /api/akshare/stock_zh_a_spot_em")
                    df = await asyncio.get_event_loop().run_in_executor(
                        None, ak.stock_zh_a_spot_em
                    )
                    if df is not None and not df.empty:
                        stock_data = df[df['代码'] == symbol]
                        if not stock_data.empty:
                            return {"data": stock_data.to_dict('records'), "_data_source": "direct:akshare"}
                    return {"data": [], "_data_source": "direct:akshare"}

            elif path == "/eastmoney/kline":
                symbol = params.get("symbol")
                period = params.get("period", "daily")
                start = params.get("start")
                end = params.get("end")
                adjust = params.get("adjust", "")
                if symbol:
                    logger.warning(f"使用已废弃的路径 /eastmoney/kline，建议改用 /api/akshare/stock_zh_a_hist")
                    df = await asyncio.get_event_loop().run_in_executor(
                        None,
                        ak.stock_zh_a_hist,
                        symbol,
                        period,
                        start,
                        end,
                        adjust
                    )
                    if df is not None and not df.empty:
                        return {"data": df.to_dict('records'), "_data_source": "direct:akshare"}
                    return {"data": [], "_data_source": "direct:akshare"}

            elif function_name == "stock_zh_a_hist":
                symbol = params.get("symbol")
                period = params.get("period", "daily")
                start = params.get("start_date") or params.get("start")
                end = params.get("end_date") or params.get("end")
                adjust = params.get("adjust", "")
                if symbol:
                    logger.info(f"调用 ak.stock_zh_a_hist: {symbol} {period}")
                    # 通过 Worker 代理（如果配置了）
                    df = await asyncio.get_event_loop().run_in_executor(
                        None,
                        ak.stock_zh_a_hist,
                        symbol,
                        period,
                        start,
                        end,
                        adjust
                    )
                    if df is not None and not df.empty:
                        return {"data": df.to_dict('records'), "_data_source": "direct:akshare"}
                    return {"data": [], "_data_source": "direct:akshare"}
            elif function_name == "stock_zh_a_hist_min_em":
                symbol = params.get("symbol")
                start = params.get("start_date") or params.get("start")
                end = params.get("end_date") or params.get("end")
                period = params.get("period", "1")
                adjust = params.get("adjust", "")
                if symbol:
                    logger.info(f"调用 ak.stock_zh_a_hist_min_em: {symbol} {period}")
                    # 通过 Worker 代理（如果配置了）
                    df = await asyncio.get_event_loop().run_in_executor(
                        None,
                        ak.stock_zh_a_hist_min_em,
                        symbol,
                        start,
                        end,
                        period,
                        adjust
                    )
                    if df is not None and not df.empty:
                        return {"data": df.to_dict('records'), "_data_source": "direct:akshare"}
                    return {"data": [], "_data_source": "direct:akshare"}
            
            elif function_name == "stock_sse_summary":
                logger.info(f"调用 ak.stock_sse_summary")
                df = await asyncio.get_event_loop().run_in_executor(
                    None, ak.stock_sse_summary
                )
                if df is not None and not df.empty:
                    return {"data": df.to_dict('records'), "_data_source": "direct:akshare"}
                return {"data": [], "_data_source": "direct:akshare"}
            
            elif function_name == "stock_szse_summary":
                date = params.get("date")
                logger.info(f"调用 ak.stock_szse_summary: {date}")
                if date:
                    # 转换日期格式 2024-01-01 -> 20240101
                    date = date.replace("-", "")
                    df = await asyncio.get_event_loop().run_in_executor(
                        None, ak.stock_szse_summary, date
                    )
                else:
                    df = await asyncio.get_event_loop().run_in_executor(
                        None, ak.stock_szse_summary
                    )
                if df is not None and not df.empty:
                    return {"data": df.to_dict('records'), "_data_source": "direct:akshare"}
                return {"data": [], "_data_source": "direct:akshare"}
            
            # 板块数据类API
            elif function_name == "stock_board_industry_name_em":
                logger.info(f"调用 ak.stock_board_industry_name_em")
                df = await asyncio.get_event_loop().run_in_executor(
                    None, ak.stock_board_industry_name_em
                )
                if df is not None and not df.empty:
                    return {"data": df.to_dict('records'), "_data_source": "direct:akshare"}
                return {"data": [], "_data_source": "direct:akshare"}
            
            elif function_name == "stock_board_concept_name_em":
                logger.info(f"调用 ak.stock_board_concept_name_em")
                df = await asyncio.get_event_loop().run_in_executor(
                    None, ak.stock_board_concept_name_em
                )
                if df is not None and not df.empty:
                    return {"data": df.to_dict('records'), "_data_source": "direct:akshare"}
                return {"data": [], "_data_source": "direct:akshare"}
            
            # 同花顺概念板块API
            elif function_name == "stock_board_concept_name_ths":
                logger.info(f"调用 ak.stock_board_concept_name_ths")
                # 检查函数是否存在
                if not hasattr(ak, 'stock_board_concept_name_ths'):
                    logger.error("AkShare版本不支持stock_board_concept_name_ths函数")
                    return {"data": [], "_data_source": "direct:akshare", "error": "Function not supported"}
                df = await asyncio.get_event_loop().run_in_executor(
                    None, ak.stock_board_concept_name_ths
                )
                if df is not None and not df.empty:
                    return {"data": df.to_dict('records'), "_data_source": "direct:akshare"}
                return {"data": [], "_data_source": "direct:akshare"}
            
            elif function_name == "stock_board_concept_index_ths":
                symbol = params.get("symbol")
                start_date = params.get("start_date", "20200101")
                end_date = params.get("end_date", "20250321")
                logger.info(f"调用 ak.stock_board_concept_index_ths: {symbol}")
                # 检查函数是否存在
                if not hasattr(ak, 'stock_board_concept_index_ths'):
                    logger.error("AkShare版本不支持stock_board_concept_index_ths函数")
                    return {"data": [], "_data_source": "direct:akshare", "error": "Function not supported"}
                df = await asyncio.get_event_loop().run_in_executor(
                    None, ak.stock_board_concept_index_ths, symbol, start_date, end_date
                )
                if df is not None and not df.empty:
                    return {"data": df.to_dict('records'), "_data_source": "direct:akshare"}
                return {"data": [], "_data_source": "direct:akshare"}
            
            elif function_name == "stock_board_concept_info_ths":
                symbol = params.get("symbol")
                logger.info(f"调用 ak.stock_board_concept_info_ths: {symbol}")
                # 检查函数是否存在
                if not hasattr(ak, 'stock_board_concept_info_ths'):
                    logger.error("AkShare版本不支持stock_board_concept_info_ths函数")
                    return {"data": [], "_data_source": "direct:akshare", "error": "Function not supported"}
                df = await asyncio.get_event_loop().run_in_executor(
                    None, ak.stock_board_concept_info_ths, symbol
                )
                if df is not None and not df.empty:
                    return {"data": df.to_dict('records'), "_data_source": "direct:akshare"}
                return {"data": [], "_data_source": "direct:akshare"}
            
            elif function_name == "stock_board_concept_cons_ths":
                symbol = params.get("symbol")
                logger.info(f"调用 ak.stock_board_concept_cons_ths: {symbol}")
                # 检查函数是否存在
                if not hasattr(ak, 'stock_board_concept_cons_ths'):
                    logger.error("AkShare版本不支持stock_board_concept_cons_ths函数")
                    return {"data": [], "_data_source": "direct:akshare", "error": "Function not supported"}
                df = await asyncio.get_event_loop().run_in_executor(
                    None, ak.stock_board_concept_cons_ths, symbol
                )
                if df is not None and not df.empty:
                    return {"data": df.to_dict('records'), "_data_source": "direct:akshare"}
                return {"data": [], "_data_source": "direct:akshare"}
            
            # 涨跌停和异动数据
            elif function_name == "stock_zt_pool_em":
                date = params.get("date")
                logger.info(f"调用 ak.stock_zt_pool_em: {date}")
                if date:
                    df = await asyncio.get_event_loop().run_in_executor(
                        None, ak.stock_zt_pool_em, date
                    )
                else:
                    df = await asyncio.get_event_loop().run_in_executor(
                        None, ak.stock_zt_pool_em
                    )
                if df is not None and not df.empty:
                    return {"data": df.to_dict('records'), "_data_source": "direct:akshare"}
                return {"data": [], "_data_source": "direct:akshare"}
            
            elif function_name == "stock_zt_pool_dtgc_em":
                date = params.get("date")
                logger.info(f"调用 ak.stock_zt_pool_dtgc_em: {date}")
                if date:
                    df = await asyncio.get_event_loop().run_in_executor(
                        None, ak.stock_zt_pool_dtgc_em, date
                    )
                else:
                    df = await asyncio.get_event_loop().run_in_executor(
                        None, ak.stock_zt_pool_dtgc_em
                    )
                if df is not None and not df.empty:
                    return {"data": df.to_dict('records'), "_data_source": "direct:akshare"}
                return {"data": [], "_data_source": "direct:akshare"}
            
            # 沪深港通数据
            elif function_name == "stock_hsgt_fund_flow_summary_em":
                logger.info(f"调用 ak.stock_hsgt_fund_flow_summary_em")
                df = await asyncio.get_event_loop().run_in_executor(
                    None, ak.stock_hsgt_fund_flow_summary_em
                )
                if df is not None and not df.empty:
                    # 记录原始列名用于调试
                    logger.debug(f"原始列名: {df.columns.tolist()}")
                    
                    # 重命名所有列以避免编码问题
                    # 注意：需要完全覆盖所有可能的列名
                    rename_map = {
                        '日期时间': 'date_time',
                        '名称': 'name',
                        '类型': 'type',
                        '资金流向': 'flow_direction',
                        '买卖方向': 'trade_direction',
                        '买卖状态': 'trade_status',  # 可能是买卖状态而不是买卖方向
                        '成交净买额': 'net_buy',
                        '资金净流入': 'net_inflow',
                        '累计净流入额': 'total_net_inflow',
                        '领涨股': 'leading_stock',
                        '涨跌平家数': 'rise_fall_count',
                        '最低价': 'low',
                        '相关指数': 'related_index',
                        '指数涨跌幅': 'index_change',
                        # 添加其他可能的列名映射
                        '板块': 'sector',
                        '日期': 'date'
                    }
                    
                    # 只重命名存在的列
                    actual_renames = {}
                    for old_col, new_col in rename_map.items():
                        if old_col in df.columns:
                            actual_renames[old_col] = new_col
                    
                    if actual_renames:
                        df = df.rename(columns=actual_renames)
                        logger.debug(f"重命名后列名: {df.columns.tolist()}")
                    
                    return {"data": df.to_dict('records'), "_data_source": "direct:akshare"}
                return {"data": [], "_data_source": "direct:akshare"}
            
            # 分时数据
            elif function_name == "stock_intraday_em":
                symbol = params.get("symbol")
                if symbol:
                    logger.info(f"调用 ak.stock_intraday_em: {symbol}")
                    df = await asyncio.get_event_loop().run_in_executor(
                        None, ak.stock_intraday_em, symbol
                    )
                    if df is not None and not df.empty:
                        return {"data": df.to_dict('records'), "_data_source": "direct:akshare"}
                    return {"data": [], "_data_source": "direct:akshare"}

            # 未匹配的路径
            logger.warning(f"直连模式不支持路径: {path}")
            return {"error": f"Path {path} not supported in direct mode", "data": [],
                    "_data_source": "direct:unsupported"}

        except Exception as e:
            logger.error(f"直连访问失败: {e}")
            # 直连也失败，但不要缓存错误
            raise Exception(f"Direct access failed: {str(e)}")

    async def get_realtime_data(self, symbols: List[str]) -> Dict[str, Any]:
        """获取实时数据"""
        if not symbols:
            return {"timestamp": datetime.now().isoformat(), "data": [], "data_source": "none"}

        # 检查本地缓存
        cache_key = f"realtime:{','.join(symbols)}"
        cached_entry = self._get_cache_entry(cache_key)
        if cached_entry:
            # 根据缓存状态决定TTL
            ttl = 10 if cached_entry["status"] == "success" else 30
            if time.time() - cached_entry["timestamp"] < ttl:
                logger.debug(f"使用缓存数据 (status={cached_entry['status']}): {cache_key}")
                # 添加缓存标识
                if isinstance(cached_entry["data"], dict):
                    cached_entry["data"]["data_source"] = "cache"
                return cached_entry["data"]

        # 直接使用 akshare 库获取数据
        # 如果配置了 Worker，会自动通过代理
        try:
            import akshare as ak

            logger.info(f"获取股票实时数据: {symbols}")

            # 获取所有股票数据（带超时控制）
            df = await self.async_wrapper.call_with_timeout(
                ak.stock_zh_a_spot_em,
                timeout=15  # 15秒超时
            )

            # 判断数据源
            from deepsearch.utils.network.proxy_client import get_proxy_client
            client = get_proxy_client()
            if client.use_proxy:
                data_source = f"proxy:{client.worker_url}"
            else:
                data_source = "direct:akshare"

        except Exception as e:
            logger.error(f"获取实时数据失败: {e}")
            return {"timestamp": datetime.now().isoformat(), "data": [], "data_source": "error"}

        # 整合结果
        data = {
            "timestamp": datetime.now().isoformat(),
            "data": [],
            "data_source": data_source
        }

        has_valid_data = False

        if df is not None and not df.empty:
            # 转换为字典列表
            all_stocks = df.to_dict('records')

            # 创建代码映射以快速查找
            stock_map = {}
            for item in all_stocks:
                code = item.get("代码")
                if code:
                    stock_map[code] = item

            # 筛选需要的股票
            for symbol in symbols:
                if symbol in stock_map:
                    data["data"].append(stock_map[symbol])
                    has_valid_data = True
                else:
                    logger.warning(f"未找到股票 {symbol} 的数据")

        # 智能缓存策略
        if has_valid_data:
            # 有效数据，正常缓存
            self._set_cache_entry(cache_key, data, "success", ttl=300)
        elif len(data["data"]) == 0:
            # 空数据，短TTL负缓存
            self._set_cache_entry(cache_key, data, "empty", ttl=60)
            logger.warning(f"获取实时数据为空，设置负缓存: {cache_key}")
        # 注意：完全失败不缓存

        return data

    async def get_history_data(
            self,
            symbol: str,
            start_date: str,
            end_date: str,
            period: str = "daily"
    ) -> pd.DataFrame:
        """获取历史数据"""
        # 检查本地缓存
        cache_key = f"history:{symbol}:{start_date}:{end_date}:{period}"
        cached_entry = self._get_cache_entry(cache_key)
        if cached_entry:
            ttl = self._cache_ttl if cached_entry["status"] == "success" else 60
            if time.time() - cached_entry["timestamp"] < ttl:
                logger.debug(f"使用缓存历史数据 (status={cached_entry['status']}): {cache_key}")
                return cached_entry["data"]

        try:
            import akshare as ak

            logger.info(f"获取历史数据: {symbol} {period} {start_date}-{end_date}")

            # 直接使用 akshare，会自动通过代理（如果配置了）
            df = await asyncio.get_event_loop().run_in_executor(
                None,
                ak.stock_zh_a_hist,
                symbol,
                period,
                start_date,
                end_date,
                ""
            )

            # 验证数据有效性
            if df is not None and not df.empty:
                # 设置日期索引
                if "日期" in df.columns:
                    df["日期"] = pd.to_datetime(df["日期"])
                    df.set_index("日期", inplace=True)

                # 缓存有效数据
                self._set_cache_entry(cache_key, df, "success", ttl=self._cache_ttl)
                return df
            else:
                # 空数据，短TTL负缓存
                df = pd.DataFrame()
                self._set_cache_entry(cache_key, df, "empty", ttl=60)
                logger.warning(f"历史数据为空: {cache_key}")
                return df

        except Exception as e:
            logger.error(f"获取历史数据失败: {e}")
            # 失败不缓存，直接返回空数据
            return pd.DataFrame()

    async def monitor_worker_health(self):
        """持续监控 Worker 健康状态"""
        while True:
            try:
                # 每分钟检查一次
                await asyncio.sleep(60)

                for url in self.worker_urls:
                    old_health = self.worker_health[url]
                    new_health = await self._check_worker_health(url)

                    if new_health != old_health:
                        logger.info(
                            f"Worker {url} 状态变化: "
                            f"{'异常→健康' if new_health else '健康→异常'}"
                        )
                        self.worker_health[url] = new_health

            except Exception as e:
                logger.error(f"健康监控错误: {e}")

    def _get_cache_entry(self, key: str) -> Optional[Dict[str, Any]]:
        """获取缓存条目（包含元数据）"""
        from deepsearch.data_providers.utils import get_cache

        cache = get_cache()

        # 根据key判断数据类型
        if "realtime" in key or "spot" in key:
            data_type = "realtime"
        elif "history" in key or "hist" in key:
            if "min" in key or "minute" in key:
                data_type = "minute"
            else:
                data_type = "daily"
        elif "info" in key:
            data_type = "info"
        else:
            data_type = "daily"

        # 从新缓存系统获取数据
        cached_data = cache.get(data_type, key)
        if cached_data:
            # 使用动态TTL检查缓存是否过期
            ttl = MarketTimeUtil.get_cache_ttl(data_type)
            if time.time() - cached_data.get("timestamp", 0) < ttl:
                return cached_data
            else:
                # 缓存过期，删除
                cache.delete(data_type, key)

        # 兼容旧的本地缓存（逐步迁移）
        if hasattr(self, '_cache') and key in self._cache:
            return self._cache[key]

        return None

    def _set_cache_entry(self, key: str, data: Any, status: str, ttl: Optional[int] = None):
        """设置缓存条目（包含元数据）"""
        # 使用新的统一缓存系统
        from deepsearch.data_providers.utils import get_cache

        cache = get_cache()

        # 根据数据类型选择合适的缓存分类
        if "realtime" in key or "spot" in key:
            data_type = "realtime"
        elif "history" in key or "hist" in key:
            if "min" in key or "minute" in key:
                data_type = "minute"
            else:
                data_type = "daily"
        elif "info" in key:
            data_type = "info"
        else:
            data_type = "daily"  # 默认使用daily缓存

        # 如果没有指定TTL，使用动态TTL（考虑用户配置）
        if ttl is None:
            ttl = self._get_dynamic_cache_ttl(data_type)

        # 包装数据，保留元数据
        wrapped_data = {
            "data": data,
            "status": status,
            "timestamp": time.time()
        }

        cache.set(data_type, key, wrapped_data, ttl)

        # 定期清理（每100次设置后清理一次）
        if hasattr(self, '_cache_set_count'):
            self._cache_set_count += 1
        else:
            self._cache_set_count = 1

        if self._cache_set_count % 100 == 0:
            cache.cleanup_all()

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        total_requests = sum(s["total_requests"] for s in self.worker_stats.values())
        total_success = sum(s["success_count"] for s in self.worker_stats.values())

        # 统计缓存状态
        cache_stats = {"success": 0, "empty": 0, "error": 0}
        for entry in self._cache.values():
            status = entry.get("status", "unknown")
            if status in cache_stats:
                cache_stats[status] += 1

        return {
            "provider": self.name,
            "display_name": self.display_name,
            "total_requests": total_requests,
            "success_rate": total_success / total_requests if total_requests > 0 else 0,
            "worker_count": len(self.worker_urls),
            "healthy_workers": sum(1 for h in self.worker_health.values() if h),
            "worker_stats": self.worker_stats,
            "cache_size": len(self._cache),
            "cache_stats": cache_stats
        }
    
    @monitor_data_source(
        source=DataSourceType.CLOUDFLARE,
        access_type=DataAccessType.HISTORICAL_KLINE,
        extract_symbol=lambda *args, **kwargs: kwargs.get('params', {}).get('symbol')
    )
    async def call_api(self, api_name: str, params: Dict[str, Any]) -> Any:
        """
        通用API调用方法
        
        Args:
            api_name: API名称
            params: API参数
            
        Returns:
            API返回数据
        """
        try:
            # 判断请求优先级
            priority = self._determine_priority(api_name)
            
            # 使用请求优化器提交请求
            result = await self.request_optimizer.submit(
                api_name=api_name,
                params=params,
                priority=priority,
                use_cache=True  # 启用去重缓存
            )
            return result
        except Exception as e:
            logger.error(f"调用API {api_name} 失败: {e}")
            return {"error": str(e), "success": False}
    
    def _determine_priority(self, api_name: str) -> RequestPriority:
        """
        根据API名称确定请求优先级
        
        Args:
            api_name: API名称
            
        Returns:
            请求优先级
        """
        # 实时数据 - 紧急
        if any(keyword in api_name for keyword in ["intraday", "bid_ask", "realtime"]):
            return RequestPriority.URGENT
        
        # 用户交互数据 - 高优先级
        elif any(keyword in api_name for keyword in ["spot", "individual_info", "cyq"]):
            return RequestPriority.HIGH
        
        # 批量数据 - 可批处理
        elif any(keyword in api_name for keyword in ["board", "industry", "concept", "all"]):
            return RequestPriority.BATCH
        
        # 历史数据 - 低优先级
        elif any(keyword in api_name for keyword in ["hist", "daily", "weekly", "monthly"]):
            return RequestPriority.LOW
        
        # 默认正常优先级
        else:
            return RequestPriority.NORMAL
    
    async def fetch_sector_data(self, api_name: str, params: Dict[str, Any]) -> Any:
        """获取板块数据"""
        return await self.call_api(api_name, params)
    
    async def fetch_anomaly_data(self, api_name: str, params: Dict[str, Any]) -> Any:
        """获取异动数据"""
        return await self.call_api(api_name, params)
    
    async def fetch_hsgt_data(self, api_name: str, params: Dict[str, Any]) -> Any:
        """获取沪深港通数据"""
        return await self.call_api(api_name, params)
    
    @monitor_data_source(
        source=DataSourceType.CLOUDFLARE,
        access_type=DataAccessType.REALTIME_QUOTE,
        extract_symbol=lambda *args, **kwargs: "ALL_MARKET"
    )
    async def fetch_all_realtime_quotes(self) -> Any:
        """获取全市场实时行情"""
        return await self.call_api("stock_zh_a_spot_em", {})
    
    @monitor_data_source(
        source=DataSourceType.CLOUDFLARE,
        access_type=DataAccessType.TICK_DATA,
        extract_symbol=lambda *args, **kwargs: args[1] if len(args) > 1 else kwargs.get('symbol')
    )
    async def fetch_intraday_data(self, symbol: str) -> Any:
        """获取分时数据"""
        return await self.call_api("stock_intraday_em", {"symbol": symbol})
    
    @monitor_data_source(
        source=DataSourceType.CLOUDFLARE,
        access_type=DataAccessType.ORDERBOOK,
        extract_symbol=lambda *args, **kwargs: args[1] if len(args) > 1 else kwargs.get('symbol')
    )
    async def fetch_orderbook_data(self, symbol: str) -> Any:
        """获取盘口数据"""
        return await self.call_api("stock_bid_ask_em", {"symbol": symbol})
    
    async def cleanup(self):
        """清理资源"""
        logger.info("清理 AkShareProxyProvider 资源")
        # 停止请求优化器
        if hasattr(self, 'request_optimizer'):
            await self.request_optimizer.stop()
        # 清理缓存
        self._cache.clear()
    
    def _register_config_callback(self):
        """注册配置变更回调"""
        def on_config_change(config):
            """配置变更时更新本地参数"""
            logger.info(f"数据源配置更新: {config.mode.value}模式")
            
            # 更新批量处理器配置
            self.batch_processor.enabled = config.batch_enabled
            self.batch_processor.batch_timeout = config.batch_timeout
            self.batch_processor.max_batch_size = config.max_batch_size
            
            # 更新重试配置
            if hasattr(self, 'retry_config'):
                self.retry_config.base_delay = config.retry_base_delay
                self.retry_config.max_delay = config.retry_max_delay
            
            logger.info(f"配置已应用 - 速率限制: {config.global_rate_limit}/s, "
                       f"批量: {'启用' if config.batch_enabled else '禁用'}")
        
        self.config_manager.register_change_callback(on_config_change)
    
    def _get_dynamic_timeout(self, api_name: str) -> float:
        """获取动态超时时间"""
        # 从配置管理器获取当前配置
        config = self.config_manager.config
        
        # 获取基础超时
        base_timeout = APIConfigManager.get_timeout(api_name)
        
        # 应用全局倍数
        return base_timeout * config.global_timeout_multiplier
    
    def _get_dynamic_cache_ttl(self, data_type: str) -> int:
        """获取动态缓存TTL"""
        # 从配置管理器获取数据类型配置
        dt_config = self.config_manager.get_data_type_config(data_type)
        config = self.config_manager.config
        
        # 应用全局倍数
        return int(dt_config.cache_ttl * config.global_cache_multiplier)
