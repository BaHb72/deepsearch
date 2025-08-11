"""
Cloudflare Tunnel 数据模型
"""
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field


class TunnelState(str, Enum):
    """Tunnel 状态枚举"""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"
    UNKNOWN = "unknown"


class ServiceType(str, Enum):
    """服务类型"""
    HTTP = "http"
    HTTPS = "https"
    TCP = "tcp"
    SSH = "ssh"
    RDP = "rdp"


class PublicHostname(BaseModel):
    """Public Hostname 配置"""
    hostname: str = Field(..., description="公开访问的域名")
    service_type: ServiceType = Field(default=ServiceType.HTTP, description="服务类型")
    service_url: str = Field(..., description="后端服务地址，如 localhost:8000")
    path: Optional[str] = Field(None, description="路径匹配规则")

    # 高级选项
    no_tls_verify: bool = Field(default=False, description="是否跳过 TLS 验证")
    origin_server_name: Optional[str] = Field(None, description="源服务器名称")
    ca_pool: Optional[str] = Field(None, description="CA 证书池")

    # 负载均衡
    lb_pool: Optional[str] = Field(None, description="负载均衡池")

    class Config:
        schema_extra = {
            "example": {
                "hostname": "api.example.com",
                "service_type": "http",
                "service_url": "localhost:8000",
                "path": "/api/*"
            }
        }


class TunnelConfig(BaseModel):
    """Tunnel 配置模型"""
    # 基本信息
    name: str = Field(..., description="Tunnel 名称")
    tunnel_id: Optional[str] = Field(None, description="Tunnel ID")
    token: Optional[str] = Field(None, description="Tunnel Token")

    # 连接配置
    credentials_file: Optional[str] = Field(None, description="认证文件路径")
    config_file: Optional[str] = Field(None, description="配置文件路径")

    # Public Hostnames
    hostnames: List[PublicHostname] = Field(default_factory=list, description="公开主机名配置")

    # 高级配置
    protocol: str = Field(default="quic", description="传输协议: quic, http2")
    loglevel: str = Field(default="info", description="日志级别")
    logfile: Optional[str] = Field(None, description="日志文件路径")

    # 自动重启
    auto_restart: bool = Field(default=True, description="异常退出时自动重启")
    restart_delay: int = Field(default=5, description="重启延迟（秒）")

    # Metrics
    metrics_enabled: bool = Field(default=True, description="启用指标收集")
    metrics_port: int = Field(default=2000, description="Metrics 端口")

    class Config:
        schema_extra = {
            "example": {
                "name": "deepsearch-tunnel",
                "token": "eyJhIjo...",
                "hostnames": [
                    {
                        "hostname": "api.example.com",
                        "service_type": "http",
                        "service_url": "localhost:8000"
                    }
                ],
                "protocol": "quic",
                "loglevel": "info"
            }
        }


class TunnelStatus(BaseModel):
    """Tunnel 状态信息"""
    state: TunnelState = Field(default=TunnelState.UNKNOWN, description="当前状态")
    connected: bool = Field(default=False, description="是否已连接")
    connection_time: Optional[datetime] = Field(None, description="连接时间")

    # 连接信息
    connector_id: Optional[str] = Field(None, description="连接器 ID")
    connection_count: int = Field(default=0, description="活动连接数")

    # 流量统计
    bytes_sent: int = Field(default=0, description="发送字节数")
    bytes_received: int = Field(default=0, description="接收字节数")
    requests_count: int = Field(default=0, description="请求总数")

    # 错误信息
    last_error: Optional[str] = Field(None, description="最后错误信息")
    error_count: int = Field(default=0, description="错误次数")
    last_error_time: Optional[datetime] = Field(None, description="最后错误时间")

    # 进程信息
    pid: Optional[int] = Field(None, description="进程 ID")
    cpu_percent: float = Field(default=0.0, description="CPU 使用率")
    memory_mb: float = Field(default=0.0, description="内存使用 (MB)")

    # 版本信息
    version: Optional[str] = Field(None, description="cloudflared 版本")

    def dict(self, **kwargs):
        """转换为字典时处理 datetime"""
        d = super().dict(**kwargs)
        # 转换 datetime 为 ISO 格式字符串
        for key in ['connection_time', 'last_error_time']:
            if d.get(key):
                d[key] = d[key].isoformat() if isinstance(d[key], datetime) else d[key]
        return d


class TunnelInfo(BaseModel):
    """Tunnel 完整信息（配置 + 状态）"""
    config: TunnelConfig
    status: TunnelStatus

    # 运行时信息
    uptime_seconds: Optional[int] = Field(None, description="运行时间（秒）")

    # API 服务器信息（如果有）
    api_servers: List[Dict[str, Any]] = Field(default_factory=list, description="关联的 API 服务器")

    class Config:
        schema_extra = {
            "example": {
                "config": {
                    "name": "deepsearch-tunnel",
                    "hostnames": []
                },
                "status": {
                    "state": "running",
                    "connected": True
                },
                "uptime_seconds": 3600,
                "api_servers": [
                    {
                        "name": "akshare-api",
                        "url": "localhost:8000",
                        "status": "healthy"
                    }
                ]
            }
        }


class TunnelMetrics(BaseModel):
    """Tunnel 指标数据"""
    timestamp: datetime = Field(default_factory=datetime.now, description="时间戳")

    # 连接指标
    active_connections: int = Field(default=0, description="活动连接数")
    total_connections: int = Field(default=0, description="总连接数")

    # 流量指标
    bytes_in_rate: float = Field(default=0.0, description="入站速率 (bytes/s)")
    bytes_out_rate: float = Field(default=0.0, description="出站速率 (bytes/s)")

    # 请求指标
    requests_per_second: float = Field(default=0.0, description="请求速率 (req/s)")
    avg_response_time_ms: float = Field(default=0.0, description="平均响应时间 (ms)")

    # 错误指标
    error_rate: float = Field(default=0.0, description="错误率 (%)")

    # 系统指标
    cpu_usage: float = Field(default=0.0, description="CPU 使用率 (%)")
    memory_usage: float = Field(default=0.0, description="内存使用 (MB)")


class TunnelCommand(BaseModel):
    """Tunnel 控制命令"""
    action: str = Field(..., description="操作: start, stop, restart, reload")
    tunnel_name: str = Field(..., description="Tunnel 名称")
    params: Optional[Dict[str, Any]] = Field(None, description="额外参数")

    class Config:
        schema_extra = {
            "example": {
                "action": "restart",
                "tunnel_name": "deepsearch-tunnel",
                "params": {}
            }
        }
