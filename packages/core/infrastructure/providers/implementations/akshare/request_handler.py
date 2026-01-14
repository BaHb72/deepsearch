"""
请求处理器
负责处理API请求、重试逻辑和响应处理
"""

import asyncio
import base64
import json
import time
from typing import Any, Dict, List, cast

import aiohttp
from core.config import get_config
from core.core.utils.timeout_config import get_timeout_manager
from loguru import logger

from .akshare_api_mapping import AkShareAPIMapping
from .cache_manager import get_cache_manager
from .request_optimizer import RequestOptimizer, RequestPriority
from .worker_manager import WorkerManager


class RequestHandler:
    """请求处理器"""

    def __init__(self, worker_manager: WorkerManager):
        """
        初始化请求处理器

        Args:
            worker_manager: Worker管理器实例
        """
        self.worker_manager = worker_manager
        self.session: aiohttp.ClientSession | None = None

        # 获取配置
        config = get_config()
        self.auth_key = "akshare_proxy_auth_2024"
        workers_config = getattr(config, "cloudflare_workers", None) if config else None
        auth_key = getattr(workers_config, "auth_key", None)
        if isinstance(auth_key, str) and auth_key:
            self.auth_key = auth_key

        # 请求优化器
        self.request_optimizer = RequestOptimizer()
        # 设置请求执行器为带缓存和重试的请求方法
        self.request_optimizer.executor = self._fetch_with_fallback

        # 缓存管理器
        self.cache_manager = get_cache_manager()

        # API映射
        self.api_mapping = AkShareAPIMapping()

        # 超时管理器
        self.timeout_manager = get_timeout_manager()

    async def initialize(self):
        """初始化异步会话"""
        if self.session is None:
            self.session = aiohttp.ClientSession()

    def _require_session(self) -> aiohttp.ClientSession:
        session = self.session
        if session is None:
            raise RuntimeError("HTTP session is not initialized")
        return session

    def _generate_auth_headers(self) -> Dict[str, str]:
        """
        生成认证头

        Returns:
            认证头字典
        """
        timestamp = str(int(time.time()))
        auth_string = f"{self.auth_key}:{timestamp}"
        auth_token = base64.b64encode(auth_string.encode()).decode()

        return {
            "X-Auth-Token": auth_token,
            "X-Timestamp": timestamp,
            "Content-Type": "application/json",
            "User-Agent": "DeepSearch/1.0",
        }

    def _build_url(self, base: str, path: str) -> str:
        """构建完整URL"""
        if not path.startswith("/"):
            path = f"/{path}"
        return f"{base}{path}"

    async def _fetch_direct(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        直接从 Worker 获取数据

        Args:
            path: API路径
            params: 请求参数

        Returns:
            响应数据
        """
        # 选择 Worker 节点
        worker_url = self.worker_manager.select_worker()
        if not worker_url:
            raise Exception("没有可用的 Worker 节点")

        # 构建请求
        url = self._build_url(worker_url, path)
        headers = self._generate_auth_headers()

        # 准备请求数据
        request_data = {"api": path.replace("/api/", ""), "params": params}

        try:
            logger.debug(f"发送请求到 Worker: {url}")

            # 动态获取超时时间
            timeout = self.timeout_manager.get_timeout_for_api(
                path.replace("/api/", ""), is_batch="batch" in path or "all" in params
            )

            session = self._require_session()
            async with session.post(
                url,
                json=request_data,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as response:
                response_text = await response.text()

                if response.status == 200:
                    try:
                        result = cast(Dict[str, Any], json.loads(response_text))

                        # 处理 Worker 返回的错误
                        if result.get("error"):
                            error_msg = result.get("message", "Unknown error")
                            error_code = result.get("code", "UNKNOWN")

                            # 特定错误码处理
                            if error_code == "TIMEOUT":
                                raise asyncio.TimeoutError(f"Worker timeout: {error_msg}")
                            elif error_code == "API_ERROR":
                                logger.error(f"API error from Worker: {error_msg}")
                                # 记录失败但不熔断（API问题不是Worker问题）
                                return {"error": error_msg, "data": None}
                            else:
                                raise Exception(f"Worker error: {error_msg}")

                        # 成功响应
                        self.worker_manager.record_success(worker_url)
                        return result

                    except json.JSONDecodeError as e:
                        logger.error(f"JSON 解析失败: {e}, 响应内容: {response_text[:200]}")
                        self.worker_manager.record_failure(worker_url)
                        raise Exception(f"Invalid JSON response: {e}")

                elif response.status == 401:
                    logger.error("认证失败，请检查 auth_key 配置")
                    raise Exception("Authentication failed")

                elif response.status == 429:
                    # 速率限制
                    retry_after = response.headers.get("Retry-After", "60")
                    logger.warning(f"Worker 速率限制，建议等待 {retry_after} 秒")
                    self.worker_manager.record_failure(worker_url)
                    raise Exception(f"Rate limited, retry after {retry_after} seconds")

                elif response.status == 502 or response.status == 503:
                    # Worker 不可用
                    logger.error(f"Worker {worker_url} 不可用: {response.status}")
                    self.worker_manager.record_failure(worker_url)
                    raise Exception(f"Worker unavailable: {response.status}")

                else:
                    logger.error(
                        f"Worker 返回错误状态码: {response.status}, 响应: {response_text[:200]}"
                    )
                    self.worker_manager.record_failure(worker_url)
                    raise Exception(f"Worker returned status {response.status}")

        except asyncio.TimeoutError:
            logger.error(f"请求 Worker {worker_url} 超时")
            self.worker_manager.record_failure(worker_url)
            raise
        except aiohttp.ClientError as e:
            logger.error(f"网络错误: {e}")
            self.worker_manager.record_failure(worker_url)
            raise
        except Exception as e:
            logger.error(f"请求异常: {e}")
            self.worker_manager.record_failure(worker_url)
            raise

    async def _fetch_with_fallback(
        self, api_name: str, params: Dict[str, Any], max_retries: int = 3, use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        带重试和缓存的数据获取

        Args:
            api_name: API名称
            params: 请求参数
            max_retries: 最大重试次数
            use_cache: 是否使用缓存

        Returns:
            响应数据
        """
        # 生成缓存键
        # 尝试从缓存获取
        if use_cache:
            cached = self.cache_manager.get(api_name, params)
            if isinstance(cached, dict):
                logger.debug(f"缓存命中: {api_name}")
                return cast(Dict[str, Any], cached)

        # 准备请求
        async def _do_fetch() -> Dict[str, Any]:
            for attempt in range(max_retries):
                try:
                    result = await self._fetch_direct(f"/api/{api_name}", params)

                    # 缓存成功结果
                    if use_cache and result and not result.get("error"):
                        # 根据API类型设置不同的缓存时间
                        ttl = self._get_dynamic_cache_ttl(api_name)
                        self.cache_manager.set(api_name, params, result, ttl)

                    if not isinstance(result, dict):
                        raise TypeError(
                            f"AkShare 请求返回类型异常: 期望 dict, 实际 {type(result)!r}"
                        )

                    return cast(Dict[str, Any], result)

                except asyncio.TimeoutError:
                    if attempt < max_retries - 1:
                        wait_time = (attempt + 1) * 2  # 指数退避
                        logger.warning(
                            f"超时，等待 {wait_time} 秒后重试 (尝试 {attempt + 2}/{max_retries})"
                        )
                        await asyncio.sleep(wait_time)
                    else:
                        raise

                except Exception as e:
                    if attempt < max_retries - 1:
                        logger.warning(f"请求失败: {e}, 重试 {attempt + 2}/{max_retries}")
                        await asyncio.sleep(1)
                    else:
                        raise

            raise Exception(f"请求失败，已重试 {max_retries} 次")

        return await _do_fetch()

    async def _optimized_fetch(self, api_name: str, params: Dict[str, Any]) -> Any:
        """
        优化的数据获取（使用请求优化器）

        Args:
            api_name: API名称
            params: 请求参数

        Returns:
            响应数据
        """
        # 确定优先级
        priority = self._determine_priority(api_name)

        # 添加到优化器队列
        return await self.request_optimizer.submit(api_name, params, priority, use_cache=True)

    def _determine_priority(self, api_name: str) -> RequestPriority:
        """
        确定请求优先级

        Args:
            api_name: API名称

        Returns:
            请求优先级
        """
        # 实时数据最高优先级
        if "realtime" in api_name or "spot" in api_name:
            return RequestPriority.HIGH

        # 板块、资金流等重要数据
        if any(keyword in api_name for keyword in ["sector", "fund", "hsgt", "etf"]):
            return RequestPriority.HIGH

        # 历史数据中等优先级
        if "hist" in api_name or "daily" in api_name:
            return RequestPriority.MEDIUM

        # 其他数据低优先级
        return RequestPriority.LOW

    def _get_dynamic_cache_ttl(self, api_name: str) -> int:
        """
        根据数据类型动态设置缓存时间

        Args:
            api_name: API名称

        Returns:
            缓存TTL（秒）
        """
        # 实时数据：短缓存
        if "realtime" in api_name or "spot" in api_name:
            return 30  # 30秒

        # 分时数据：中等缓存
        if "intraday" in api_name or "minute" in api_name:
            return 60  # 1分钟

        # 日线数据：长缓存
        if "daily" in api_name or "hist" in api_name:
            return 3600  # 1小时

        # 板块、概念等：中长缓存
        if "sector" in api_name or "concept" in api_name:
            return 1800  # 30分钟

        # 默认缓存时间
        return 300  # 5分钟

    def _get_dynamic_timeout(self, api_name: str) -> float:
        """
        根据API类型动态设置超时时间

        Args:
            api_name: API名称

        Returns:
            超时时间（秒）
        """
        # 批量数据需要更长超时
        if "all" in api_name or "batch" in api_name:
            return 60.0

        # 历史数据可能较慢
        if "hist" in api_name:
            return 45.0

        # 实时数据需要快速响应
        if "realtime" in api_name:
            return 15.0

        # 默认超时
        return 30.0

    async def call_api(self, api_name: str, params: Dict[str, Any]) -> Any:
        """
        调用API（公共接口）

        Args:
            api_name: API名称
            params: 请求参数

        Returns:
            API响应数据
        """
        try:
            # 使用优化的请求方式
            result = await self._optimized_fetch(api_name, params)

            if isinstance(result, dict) and result.get("error"):
                logger.error(f"API {api_name} 返回错误: {result['error']}")
                return None

            return result.get("data") if isinstance(result, dict) else result

        except Exception as e:
            logger.error(f"调用API {api_name} 失败: {e}")
            raise

    async def batch_call_api(
        self, requests: List[Dict[str, Any]], max_concurrent: int = 5
    ) -> List[Any]:
        """
        批量调用API

        Args:
            requests: 请求列表，每个请求包含 {"api": "api_name", "params": {...}}
            max_concurrent: 最大并发数

        Returns:
            响应列表
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def _call_with_semaphore(req):
            async with semaphore:
                return await self.call_api(req["api"], req.get("params", {}))

        tasks = [_call_with_semaphore(req) for req in requests]
        return await asyncio.gather(*tasks, return_exceptions=True)

    async def cleanup(self):
        """清理资源"""
        if self.session:
            await self.session.close()
            self.session = None
        await self.request_optimizer.cleanup()
