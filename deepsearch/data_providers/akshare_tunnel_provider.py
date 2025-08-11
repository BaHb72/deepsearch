"""
AkShare Tunnel 数据提供者

通过 Cloudflare Tunnel 访问 AkShare API 服务器
"""
import asyncio
import json
import urllib.parse
import urllib.request
from typing import Dict, Any, Optional, List

from pydantic import BaseModel, Field

from deepsearch.observability.logger import logger
from .base import DataProvider


class AkShareTunnelConfig(BaseModel):
    """AkShare Tunnel 配置"""
    tunnel_url: str = Field(
        default="https://akshare-api.yourdomain.com",
        description="Cloudflare Tunnel URL"
    )
    api_key: Optional[str] = Field(default=None, description="API密钥")
    timeout: int = Field(default=30, description="请求超时时间(秒)")
    retry_count: int = Field(default=3, description="重试次数")


class AkShareTunnelProvider(DataProvider):
    """
    AkShare Tunnel 数据提供者
    
    通过 Cloudflare Tunnel 访问部署的 AkShare API 服务器
    """

    def __init__(self, config: Optional[AkShareTunnelConfig] = None):
        """
        初始化 AkShare Tunnel 提供者
        
        Args:
            config: 配置对象
        """
        super().__init__("akshare_tunnel")
        self.config = config or AkShareTunnelConfig()
        self.logger = logger.bind(provider=self.name)
        self._connected = False

    async def initialize(self) -> None:
        """初始化提供者"""
        try:
            # 测试连接
            await self._health_check()
            self._connected = True
            self.logger.info(f"AkShare Tunnel connected: {self.config.tunnel_url}")
        except Exception as e:
            self.logger.error(f"Failed to connect to AkShare Tunnel: {e}")
            self._connected = False
            raise

    async def shutdown(self) -> None:
        """关闭提供者"""
        self._connected = False
        self.logger.info("AkShare Tunnel provider shutdown")

    async def _health_check(self) -> bool:
        """健康检查"""
        try:
            url = f"{self.config.tunnel_url}/health"

            # 创建请求
            req = urllib.request.Request(url)
            if self.config.api_key:
                req.add_header('X-API-Key', self.config.api_key)

            # 发送请求
            with urllib.request.urlopen(req, timeout=self.config.timeout) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode())
                    return data.get("status") == "healthy"

        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return False

    async def _request(
            self,
            endpoint: str,
            method: str = "GET",
            params: Optional[Dict[str, Any]] = None,
            data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        发送请求到 AkShare API
        
        Args:
            endpoint: API 端点
            method: HTTP 方法
            params: 查询参数
            data: POST 数据
            
        Returns:
            响应数据
        """
        # 构建 URL
        url = f"{self.config.tunnel_url}{endpoint}"
        if params and method == "GET":
            query_string = urllib.parse.urlencode(params)
            url = f"{url}?{query_string}"

        # 重试逻辑
        last_error = None
        for attempt in range(self.config.retry_count):
            try:
                # 创建请求
                if method == "POST" and data:
                    post_data = json.dumps(data).encode('utf-8')
                    req = urllib.request.Request(
                        url,
                        data=post_data,
                        method=method
                    )
                    req.add_header('Content-Type', 'application/json')
                else:
                    req = urllib.request.Request(url, method=method)

                # 添加认证头
                if self.config.api_key:
                    req.add_header('X-API-Key', self.config.api_key)

                # 发送请求
                with urllib.request.urlopen(req, timeout=self.config.timeout) as response:
                    if response.status == 200:
                        result = json.loads(response.read().decode())
                        if result.get("success"):
                            return result
                        else:
                            last_error = result.get("message", "Unknown error")
                    else:
                        last_error = f"HTTP {response.status}"

            except urllib.error.HTTPError as e:
                last_error = f"HTTP {e.code}: {e.reason}"
                if e.code == 401:
                    raise Exception("Invalid API key")
            except urllib.error.URLError as e:
                last_error = f"Network error: {e.reason}"
            except Exception as e:
                last_error = str(e)

            # 等待后重试
            if attempt < self.config.retry_count - 1:
                wait_time = 2 ** attempt
                await asyncio.sleep(wait_time)
                self.logger.debug(f"Retrying after {wait_time}s...")

        raise Exception(f"Request failed after {self.config.retry_count} attempts: {last_error}")

    async def get_stock_realtime(
            self,
            symbol: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        获取实时行情
        
        Args:
            symbol: 股票代码（可选，None 获取全部）
            
        Returns:
            实时行情数据
        """
        params = {}
        if symbol:
            params["symbol"] = symbol

        try:
            result = await self._request("/api/stock/realtime", params=params)
            return result.get("data", [])
        except Exception as e:
            self.logger.error(f"Failed to get realtime quote: {e}")
            raise

    async def get_stock_history(
            self,
            symbol: str,
            start_date: Optional[str] = None,
            end_date: Optional[str] = None,
            period: str = "daily",
            adjust: str = "qfq"
    ) -> Dict[str, Any]:
        """
        获取历史K线数据
        
        Args:
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            period: 周期
            adjust: 复权方式
            
        Returns:
            历史数据
        """
        data = {
            "symbol": symbol,
            "start_date": start_date,
            "end_date": end_date,
            "period": period,
            "adjust": adjust
        }

        try:
            result = await self._request("/api/stock/history", method="POST", data=data)
            return result.get("data", [])
        except Exception as e:
            self.logger.error(f"Failed to get stock history: {e}")
            raise

    async def get_stock_minute(
            self,
            symbol: str,
            period: str = "1"
    ) -> Dict[str, Any]:
        """
        获取分钟K线数据
        
        Args:
            symbol: 股票代码
            period: 分钟周期（1, 5, 15, 30, 60）
            
        Returns:
            分钟数据
        """
        params = {
            "symbol": symbol,
            "period": period
        }

        try:
            result = await self._request("/api/stock/minute", params=params)
            return result.get("data", [])
        except Exception as e:
            self.logger.error(f"Failed to get minute data: {e}")
            raise

    async def get_stock_info(
            self,
            symbol: str
    ) -> Dict[str, Any]:
        """
        获取个股信息
        
        Args:
            symbol: 股票代码
            
        Returns:
            个股信息
        """
        params = {"symbol": symbol}

        try:
            result = await self._request("/api/stock/info", params=params)
            return result.get("data", [])
        except Exception as e:
            self.logger.error(f"Failed to get stock info: {e}")
            raise

    async def get_stock_list(self) -> List[Dict[str, Any]]:
        """
        获取股票列表
        
        Returns:
            股票列表
        """
        try:
            result = await self._request("/api/stock/list")
            return result.get("data", [])
        except Exception as e:
            self.logger.error(f"Failed to get stock list: {e}")
            raise

    async def test_connection(self) -> bool:
        """测试连接"""
        try:
            # 测试健康检查
            health_ok = await self._health_check()
            if not health_ok:
                return False

            # 测试获取数据
            data = await self.get_stock_realtime("000001")
            return data is not None

        except Exception as e:
            self.logger.error(f"Connection test failed: {e}")
            return False

    def get_status(self) -> Dict[str, Any]:
        """获取提供者状态"""
        return {
            "name": self.name,
            "type": "akshare_tunnel",
            "tunnel_url": self.config.tunnel_url,
            "connected": self._connected,
            "has_api_key": bool(self.config.api_key),
            "config": {
                "timeout": self.config.timeout,
                "retry_count": self.config.retry_count
            }
        }
