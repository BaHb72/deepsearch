"""
Cloudflare Worker 代理数据提供者

通过 Cloudflare Workers 代理请求，避免 IP 限制
"""
import asyncio
import hashlib
import json
import time
import urllib.parse
import urllib.request
from typing import Dict, Any, Optional, List

try:
    import aiohttp

    HAS_AIOHTTP = True
except ImportError:
    aiohttp = None
    HAS_AIOHTTP = False

from pydantic import BaseModel, Field

from deepsearch.observability.logger import logger
from .base import DataProvider


class CloudflareConfig(BaseModel):
    """Cloudflare Worker 配置"""
    worker_url: str = Field(
        default="https://wandering-sea-d394.934073514.workers.dev",
        description="Worker URL"
    )
    timeout: int = Field(default=30, description="请求超时时间(秒)")
    retry_count: int = Field(default=3, description="重试次数")
    cache_ttl: int = Field(default=60, description="本地缓存时间(秒)")
    secret_key: Optional[str] = Field(default=None, description="API密钥")


class CloudflareProxyProvider(DataProvider):
    """
    Cloudflare Worker 代理数据提供者
    
    通过部署在 Cloudflare 边缘网络的 Worker 获取数据，
    利用全球分布式节点避免 IP 限制
    """

    def __init__(self, config: Optional[CloudflareConfig] = None):
        """
        初始化 Cloudflare 代理提供者
        
        Args:
            config: Cloudflare 配置
        """
        super().__init__("cloudflare_proxy")
        self.config = config or CloudflareConfig()
        self._session: Optional[aiohttp.ClientSession] = None
        self._cache: Dict[str, Dict[str, Any]] = {}
        self.logger = logger.bind(provider=self.name)

    async def initialize(self) -> None:
        """初始化提供者"""
        if HAS_AIOHTTP:
            if not self._session:
                self._session = aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=self.config.timeout)
                )
        else:
            self.logger.warning("aiohttp not available, using urllib fallback")
            self._session = None

        # 测试 Worker 连接
        try:
            await self._health_check()
            self.logger.info(f"Cloudflare Worker connected: {self.config.worker_url}")
        except Exception as e:
            self.logger.error(f"Failed to connect to Worker: {e}")
            raise

    async def shutdown(self) -> None:
        """关闭提供者"""
        if self._session:
            await self._session.close()
            self._session = None

    async def _health_check(self) -> bool:
        """健康检查"""
        try:
            url = f"{self.config.worker_url}/health"

            if HAS_AIOHTTP and self._session:
                async with self._session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("status") == "healthy"
            else:
                # 使用 urllib 作为后备
                with urllib.request.urlopen(url, timeout=self.config.timeout) as response:
                    if response.status == 200:
                        data = json.loads(response.read().decode())
                        return data.get("status") == "healthy"

        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return False

    def _generate_signature(self, timestamp: str) -> str:
        """
        生成请求签名
        
        Args:
            timestamp: 时间戳
            
        Returns:
            签名字符串
        """
        if not self.config.secret_key:
            return ""

        message = f"{self.config.secret_key}{timestamp}"
        return hashlib.sha256(message.encode()).hexdigest()

    def _get_cache_key(self, source: str, endpoint: str, symbol: str) -> str:
        """生成缓存键"""
        return f"{source}:{endpoint}:{symbol}"

    def _is_cache_valid(self, cache_entry: Dict[str, Any]) -> bool:
        """检查缓存是否有效"""
        if not cache_entry:
            return False

        cached_time = cache_entry.get("timestamp", 0)
        current_time = time.time()
        return (current_time - cached_time) < self.config.cache_ttl

    async def _request_with_retry(
            self,
            url: str,
            params: Optional[Dict[str, str]] = None,
            headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        带重试的请求
        
        Args:
            url: 请求URL
            params: 查询参数
            headers: 请求头
            
        Returns:
            响应数据
        """
        last_error = None

        for attempt in range(self.config.retry_count):
            try:
                async with self._session.get(
                        url,
                        params=params,
                        headers=headers
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        error_text = await response.text()
                        last_error = f"HTTP {response.status}: {error_text}"

            except asyncio.TimeoutError:
                last_error = "Request timeout"
            except Exception as e:
                last_error = str(e)

            if attempt < self.config.retry_count - 1:
                wait_time = 2 ** attempt  # 指数退避
                await asyncio.sleep(wait_time)

        raise Exception(f"Request failed after {self.config.retry_count} attempts: {last_error}")

    async def get_realtime_quote(
            self,
            symbol: str,
            source: str = "eastmoney"
    ) -> Dict[str, Any]:
        """
        获取实时行情
        
        Args:
            symbol: 股票代码
            source: 数据源 (eastmoney/sina/tencent)
            
        Returns:
            实时行情数据
        """
        # 检查缓存
        cache_key = self._get_cache_key(source, "realtime", symbol)
        if cache_key in self._cache:
            cache_entry = self._cache[cache_key]
            if self._is_cache_valid(cache_entry):
                self.logger.debug(f"Cache hit for {symbol}")
                return cache_entry["data"]

        # 构建请求
        url = f"{self.config.worker_url}/api/{source}/realtime"
        params = {"symbol": symbol}

        # 添加认证头（如果配置了密钥）
        headers = {}
        if self.config.secret_key:
            timestamp = str(int(time.time()))
            headers = {
                "X-Timestamp": timestamp,
                "X-Signature": self._generate_signature(timestamp)
            }

        try:
            # 发起请求
            data = await self._request_with_retry(url, params, headers)

            # 更新缓存
            self._cache[cache_key] = {
                "data": data,
                "timestamp": time.time()
            }

            return data

        except Exception as e:
            self.logger.error(f"Failed to get realtime quote for {symbol}: {e}")
            raise

    async def get_kline_data(
            self,
            symbol: str,
            period: str = "101",  # 101:日线, 102:周线, 103:月线
            source: str = "eastmoney"
    ) -> Dict[str, Any]:
        """
        获取K线数据
        
        Args:
            symbol: 股票代码
            period: K线周期
            source: 数据源
            
        Returns:
            K线数据
        """
        url = f"{self.config.worker_url}/api/{source}/kline"
        params = {
            "symbol": symbol,
            "period": period
        }

        try:
            data = await self._request_with_retry(url, params)
            return data
        except Exception as e:
            self.logger.error(f"Failed to get kline data for {symbol}: {e}")
            raise

    async def get_money_flow(
            self,
            symbol: str,
            source: str = "eastmoney"
    ) -> Dict[str, Any]:
        """
        获取资金流向数据
        
        Args:
            symbol: 股票代码
            source: 数据源
            
        Returns:
            资金流向数据
        """
        url = f"{self.config.worker_url}/api/{source}/flow"
        params = {"symbol": symbol}

        try:
            data = await self._request_with_retry(url, params)
            return data
        except Exception as e:
            self.logger.error(f"Failed to get money flow for {symbol}: {e}")
            raise

    async def batch_get_quotes(
            self,
            symbols: List[str],
            source: str = "eastmoney"
    ) -> List[Dict[str, Any]]:
        """
        批量获取行情
        
        Args:
            symbols: 股票代码列表
            source: 数据源
            
        Returns:
            行情数据列表
        """
        tasks = [
            self.get_realtime_quote(symbol, source)
            for symbol in symbols
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 处理结果
        valid_results = []
        for symbol, result in zip(symbols, results):
            if isinstance(result, Exception):
                self.logger.error(f"Failed to get quote for {symbol}: {result}")
                valid_results.append({
                    "symbol": symbol,
                    "error": str(result)
                })
            else:
                valid_results.append(result)

        return valid_results

    def get_status(self) -> Dict[str, Any]:
        """获取提供者状态"""
        return {
            "name": self.name,
            "type": "cloudflare_proxy",
            "worker_url": self.config.worker_url,
            "connected": self._session is not None,
            "cache_size": len(self._cache),
            "config": {
                "timeout": self.config.timeout,
                "retry_count": self.config.retry_count,
                "cache_ttl": self.config.cache_ttl
            }
        }

    async def test_connection(self) -> bool:
        """测试连接"""
        try:
            # 测试健康检查
            health_ok = await self._health_check()
            if not health_ok:
                return False

            # 测试获取数据
            data = await self.get_realtime_quote("1.000001")  # 平安银行
            return "data" in data

        except Exception as e:
            self.logger.error(f"Connection test failed: {e}")
            return False
