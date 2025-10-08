"""全局数据源配置相关路由"""

from dataclasses import asdict
from typing import Any, Dict, Optional

from loguru import logger
from pydantic import BaseModel, ConfigDict, Field

from deepsearch.config.data_source_config import get_config_manager
from deepsearch.webui.api.common.response_format import APIResponse, ErrorCodes

from .datasource_manager import router


class GlobalConfigUpdate(BaseModel):
    """全局数据源配置更新模型"""

    model_config = ConfigDict(extra="allow")

    global_rate_limit: Optional[float] = Field(None, ge=0, description="全局速率限制(req/s)")
    global_timeout_multiplier: Optional[float] = Field(None, gt=0, description="全局超时倍率")
    global_cache_multiplier: Optional[float] = Field(None, gt=0, description="全局缓存倍率")
    batch_enabled: Optional[bool] = Field(None, description="是否启用批量处理")
    batch_timeout: Optional[float] = Field(None, ge=0, description="批量等待时长")
    max_batch_size: Optional[int] = Field(None, ge=1, description="批量最大条目数")
    retry_enabled: Optional[bool] = Field(None, description="是否启用重试")
    retry_base_delay: Optional[float] = Field(None, ge=0, description="重试基础延迟")
    retry_max_delay: Optional[float] = Field(None, ge=0, description="重试最大延迟")
    circuit_breaker_enabled: Optional[bool] = Field(None, description="是否启用熔断")
    circuit_breaker_threshold: Optional[int] = Field(None, ge=0, description="熔断阈值")
    circuit_breaker_timeout: Optional[float] = Field(None, ge=0, description="熔断超时时长")
    auto_adjust: Optional[bool] = Field(None, description="是否启用自动调节")


def _serialize_global_config(config_obj: Any) -> Dict[str, Any]:
    """将管理器中的配置转换为可序列化字典"""

    config_dict = asdict(config_obj)

    mode_value = getattr(config_obj, "mode", None)
    if mode_value is not None:
        config_dict["mode"] = mode_value.value if hasattr(mode_value, "value") else mode_value

    kept_fields = {
        "mode",
        "global_rate_limit",
        "global_timeout_multiplier",
        "global_cache_multiplier",
        "batch_enabled",
        "batch_timeout",
        "max_batch_size",
        "retry_enabled",
        "retry_base_delay",
        "retry_max_delay",
        "circuit_breaker_enabled",
        "circuit_breaker_threshold",
        "circuit_breaker_timeout",
        "auto_adjust",
        "last_updated",
        "version",
    }

    return {key: config_dict.get(key) for key in kept_fields if key in config_dict}


@router.get("/config")
async def get_global_config():
    """获取当前全局数据源配置"""

    try:
        manager = get_config_manager()
        payload = _serialize_global_config(manager.config)
        return APIResponse.success(data=payload, message="获取全局配置成功")
    except Exception as exc:
        logger.error(f"获取全局配置失败: {exc}")
        return APIResponse.error(
            code=ErrorCodes.INTERNAL_ERROR, message=f"获取全局配置失败: {exc}", status_code=500
        )


@router.put("/config")
async def update_global_config(config: GlobalConfigUpdate):
    """更新并持久化全局数据源配置"""

    try:
        manager = get_config_manager()
        updates = config.model_dump(exclude_unset=True)

        if updates:
            logger.info(f"更新全局数据源配置: {updates}")
            manager.update_config(updates)
            message = "全局配置更新成功"
        else:
            message = "未检测到需要更新的配置项"

        payload = _serialize_global_config(manager.config)
        return APIResponse.success(data=payload, message=message)
    except Exception as exc:
        logger.error(f"更新全局配置失败: {exc}")
        return APIResponse.error(
            code=ErrorCodes.INTERNAL_ERROR, message=f"更新全局配置失败: {exc}", status_code=500
        )
