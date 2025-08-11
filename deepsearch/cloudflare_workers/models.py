"""
Cloudflare Workers 代理数据模型
"""
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any

from pydantic import BaseModel, Field


class ProxyStatus(str, Enum):
    """代理状态枚举"""
    ENABLED = "enabled"
    DISABLED = "disabled"
    ERROR = "error"
    TESTING = "testing"


class WorkersConfig(BaseModel):
    """Workers 代理配置"""
    # 基本配置
    enabled: bool = Field(default=False, description="是否启用代理")
    url: str = Field(
        default="",  # 默认为空，强制用户配置真实的Workers URL
        description="Workers 域名（例如：your-worker.workers.dev）"
    )

    # 请求配置
    timeout: int = Field(default=30, description="请求超时时间（秒）")
    retry_count: int = Field(default=3, description="重试次数")
    retry_delay: int = Field(default=1, description="重试延迟（秒）")

    # 认证配置（如果需要）
    api_key: Optional[str] = Field(None, description="API 密钥")

    # 故障转移
    fallback_to_direct: bool = Field(
        default=True,
        description="Workers 失败时是否自动切换到直连"
    )

    # 缓存配置
    cache_enabled: bool = Field(default=True, description="是否启用缓存")
    cache_ttl: int = Field(default=300, description="缓存过期时间（秒）")

    class Config:
        json_schema_extra = {
            "example": {
                "enabled": True,
                "url": "wandering-sea-d394.934073514.workers.dev",
                "timeout": 30,
                "retry_count": 3,
                "fallback_to_direct": True
            }
        }


class ProxyStatistics(BaseModel):
    """代理统计信息"""
    total_requests: int = Field(default=0, description="总请求数")
    successful_requests: int = Field(default=0, description="成功请求数")
    failed_requests: int = Field(default=0, description="失败请求数")
    fallback_count: int = Field(default=0, description="降级到直连的次数")

    # 性能指标
    avg_response_time: float = Field(default=0.0, description="平均响应时间（毫秒）")
    last_response_time: float = Field(default=0.0, description="最后响应时间（毫秒）")

    # 流量统计
    bytes_sent: int = Field(default=0, description="发送字节数")
    bytes_received: int = Field(default=0, description="接收字节数")

    # 时间戳
    started_at: Optional[datetime] = Field(None, description="开始时间")
    last_request_at: Optional[datetime] = Field(None, description="最后请求时间")

    # 错误信息
    last_error: Optional[str] = Field(None, description="最后错误信息")
    last_error_at: Optional[datetime] = Field(None, description="最后错误时间")

    def dict(self, **kwargs):
        """转换为字典时处理 datetime"""
        d = super().dict(**kwargs)
        # 转换 datetime 为 ISO 格式字符串
        for key in ['started_at', 'last_request_at', 'last_error_at']:
            if d.get(key):
                d[key] = d[key].isoformat() if isinstance(d[key], datetime) else d[key]
        return d

    def reset(self):
        """重置统计信息"""
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.fallback_count = 0
        self.avg_response_time = 0.0
        self.bytes_sent = 0
        self.bytes_received = 0
        self.started_at = datetime.now()
        self.last_request_at = None
        self.last_error = None
        self.last_error_at = None


class ProxyTestResult(BaseModel):
    """代理测试结果"""
    success: bool = Field(..., description="测试是否成功")
    response_time: float = Field(..., description="响应时间（毫秒）")
    status_code: Optional[int] = Field(None, description="HTTP 状态码")
    message: str = Field(..., description="测试消息")
    workers_version: Optional[str] = Field(None, description="Workers 版本")
    error: Optional[str] = Field(None, description="错误信息")
    timestamp: datetime = Field(default_factory=datetime.now, description="测试时间")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "response_time": 150.5,
                "status_code": 200,
                "message": "Workers proxy is healthy",
                "workers_version": "2.0.0",
                "timestamp": "2024-08-09T12:00:00"
            }
        }


class AkShareRequest(BaseModel):
    """AkShare API 请求"""
    function: str = Field(..., description="AkShare 函数名")
    params: Dict[str, Any] = Field(default_factory=dict, description="函数参数")
    use_cache: bool = Field(default=True, description="是否使用缓存")

    class Config:
        json_schema_extra = {
            "example": {
                "function": "stock_zh_a_spot_em",
                "params": {},
                "use_cache": True
            }
        }


class AkShareResponse(BaseModel):
    """AkShare API 响应"""
    success: bool = Field(..., description="请求是否成功")
    data: Optional[Any] = Field(None, description="返回数据")
    error: Optional[str] = Field(None, description="错误信息")

    # 元数据
    source: str = Field(..., description="数据来源：workers/direct/cache")
    response_time: float = Field(..., description="响应时间（毫秒）")
    cached: bool = Field(default=False, description="是否从缓存返回")
    timestamp: datetime = Field(default_factory=datetime.now, description="响应时间戳")
