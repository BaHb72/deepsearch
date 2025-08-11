"""
Cloudflare Workers 代理管理器

管理通过 Cloudflare Workers 代理的 API 请求
"""
import asyncio
import json
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

import aiohttp
from loguru import logger

from .models import (
    WorkersConfig,
    ProxyStatus,
    ProxyStatistics,
    ProxyTestResult,
    AkShareResponse
)


class WorkersProxyManager:
    """
    Cloudflare Workers 代理管理器
    
    负责管理和路由通过 Workers 的 API 请求
    """

    def __init__(self, config: Optional[WorkersConfig] = None):
        """
        初始化代理管理器
        
        Args:
            config: Workers 配置
        """
        self.config = config or WorkersConfig()
        self.statistics = ProxyStatistics()
        self.status = ProxyStatus.DISABLED if not self.config.enabled else ProxyStatus.ENABLED

        # 缓存存储
        self._cache: Dict[str, tuple[Any, datetime]] = {}

        # HTTP 会话
        self._session: Optional[aiohttp.ClientSession] = None

        self.logger = logger.bind(component="WorkersProxy")

        # 重置统计
        self.statistics.reset()

        self.logger.info(f"Workers proxy initialized (enabled={self.config.enabled})")

    @property
    def is_enabled(self) -> bool:
        """是否启用代理"""
        return self.config.enabled and self.status == ProxyStatus.ENABLED

    async def initialize(self) -> None:
        """初始化管理器"""
        # 创建 HTTP 会话
        if not self._session:
            timeout = aiohttp.ClientTimeout(total=self.config.timeout)
            self._session = aiohttp.ClientSession(timeout=timeout)

        # 如果启用，测试连接
        if self.config.enabled:
            await self.test_connection()

        self.logger.info("Workers proxy manager initialized")

    async def shutdown(self) -> None:
        """关闭管理器"""
        if self._session:
            await self._session.close()
            self._session = None

        self.logger.info("Workers proxy manager shutdown")

    def enable(self) -> None:
        """启用代理"""
        self.config.enabled = True
        self.status = ProxyStatus.ENABLED
        self.logger.info("Workers proxy enabled")

    def disable(self) -> None:
        """禁用代理"""
        self.config.enabled = False
        self.status = ProxyStatus.DISABLED
        self.logger.info("Workers proxy disabled")

    def toggle(self) -> bool:
        """切换代理状态"""
        if self.config.enabled:
            self.disable()
        else:
            self.enable()
        return self.config.enabled

    async def test_connection(self) -> ProxyTestResult:
        """
        测试 Workers 连接
        
        Returns:
            测试结果
        """
        self.status = ProxyStatus.TESTING
        start_time = time.time()

        # 验证URL是否配置
        if not self.config.url:
            result = ProxyTestResult(
                success=False,
                response_time=0,
                status_code=None,
                message="Workers URL not configured",
                error="Please configure a valid Cloudflare Workers URL",
                timestamp=datetime.now()
            )
            self.status = ProxyStatus.ERROR
            self.logger.error("Workers test failed: URL not configured")
            return result

        # 验证URL格式
        if not self.config.url.endswith('.workers.dev') and not self.config.url.endswith('.pages.dev'):
            self.logger.warning(f"URL may not be a valid Workers domain: {self.config.url}")

        try:
            # 使用真实业务路径进行健康检查
            # 优先测试轻量级的业务API
            test_url = f"https://{self.config.url}/api/test"
            health_url = f"https://{self.config.url}/health"

            # 发送请求
            if not self._session:
                await self.initialize()

            # 总是发送 API key header，即使为空
            # 这样可以正确测试端点是否需要认证
            headers = {}
            api_key = self.config.api_key if self.config.api_key else ""
            headers['X-API-Key'] = api_key

            # 先尝试业务API测试
            try:
                async with self._session.get(test_url, headers=headers, params={"symbol": "000001"}) as test_response:
                    if test_response.status == 200:
                        response_time = (time.time() - start_time) * 1000
                        data = await test_response.json()

                        # 验证响应格式
                        if data and isinstance(data, (dict, list)):
                            result = ProxyTestResult(
                                success=True,
                                response_time=response_time,
                                status_code=test_response.status,
                                message="Workers proxy is healthy (business API tested)",
                                workers_version=data.get('version') if isinstance(data, dict) else None,
                                timestamp=datetime.now()
                            )
                            self.status = ProxyStatus.ENABLED if self.config.enabled else ProxyStatus.DISABLED
                            self.logger.info(f"Workers business API test successful (time={response_time:.2f}ms)")
                            return result
            except:
                pass  # 如果业务API测试失败，继续尝试健康检查

            # 降级到基础健康检查
            async with self._session.get(health_url, headers=headers) as response:
                response_time = (time.time() - start_time) * 1000  # 转换为毫秒

                if response.status == 200:
                    data = await response.json()

                    # 检查端点是否需要认证
                    requires_auth = data.get('requires_auth', False)
                    authenticated = data.get('authenticated', None)

                    # 如果端点需要认证但没有提供有效的 API 密钥
                    if requires_auth and not api_key:
                        result = ProxyTestResult(
                            success=False,
                            response_time=response_time,
                            status_code=response.status,
                            message="Authentication required",
                            error="This endpoint requires an API key but none was provided",
                            timestamp=datetime.now()
                        )
                        self.status = ProxyStatus.ERROR
                        self.logger.error("Workers test failed: API key required but not provided")
                        return result

                    # 如果提供了 API 密钥，验证其有效性
                    if api_key:
                        # 如果响应明确表示未认证
                        if authenticated is False:
                            result = ProxyTestResult(
                                success=False,
                                response_time=response_time,
                                status_code=response.status,
                                message="API key validation failed",
                                error="Invalid or unauthorized API key",
                                timestamp=datetime.now()
                            )
                            self.status = ProxyStatus.ERROR
                            self.logger.error("Workers test failed: Invalid API key")
                            return result
                        # 如果端点需要认证且认证成功
                        elif requires_auth and authenticated:
                            auth_msg = " (authenticated)"
                        # 如果提供了 key 但端点不需要认证
                        elif not requires_auth:
                            auth_msg = " (API key provided but not required)"
                        else:
                            auth_msg = ""
                    else:
                        # 没有提供 API key 且端点不需要认证
                        auth_msg = " (no authentication required)"

                    # 测试成功
                    result = ProxyTestResult(
                        success=True,
                        response_time=response_time,
                        status_code=response.status,
                        message="Workers proxy is healthy" + auth_msg,
                        workers_version=data.get('version'),
                        timestamp=datetime.now()
                    )

                    self.status = ProxyStatus.ENABLED if self.config.enabled else ProxyStatus.DISABLED
                    self.logger.info(f"Workers test successful (time={response_time:.2f}ms)")

                elif response.status == 401:
                    # 明确的认证失败
                    error_msg = "API key required but not provided" if not api_key else "Invalid API key"
                    result = ProxyTestResult(
                        success=False,
                        response_time=response_time,
                        status_code=response.status,
                        message="Authentication failed",
                        error=error_msg,
                        timestamp=datetime.now()
                    )

                    self.status = ProxyStatus.ERROR
                    self.logger.error(f"Workers test failed: Authentication error (HTTP 401)")

                else:
                    result = ProxyTestResult(
                        success=False,
                        response_time=response_time,
                        status_code=response.status,
                        message=f"HTTP {response.status}",
                        error=await response.text(),
                        timestamp=datetime.now()
                    )

                    self.status = ProxyStatus.ERROR
                    self.logger.error(f"Workers test failed: HTTP {response.status}")

                return result

        except asyncio.TimeoutError:
            response_time = self.config.timeout * 1000

            result = ProxyTestResult(
                success=False,
                response_time=response_time,
                message="Connection timeout",
                error="Request timed out",
                timestamp=datetime.now()
            )

            self.status = ProxyStatus.ERROR
            self.logger.error("Workers test timeout")
            return result

        except Exception as e:
            response_time = (time.time() - start_time) * 1000

            result = ProxyTestResult(
                success=False,
                response_time=response_time,
                message="Connection failed",
                error=str(e),
                timestamp=datetime.now()
            )

            self.status = ProxyStatus.ERROR
            self.logger.error(f"Workers test error: {e}")
            return result

    async def request_akshare(
            self,
            function: str,
            params: Optional[Dict[str, Any]] = None,
            use_cache: bool = True
    ) -> AkShareResponse:
        """
        通过 Workers 请求 AkShare API
        
        Args:
            function: AkShare 函数名
            params: 函数参数
            use_cache: 是否使用缓存
            
        Returns:
            API 响应
        """
        params = params or {}

        # 更新统计
        self.statistics.total_requests += 1
        self.statistics.last_request_at = datetime.now()

        # 检查缓存
        if use_cache and self.config.cache_enabled:
            cache_key = self._get_cache_key(function, params)
            cached_data = self._get_cached(cache_key)
            if cached_data is not None:
                self.statistics.successful_requests += 1
                return AkShareResponse(
                    success=True,
                    data=cached_data,
                    source="cache",
                    response_time=0,
                    cached=True,
                    timestamp=datetime.now()
                )

        # 决定使用 Workers 还是直连
        if self.is_enabled:
            try:
                response = await self._request_via_workers(function, params)
                if response.success and response.data:
                    # 只缓存有效的成功响应
                    if use_cache and self.config.cache_enabled:
                        # 验证数据不为空
                        if response.data and (isinstance(response.data, list) and len(response.data) > 0 or
                                              isinstance(response.data, dict) and response.data):
                            self._set_cached(
                                self._get_cache_key(function, params),
                                response.data,
                                status="success"
                            )
                        else:
                            # 空数据使用短TTL负缓存
                            self._set_cached(
                                self._get_cache_key(function, params),
                                response.data,
                                status="empty",
                                ttl=60  # 60秒负缓存
                            )
                elif not response.success:
                    # 失败不缓存
                    self.logger.debug(f"Request failed, not caching: {function}")
                return response

            except Exception as e:
                self.logger.error(f"Workers request failed: {e}")
                self.statistics.failed_requests += 1

                # 如果启用了故障转移
                if self.config.fallback_to_direct:
                    self.logger.info("Falling back to direct connection")
                    self.statistics.fallback_count += 1
                    return await self._request_direct(function, params)

                raise
        else:
            # 直接连接
            return await self._request_direct(function, params)

    async def _request_via_workers(
            self,
            function: str,
            params: Dict[str, Any]
    ) -> AkShareResponse:
        """
        通过 Workers 发送请求
        
        Args:
            function: 函数名
            params: 参数
            
        Returns:
            响应
        """
        start_time = time.time()

        try:
            # 构建 URL
            url = f"https://{self.config.url}/api/akshare/{function}"

            # 准备请求
            headers = {
                'Content-Type': 'application/json'
            }
            # 总是发送 API key header 以正确处理认证
            api_key = self.config.api_key if self.config.api_key else ""
            headers['X-API-Key'] = api_key

            # 发送请求
            if not self._session:
                await self.initialize()

            # 重试逻辑（带指数退避）
            last_error = None
            for attempt in range(self.config.retry_count):
                try:
                    async with self._session.post(
                            url,
                            json=params,
                            headers=headers
                    ) as response:
                        response_time = (time.time() - start_time) * 1000

                        # 更新统计
                        self.statistics.last_response_time = response_time
                        self.statistics.bytes_sent += len(json.dumps(params))

                        if response.status == 200:
                            data = await response.json()

                            # 更新统计
                            self.statistics.successful_requests += 1
                            self.statistics.bytes_received += len(await response.read())
                            self._update_avg_response_time(response_time)

                            return AkShareResponse(
                                success=True,
                                data=data.get('data'),
                                source="workers",
                                response_time=response_time,
                                cached=False,
                                timestamp=datetime.now()
                            )
                        else:
                            error_text = await response.text()
                            last_error = f"HTTP {response.status}: {error_text}"
                            self.logger.error(f"Workers returned {response.status}: {error_text}")

                            if attempt < self.config.retry_count - 1:
                                # 指数退避，最多等待10秒
                                wait_time = min(2 ** attempt * self.config.retry_delay, 10)
                                self.logger.debug(f"Retrying after {wait_time}s...")
                                await asyncio.sleep(wait_time)
                                continue

                            self.statistics.last_error = error_text
                            self.statistics.last_error_at = datetime.now()

                            return AkShareResponse(
                                success=False,
                                error=error_text,
                                source="workers",
                                response_time=response_time,
                                cached=False,
                                timestamp=datetime.now()
                            )

                except asyncio.TimeoutError:
                    last_error = "Request timeout"
                    self.logger.warning(f"Request timeout (attempt {attempt + 1}/{self.config.retry_count})")

                    # DNS/TLS类错误减少重试次数
                    if attempt < min(2, self.config.retry_count - 1):  # 最多重试2次
                        wait_time = min(2 ** attempt, 5)  # 超时后等待时间更短
                        self.logger.debug(f"Retrying after {wait_time}s...")
                        await asyncio.sleep(wait_time)
                        continue
                    break

            # 如果所有重试都失败了
            response_time = (time.time() - start_time) * 1000
            self.statistics.failed_requests += 1
            self.statistics.last_error = last_error or "All retries failed"
            self.statistics.last_error_at = datetime.now()

            return AkShareResponse(
                success=False,
                error=last_error or "All retries failed",
                source="workers",
                response_time=response_time,
                cached=False,
                timestamp=datetime.now()
            )

        except Exception as e:
            response_time = (time.time() - start_time) * 1000

            self.statistics.failed_requests += 1
            self.statistics.last_error = str(e)
            self.statistics.last_error_at = datetime.now()

            return AkShareResponse(
                success=False,
                error=str(e),
                source="workers",
                response_time=response_time,
                cached=False,
                timestamp=datetime.now()
            )

    async def _request_direct(
            self,
            function: str,
            params: Dict[str, Any]
    ) -> AkShareResponse:
        """
        直接调用 AkShare（不通过 Workers）
        
        Args:
            function: 函数名
            params: 参数
            
        Returns:
            响应
        """
        start_time = time.time()

        try:
            # 动态导入 akshare
            import akshare as ak

            # 获取函数
            if not hasattr(ak, function):
                raise ValueError(f"Unknown AkShare function: {function}")

            func = getattr(ak, function)

            # 调用函数
            # 在异步环境中运行同步函数
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, func, **params)

            response_time = (time.time() - start_time) * 1000

            # 转换 DataFrame 到 dict
            if hasattr(result, 'to_dict'):
                data = result.to_dict('records')
            else:
                data = result

            self.statistics.successful_requests += 1
            self._update_avg_response_time(response_time)

            return AkShareResponse(
                success=True,
                data=data,
                source="direct",
                response_time=response_time,
                cached=False,
                timestamp=datetime.now()
            )

        except Exception as e:
            response_time = (time.time() - start_time) * 1000

            self.statistics.failed_requests += 1
            self.statistics.last_error = str(e)
            self.statistics.last_error_at = datetime.now()

            return AkShareResponse(
                success=False,
                error=str(e),
                source="direct",
                response_time=response_time,
                cached=False,
                timestamp=datetime.now()
            )

    def _get_cache_key(self, function: str, params: Dict[str, Any]) -> str:
        """生成缓存键"""
        params_str = json.dumps(params, sort_keys=True)
        return f"{function}:{params_str}"

    def _get_cached(self, key: str) -> Optional[Any]:
        """获取缓存数据"""
        if key in self._cache:
            entry = self._cache[key]

            # 兼容旧格式
            if isinstance(entry, tuple):
                data, timestamp = entry
                if datetime.now() - timestamp < timedelta(seconds=self.config.cache_ttl):
                    return data
                else:
                    del self._cache[key]
                    return None

            # 新格式（带元数据）
            if isinstance(entry, dict):
                timestamp = entry.get("timestamp", datetime.now())
                ttl = entry.get("ttl", self.config.cache_ttl)

                # 检查是否过期
                if datetime.now() - timestamp < timedelta(seconds=ttl):
                    self.logger.debug(f"Cache hit (status={entry.get('status')}): {key}")
                    return entry.get("data")
                else:
                    # 删除过期缓存
                    del self._cache[key]
        return None

    def _set_cached(self, key: str, data: Any, status: str = "success", ttl: Optional[int] = None) -> None:
        """设置缓存数据（带元数据）"""
        cache_ttl = ttl if ttl is not None else self.config.cache_ttl
        self._cache[key] = {
            "data": data,
            "status": status,  # success, empty, error
            "timestamp": datetime.now(),
            "ttl": cache_ttl
        }

        # 限制缓存大小（简单的 LRU）
        if len(self._cache) > 100:
            # 删除最旧的缓存项
            oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k][1])
            del self._cache[oldest_key]

    def _update_avg_response_time(self, response_time: float) -> None:
        """更新平均响应时间"""
        if self.statistics.successful_requests == 1:
            self.statistics.avg_response_time = response_time
        else:
            # 移动平均
            self.statistics.avg_response_time = (
                                                        self.statistics.avg_response_time * (
                                                            self.statistics.successful_requests - 1) +
                                                        response_time
                                                ) / self.statistics.successful_requests

    def clear_cache(self) -> None:
        """清空缓存"""
        self._cache.clear()
        self.logger.info("Cache cleared")

    def get_status(self) -> Dict[str, Any]:
        """获取管理器状态"""
        # 获取配置字典并隐藏敏感信息
        config_dict = self.config.dict()
        if config_dict.get('api_key'):
            config_dict['api_key'] = '******'  # 隐藏实际的 API 密钥值

        return {
            "enabled": self.config.enabled,
            "status": self.status.value,
            "url": self.config.url,
            "statistics": self.statistics.dict(),
            "cache_size": len(self._cache),
            "config": config_dict
        }

    def update_config(self, config: WorkersConfig) -> None:
        """更新配置"""
        old_enabled = self.config.enabled
        self.config = config

        # 更新状态
        if config.enabled != old_enabled:
            self.status = ProxyStatus.ENABLED if config.enabled else ProxyStatus.DISABLED
            self.logger.info(f"Proxy {'enabled' if config.enabled else 'disabled'} via config update")

    def reset_statistics(self) -> None:
        """重置统计信息"""
        self.statistics.reset()
        self.logger.info("Statistics reset")
