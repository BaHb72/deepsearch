"""
配置管理 API 路由。
"""
from typing import Dict, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from loguru import logger

from deepsearch.config import settings

router = APIRouter()


class ConfigUpdate(BaseModel):
    """配置更新请求模型。"""
    section: str
    key: str
    value: Any


@router.get("")
async def get_config() -> Dict[str, Any]:
    """
    获取当前系统配置。
    
    Returns:
        系统配置字典
    """
    try:
        # 将配置转换为字典格式
        config_dict = settings.model_dump()

        # 移除敏感信息
        if "security" in config_dict:
            config_dict["security"] = {
                "api_key": "***" if config_dict["security"].get("api_key") else None,
                "secret_key": "***" if config_dict["security"].get("secret_key") else None
            }

        return config_dict

    except Exception as e:
        logger.error(f"获取配置失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/schema")
async def get_config_schema() -> Dict[str, Any]:
    """
    获取配置模式定义。
    
    Returns:
        配置的 JSON Schema
    """
    try:
        return settings.model_json_schema()
    except Exception as e:
        logger.error(f"获取配置模式失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("")
async def update_config(update: ConfigUpdate) -> Dict[str, Any]:
    """
    更新配置项。
    
    注意：此功能在生产环境中应该谨慎使用。
    
    Args:
        update: 配置更新信息
        
    Returns:
        更新后的配置
    """
    # 在实际实现中，这里应该：
    # 1. 验证权限
    # 2. 验证配置值的合法性
    # 3. 更新配置文件
    # 4. 可能需要重启某些服务

    return {
        "status": "not_implemented",
        "message": "配置更新功能尚未实现，请直接修改配置文件"
    }


@router.get("/validate")
async def validate_config() -> Dict[str, Any]:
    """
    验证当前配置的有效性。
    
    Returns:
        验证结果
    """
    issues = []

    try:
        # 检查必要的目录是否存在
        if not settings.log.active:
            issues.append({
                "level": "warning",
                "section": "log",
                "message": "日志功能已禁用"
            })

        # 检查消息总线配置
        if not settings.message_bus.enabled_buses:
            issues.append({
                "level": "error",
                "section": "message_bus",
                "message": "没有启用的消息总线"
            })

        # 检查监控配置
        if not settings.monitoring.enable_metrics:
            issues.append({
                "level": "info",
                "section": "monitoring",
                "message": "监控指标未启用"
            })

        return {
            "valid": len([i for i in issues if i["level"] == "error"]) == 0,
            "issues": issues
        }

    except Exception as e:
        logger.error(f"验证配置失败：{e}")
        return {
            "valid": False,
            "error": str(e),
            "issues": []
        }
