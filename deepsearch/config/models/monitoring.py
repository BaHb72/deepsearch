"""
监控配置模型。
"""
from pydantic import BaseModel, Field


class MonitoringConfig(BaseModel):
    """监控配置。"""
    enable_metrics: bool = Field(False, description="是否启用监控指标")
    metrics_port: int = Field(9090, description="指标服务端口（为未来 Web UI 预留）")

    # 监控数据存储
    data_dir: str = Field("data/monitoring", description="监控数据存储目录")
    max_records: int = Field(1000, description="内存中保留的最大记录数")

    # 更新间隔
    update_interval: int = Field(5, description="监控数据更新间隔（秒）")
    persist_interval: int = Field(300, description="数据持久化间隔（秒）")

    # 日志监控（简化版）
    log_interval: int = Field(300, description="日志记录间隔（秒）")
    enable_json_log: bool = Field(True, description="是否启用 JSON 格式日志")
