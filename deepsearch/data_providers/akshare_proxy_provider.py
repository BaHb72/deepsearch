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


class AkShareProxyProvider:
    """通过代理的 AkShare 数据提供者
    
    注意：这是一个独立的实现，不继承 DataProvider 基类，
    因为它使用 Cloudflare Workers 代理而不是传统的代理池
    """

    def __init__(self):
        self.name = "akshare_proxy"
        self.display_name = "AkShare 代理提供者"

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
                self.worker_urls = ["https://wandering-sea-d394.934073514.workers.dev"]
                logger.info("使用默认 Worker URL")
        else:
            self.worker_urls = ["https://wandering-sea-d394.934073514.workers.dev"]
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
        last_error = None
        tried_workers = set()

        for attempt in range(max_retries):
            # 选择未尝试过的 Worker
            worker_url = self._select_worker()

            if not worker_url or worker_url in tried_workers:
                # 如果没有可用 Worker，尝试直接访问
                logger.warning("所有Worker不可用，尝试直接访问模式")
                try:
                    return await self._fetch_direct(path, params)
                except Exception as e:
                    # 直连也失败，不要继续重试
                    logger.error(f"直接访问模式失败: {e}")
                    raise

            tried_workers.add(worker_url)

            try:
                start_time = time.time()

                async with aiohttp.ClientSession() as session:
                    headers = self._generate_auth_headers()
                    # 自动将裸函数名映射到 AkShare API 路径
                    mapped_path = path
                    if not mapped_path.startswith('/'):
                        mapped_path = f"/api/akshare/{mapped_path}"
                    url = self._build_url(worker_url, mapped_path)

                    async with session.get(
                            url,
                            params=params,
                            headers=headers,
                            timeout=aiohttp.ClientTimeout(total=30)
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

                            return data
                        else:
                            stats["fail_count"] += 1
                            last_error = f"HTTP {response.status}"

                            # 如果是认证失败，不要标记节点为不健康
                            if response.status != 401:
                                self._update_worker_state(worker_url, False)

            except asyncio.TimeoutError:
                last_error = "请求超时"
                self.worker_stats[worker_url]["fail_count"] += 1
                self._update_worker_state(worker_url, False)
                logger.warning(f"Worker {worker_url} 请求超时")

            except Exception as e:
                last_error = str(e)
                self.worker_stats[worker_url]["fail_count"] += 1
                self._update_worker_state(worker_url, False)
                logger.warning(f"Worker {worker_url} 请求失败: {e}")

            # 指数退避重试
            if attempt < max_retries - 1:
                wait_time = min(2 ** attempt, 10)  # 最多等待10秒
                logger.debug(f"等待 {wait_time} 秒后重试...")
                await asyncio.sleep(wait_time)

        raise Exception(f"所有尝试失败: {last_error}")

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

        # 如果启用了直连，尝试使用AkShare
        try:
            # 检查是否安装了akshare
            try:
                import akshare as ak
            except ImportError:
                logger.error("AkShare not installed for direct access")
                raise Exception("AkShare library not available for direct access")

            # 根据path映射到akshare函数
            # 这里只实现几个常用的映射
            if path == "/eastmoney/realtime":
                symbol = params.get("symbol")
                if symbol:
                    # 获取实时行情
                    logger.info(f"直连获取{symbol}实时数据")
                    df = await asyncio.get_event_loop().run_in_executor(
                        None, ak.stock_zh_a_spot_em
                    )
                    if df is not None and not df.empty:
                        # 筛选特定股票
                        stock_data = df[df['代码'] == symbol]
                        if not stock_data.empty:
                            return {"data": stock_data.to_dict('records')}
                    return {"data": []}

            elif path == "/eastmoney/kline":
                symbol = params.get("symbol")
                period = params.get("period", "daily")
                start = params.get("start")
                end = params.get("end")
                adjust = params.get("adjust", "")

                if symbol:
                    logger.info(f"直连获取{symbol}历史K线")
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
                        return {"data": df.to_dict('records')}
                    return {"data": []}

            # 直连处理 AkShare 函数路径
            elif path in ("stock_zh_a_hist", "/api/akshare/stock_zh_a_hist"):
                symbol = params.get("symbol")
                period = params.get("period", "daily")
                start = params.get("start_date") or params.get("start")
                end = params.get("end_date") or params.get("end")
                adjust = params.get("adjust", "")
                if symbol:
                    logger.info(f"直连调用 ak.stock_zh_a_hist: {symbol} {period}")
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
                        return {"data": df.to_dict('records')}
                    return {"data": []}
            elif path in ("stock_zh_a_hist_min_em", "/api/akshare/stock_zh_a_hist_min_em"):
                symbol = params.get("symbol")
                start = params.get("start_date") or params.get("start")
                end = params.get("end_date") or params.get("end")
                period = params.get("period", "1")
                adjust = params.get("adjust", "")
                if symbol:
                    logger.info(f"直连调用 ak.stock_zh_a_hist_min_em: {symbol} {period}")
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
                        return {"data": df.to_dict('records')}
                    return {"data": []}

            # 未匹配的路径
            logger.warning(f"直连模式不支持路径: {path}")
            return {"error": f"Path {path} not supported in direct mode", "data": []}

        except Exception as e:
            logger.error(f"直连访问失败: {e}")
            # 直连也失败，但不要缓存错误
            raise Exception(f"Direct access failed: {str(e)}")

    async def get_realtime_data(self, symbols: List[str]) -> Dict[str, Any]:
        """获取实时数据"""
        if not symbols:
            return {"timestamp": datetime.now().isoformat(), "data": []}

        # 检查本地缓存
        cache_key = f"realtime:{','.join(symbols)}"
        cached_entry = self._get_cache_entry(cache_key)
        if cached_entry:
            # 根据缓存状态决定TTL
            ttl = 10 if cached_entry["status"] == "success" else 30
            if time.time() - cached_entry["timestamp"] < ttl:
                logger.debug(f"使用缓存数据 (status={cached_entry['status']}): {cache_key}")
                return cached_entry["data"]

        tasks = []
        for symbol in symbols:
            task = self._fetch_with_fallback(
                "/eastmoney/realtime",
                {"symbol": symbol}
            )
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 整合结果
        data = {
            "timestamp": datetime.now().isoformat(),
            "data": []
        }

        has_valid_data = False
        for symbol, result in zip(symbols, results):
            if isinstance(result, Exception):
                logger.error(f"获取 {symbol} 数据失败: {result}")
                continue
            if result and isinstance(result, dict):
                data["data"].append({
                    "symbol": symbol,
                    **result
                })
                has_valid_data = True

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
            result = await self._fetch_with_fallback(
                "/eastmoney/kline",
                {
                    "symbol": symbol,
                    "period": period,
                    "start": start_date,
                    "end": end_date
                }
            )

            # 转换为 DataFrame
            if result and "data" in result and result["data"]:
                df = pd.DataFrame(result["data"])
                if "date" in df.columns:
                    df["date"] = pd.to_datetime(df["date"])
                    df.set_index("date", inplace=True)

                # 验证数据有效性
                if not df.empty and len(df) > 0:
                    # 有效数据，正常缓存
                    self._set_cache_entry(cache_key, df, "success", ttl=self._cache_ttl)
                    return df
                else:
                    # 空数据，短TTL负缓存
                    self._set_cache_entry(cache_key, df, "empty", ttl=60)
                    logger.warning(f"历史数据为空，设置负缓存: {cache_key}")
                    return df
            else:
                # 返回空 DataFrame，短TTL负缓存
                df = pd.DataFrame()
                self._set_cache_entry(cache_key, df, "empty", ttl=60)
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
        if key in self._cache:
            return self._cache[key]
        return None

    def _set_cache_entry(self, key: str, data: Any, status: str, ttl: int = 300):
        """设置缓存条目（包含元数据）"""
        self._cache[key] = {
            "data": data,
            "status": status,  # success, empty, error
            "timestamp": time.time(),
            "ttl": ttl
        }

        # 限制缓存大小
        if len(self._cache) > 1000:
            # 清理过期的缓存
            current_time = time.time()
            expired_keys = [
                k for k, v in self._cache.items()
                if current_time - v.get("timestamp", 0) > v.get("ttl", 300)
            ]
            for k in expired_keys:
                del self._cache[k]

            # 如果还是太多，删除最旧的
            if len(self._cache) > 1000:
                oldest_keys = sorted(
                    self._cache.keys(),
                    key=lambda k: self._cache[k].get("timestamp", 0)
                )[:100]
                for k in oldest_keys:
                    del self._cache[k]

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
