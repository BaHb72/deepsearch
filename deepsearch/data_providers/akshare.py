"""
通过 Cloudflare Workers 代理的 AkShare 数据提供者
规避 IP 封锁，提高数据获取稳定性
"""
import asyncio
import base64
import json
import time
from datetime import datetime
from typing import Dict, List, Optional, Any

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

from deepsearch.config import settings
from deepsearch.utils.akshare_proxy import patch_akshare


class AkShareProxyProvider:
    """通过代理的 AkShare 数据提供者
    
    注意：这是一个独立的实现，不继承 DataProvider 基类，
    因为它使用 Cloudflare Workers 代理而不是传统的代理池
    """

    def __init__(self):
        self.name = "akshare_proxy"
        self.display_name = "AkShare 代理提供者"

        # 应用代理补丁，让 akshare 通过 Worker 代理
        patch_akshare()

        # Worker 节点池（从配置文件读取）
        # 读取 cloudflare_workers 配置
        if hasattr(settings, 'cloudflare_workers') and settings.cloudflare_workers:
            # 读取单个 URL 配置
            if hasattr(settings.cloudflare_workers, 'url') and settings.cloudflare_workers.url:
                url = settings.cloudflare_workers.url
                # 自动添加 https:// 前缀（如果缺失）
                if not url.startswith(('http://', 'https://')):
                    url = f"https://{url}"
                self.worker_urls = [url]
                logger.info(f"使用配置的 Worker URL: {self.worker_urls[0]}")
            # 支持多个 workers（未来扩展）
            elif hasattr(settings.cloudflare_workers, 'workers') and settings.cloudflare_workers.workers:
                self.worker_urls = []
                for url in settings.cloudflare_workers.workers:
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
        cloudflare_config = getattr(settings, 'cloudflare_workers', None)
        if cloudflare_config:
            self.api_key = getattr(cloudflare_config, 'api_key', 'default-api-key')
            self.secret_key = getattr(cloudflare_config, 'secret_key', 'default-secret-key')
        else:
            self.api_key = 'default-api-key'
            self.secret_key = 'default-secret-key'

        # 本地缓存
        self._cache = {}
        self._cache_ttl = 300  # 5分钟本地缓存

        # 轮询索引（用于负载均衡）
        self._current_worker_index = 0

        # 记忆最近成功的Worker
        self._last_successful_worker = None
        self._last_successful_time = None

    async def initialize(self):
        """初始化并测试所有 Worker 节点"""
        logger.info(f"初始化 {self.display_name}")

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
                        timeout=aiohttp.ClientTimeout(total=5)
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

    def _update_worker_state(self, url: str, success: bool) -> None:
        """更新Worker状态（熔断器逻辑）"""
        stats = self.worker_stats[url]

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
                    stats["next_retry_time"] = time.time() + 60  # 60秒后半开探测
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

    async def _fetch_with_fallback(
            self,
            path: str,
            params: Dict[str, Any],
            max_retries: int = 3
    ) -> Dict[str, Any]:
        """带故障转移的数据获取"""
        from deepsearch.data_providers.utils import SmartRetry, RetryConfig, RetryStrategy

        # 创建智能重试器
        retry_config = RetryConfig(
            max_attempts=max_retries,
            strategy=RetryStrategy.EXPONENTIAL,
            base_delay=1.0,
            max_delay=10.0,
            jitter=True,
            exceptions=(aiohttp.ClientError, asyncio.TimeoutError, Exception)
        )
        smart_retry = SmartRetry(retry_config=retry_config)

        last_error = None
        tried_workers = set()

        # 内部函数，用于执行实际请求
        async def _do_fetch():
            nonlocal last_error, tried_workers

            # 选择未尝试过的 Worker
            worker_url = self._select_worker()

            if not worker_url or worker_url in tried_workers:
                # 如果没有可用 Worker，尝试直接访问
                logger.warning("所有Worker不可用，尝试直接访问模式")
                return await self._fetch_direct(path, params)

            tried_workers.add(worker_url)

            start_time = time.time()

            async with aiohttp.ClientSession() as session:
                headers = self._generate_auth_headers()
                # 自动将裸函数名映射到 AkShare API 路径
                mapped_path = path
                if not mapped_path.startswith('/'):
                    mapped_path = f"/api/akshare/{mapped_path}"
                url = self._build_url(worker_url, mapped_path)

                logger.info(f"使用 Worker 代理: {worker_url}, 请求路径: {mapped_path}")

                async with session.get(
                        url,
                        params=params,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=10)  # 优化：从30秒减少到10秒
                ) as response:
                    latency = (time.time() - start_time) * 1000  # 毫秒

                    # 更新统计
                    stats = self.worker_stats[worker_url]
                    stats["total_requests"] += 1

                    if response.status == 200:
                        data = await response.json()

                        # 更新成功统计
                        stats["success_count"] += 1
                        stats["avg_latency"] = (
                                stats["avg_latency"] * 0.9 + latency * 0.1
                        )  # 指数移动平均

                        # 更新状态（使用熔断器）
                        self._update_worker_state(worker_url, True)

                        # 记忆成功的Worker
                        self._last_successful_worker = worker_url
                        self._last_successful_time = time.time()

                        # 添加数据源标识
                        if isinstance(data, dict):
                            data["_data_source"] = f"workers:{worker_url}"

                        return data
                    else:
                        stats["fail_count"] += 1
                        last_error = f"HTTP {response.status}"

                        # 如果是认证失败，不要标记节点为不健康
                        if response.status != 401:
                            self._update_worker_state(worker_url, False)

                        raise aiohttp.ClientResponseError(
                            request_info=response.request_info,
                            history=response.history,
                            status=response.status
                        )

        # 使用智能重试执行请求
        try:
            return await smart_retry.execute(_do_fetch)
        except Exception as e:
            logger.error(f"所有尝试失败: {e}")
            raise Exception(f"所有尝试失败: {last_error or str(e)}")

    async def _fetch_direct(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """直接访问数据源（备用方案）"""
        # 检查是否启用直连回退
        cloudflare_config = getattr(settings, 'cloudflare_workers', None)
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

            # 根据path映射到akshare函数
            # 处理 AkShare 函数调用
            if path == "stock_zh_a_spot_em" or path == "/api/akshare/stock_zh_a_spot_em":
                # 获取所有股票实时数据
                logger.info(f"调用 ak.stock_zh_a_spot_em")
                # 所有 akshare 调用都会通过 Worker 代理（如果配置了）
                df = await asyncio.get_event_loop().run_in_executor(
                    None, ak.stock_zh_a_spot_em
                )
                if df is not None and not df.empty:
                    result = {"data": df.to_dict('records'), "_data_source": "direct:akshare"}
                    return result
                return {"data": [], "_data_source": "direct:akshare"}

            # 保留原有的 eastmoney 路径兼容性（暂时）
            elif path == "/eastmoney/realtime":
                symbol = params.get("symbol")
                if symbol:
                    logger.info(f"获取{symbol}实时数据 (兼容模式)")
                    # 注意：通过 Worker 代理（如果配置了）
                    df = await asyncio.get_event_loop().run_in_executor(
                        None, ak.stock_zh_a_spot_em
                    )
                    if df is not None and not df.empty:
                        # 筛选特定股票
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
                    logger.info(f"获取{symbol}历史K线 (兼容模式)")
                    # 注意：通过 Worker 代理（如果配置了）
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

            # 直连处理 AkShare 函数路径
            elif path in ("stock_zh_a_hist", "/api/akshare/stock_zh_a_hist"):
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
            elif path in ("stock_zh_a_hist_min_em", "/api/akshare/stock_zh_a_hist_min_em"):
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

            # 获取所有股票数据
            df = await asyncio.get_event_loop().run_in_executor(
                None, ak.stock_zh_a_spot_em
            )

            # 判断数据源
            from deepsearch.utils.proxy_client import get_proxy_client
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
            return cached_data

        # 兼容旧的本地缓存（逐步迁移）
        if hasattr(self, '_cache') and key in self._cache:
            return self._cache[key]

        return None

    def _set_cache_entry(self, key: str, data: Any, status: str, ttl: int = 300):
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
