"""
QMT集成配置模型
"""

from pydantic import BaseModel, Field


class QmtReceiverConfig(BaseModel):
    """QMT接收器配置"""
    tcp_port: int = Field(default=9999, description="TCP监听端口")
    websocket_port: int = Field(default=9998, description="WebSocket监听端口")
    host: str = Field(default="0.0.0.0", description="监听地址")


class QmtSecurityConfig(BaseModel):
    """QMT安全配置"""
    enable_auth: bool = Field(default=False, description="是否启用认证")
    token: str = Field(default="", description="认证令牌")


class QmtDataConfig(BaseModel):
    """QMT数据处理配置"""
    batch_size: int = Field(default=100, description="批处理大小")
    flush_interval: float = Field(default=0.1, description="批量刷新间隔（秒）")
    cache_ttl: int = Field(default=60, description="数据缓存时间（秒）")


class QmtMonitoringConfig(BaseModel):
    """QMT监控配置"""
    enabled: bool = Field(default=True, description="是否启用监控")
    report_interval: int = Field(default=30, description="状态报告间隔（秒）")


class QmtConfig(BaseModel):
    """QMT集成主配置"""
    enabled: bool = Field(default=False, description="是否启用QMT集成")
    receiver: QmtReceiverConfig = Field(default_factory=QmtReceiverConfig)
    security: QmtSecurityConfig = Field(default_factory=QmtSecurityConfig)
    data: QmtDataConfig = Field(default_factory=QmtDataConfig)
    monitoring: QmtMonitoringConfig = Field(default_factory=QmtMonitoringConfig)

    class Config:
        """Pydantic配置"""
        extra = "allow"  # 允许额外字段，便于扩展
