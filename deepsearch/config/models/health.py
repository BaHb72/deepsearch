"""
健康检查配置模型
"""

from typing import Any, Dict

from pydantic import BaseModel, Field


class HealthCheckConfig(BaseModel):
    """健康检查配置"""

    # 基础配置
    enabled: bool = Field(default=True, description="是否启用健康检查")

    interval: float = Field(default=30.0, gt=0, description="健康检查间隔（秒）")

    timeout: float = Field(default=5.0, gt=0, description="单个健康检查超时时间（秒）")

    # 组件配置
    components: Dict[str, bool] = Field(
        default_factory=lambda: {
            "database": True,
            "cache": True,
            "event_engine": True,
            "message_bus": True,
            "monitor": True,
            "gateway": True,
        },
        description="各组件的健康检查开关",
    )

    # 高级配置
    history_size: int = Field(default=100, ge=0, description="保留的历史记录数量")

    # 告警配置
    alert_enabled: bool = Field(default=False, description="是否启用健康状态告警")

    alert_threshold: int = Field(default=3, ge=1, description="连续失败多少次后触发告警")

    # 自定义健康检查器配置
    custom_checkers: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict, description="自定义健康检查器配置"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "enabled": True,
                    "interval": 30.0,
                    "timeout": 5.0,
                    "components": {
                        "database": True,
                        "cache": True,
                        "event_engine": True,
                        "message_bus": True,
                        "monitor": True,
                        "gateway": True,
                    },
                    "history_size": 100,
                    "alert_enabled": False,
                    "alert_threshold": 3,
                }
            ]
        }
    }
