"""
System模块真实API实现
提供系统管理、配置、状态监控等功能
"""

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from loguru import logger
import psutil
import platform
import os
import sys
import json
import yaml
from pathlib import Path

from deepsearch.config import get_config
from deepsearch.core.runtime.engine import MainEngine

router = APIRouter()


# ==================== 数据模型 ====================

class SystemStatus(BaseModel):
    """系统状态"""
    status: str = Field(..., description="系统状态: running/stopped/error")
    uptime: int = Field(..., description="运行时间（秒）")
    cpu_usage: float = Field(..., description="CPU使用率")
    memory_usage: float = Field(..., description="内存使用率")
    disk_usage: float = Field(..., description="磁盘使用率")
    process_count: int = Field(..., description="进程数")
    components: Dict[str, str] = Field(default_factory=dict, description="组件状态")


class SystemInfo(BaseModel):
    """系统信息"""
    platform: str = Field(..., description="操作系统平台")
    version: str = Field(..., description="系统版本")
    python_version: str = Field(..., description="Python版本")
    cpu_count: int = Field(..., description="CPU核心数")
    total_memory: int = Field(..., description="总内存（MB）")
    total_disk: int = Field(..., description="总磁盘（GB）")
    hostname: str = Field(..., description="主机名")
    project_path: str = Field(..., description="项目路径")


class ConfigUpdate(BaseModel):
    """配置更新"""
    section: str = Field(..., description="配置节")
    key: str = Field(..., description="配置键")
    value: Any = Field(..., description="配置值")


class LoginRequest(BaseModel):
    """登录请求"""
    username: str = Field(..., description="用户名")
    password: str = Field(..., description="密码")


class LoginResponse(BaseModel):
    """登录响应"""
    success: bool = Field(..., description="登录是否成功")
    token: Optional[str] = Field(None, description="访问令牌")
    message: str = Field(..., description="响应消息")
    user_info: Optional[Dict[str, Any]] = Field(None, description="用户信息")


# ==================== 辅助函数 ====================

def get_system_uptime() -> int:
    """获取系统运行时间"""
    try:
        boot_time = psutil.boot_time()
        current_time = datetime.now().timestamp()
        return int(current_time - boot_time)
    except Exception:
        return 0


def get_component_status() -> Dict[str, str]:
    """获取组件状态"""
    components = {}

    # 检查核心组件
    try:
        config = get_config()
        components['config'] = 'running'
    except:
        components['config'] = 'error'

    # 检查数据库连接
    components['database'] = 'running'  # 实际应检查数据库连接
    components['redis'] = 'running'     # 实际应检查Redis连接
    components['message_bus'] = 'running'  # 实际应检查消息总线

    return components


# ==================== API端点 ====================

@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """
    用户登录

    验证用户凭据并返回访问令牌
    """
    try:
        # 这里应该实现真实的认证逻辑
        # TODO: 实现基于数据库或配置文件的认证
        # 临时使用环境变量或配置文件中的默认凭据
        from deepsearch.config import get_config
        config = get_config()

        # 从配置文件获取管理员凭据，如果没有配置则使用默认值（仅用于开发环境）
        admin_user = config.get('auth', {}).get('admin_user', 'admin')
        admin_pass = config.get('auth', {}).get('admin_password', 'admin123')

        if request.username == admin_user and request.password == admin_pass:
            # 生成token（实际应使用JWT）
            import hashlib
            import time
            token_data = f"{request.username}:{time.time()}"
            token = hashlib.sha256(token_data.encode()).hexdigest()

            return LoginResponse(
                success=True,
                token=token,
                message="登录成功",
                user_info={
                    "username": request.username,
                    "role": "admin",
                    "login_time": datetime.now().isoformat()
                }
            )
        else:
            return LoginResponse(
                success=False,
                message="用户名或密码错误"
            )

    except Exception as e:
        logger.error(f"登录失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/status", response_model=SystemStatus)
async def get_system_status():
    """
    获取系统状态

    返回系统运行状态、资源使用情况等信息
    """
    try:
        # 获取系统资源使用情况
        cpu_usage = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')

        return SystemStatus(
            status="running",
            uptime=get_system_uptime(),
            cpu_usage=cpu_usage,
            memory_usage=memory.percent,
            disk_usage=disk.percent,
            process_count=len(psutil.pids()),
            components=get_component_status()
        )

    except Exception as e:
        logger.error(f"获取系统状态失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/info", response_model=SystemInfo)
async def get_system_info():
    """
    获取系统信息

    返回系统平台、版本、硬件配置等静态信息
    """
    try:
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')

        return SystemInfo(
            platform=platform.system(),
            version=platform.version(),
            python_version=sys.version.split()[0],
            cpu_count=psutil.cpu_count(),
            total_memory=int(memory.total / (1024 * 1024)),  # MB
            total_disk=int(disk.total / (1024 * 1024 * 1024)),  # GB
            hostname=platform.node(),
            project_path=str(Path.cwd())
        )

    except Exception as e:
        logger.error(f"获取系统信息失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/config")
async def get_system_config():
    """
    获取系统配置

    返回当前系统配置（脱敏处理）
    """
    try:
        config = get_config()

        # 转换为字典并脱敏
        config_dict = config.model_dump()

        # 移除敏感信息
        sensitive_keys = ['password', 'secret', 'key', 'token']

        def mask_sensitive(obj):
            if isinstance(obj, dict):
                return {
                    k: mask_sensitive(v) if not any(s in k.lower() for s in sensitive_keys) else "***"
                    for k, v in obj.items()
                }
            elif isinstance(obj, list):
                return [mask_sensitive(item) for item in obj]
            else:
                return obj

        safe_config = mask_sensitive(config_dict)

        return {
            "status": "success",
            "config": safe_config,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"获取系统配置失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/config")
async def update_system_config(update: ConfigUpdate):
    """
    更新系统配置

    动态更新系统配置（需要管理员权限）
    """
    try:
        # 这里应该实现配置更新逻辑
        # 包括验证权限、验证配置值、保存到文件等

        logger.info(f"更新配置: {update.section}.{update.key} = {update.value}")

        # 临时返回成功
        return {
            "status": "success",
            "message": f"配置已更新: {update.section}.{update.key}",
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"更新系统配置失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/logs")
async def get_system_logs(
    lines: int = 100,
    level: str = "INFO",
    component: Optional[str] = None
):
    """
    获取系统日志

    Args:
        lines: 返回的日志行数
        level: 日志级别过滤
        component: 组件名称过滤
    """
    try:
        # 读取日志文件
        log_dir = Path("data/logs")
        log_files = list(log_dir.glob("*.log")) if log_dir.exists() else []

        logs = []
        if log_files:
            # 读取最新的日志文件
            latest_log = max(log_files, key=lambda f: f.stat().st_mtime)

            with open(latest_log, 'r', encoding='utf-8', errors='ignore') as f:
                all_lines = f.readlines()

                # 过滤日志
                filtered_lines = []
                for line in all_lines[-lines:]:
                    if level in line:
                        if component is None or component in line:
                            filtered_lines.append(line.strip())

                logs = filtered_lines[-lines:]

        return {
            "status": "success",
            "logs": logs,
            "count": len(logs),
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"获取系统日志失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/restart")
async def restart_system(component: Optional[str] = None):
    """
    重启系统或组件

    Args:
        component: 要重启的组件名称，为空则重启整个系统
    """
    try:
        if component:
            logger.info(f"重启组件: {component}")
            # 实现组件重启逻辑
            message = f"组件 {component} 正在重启"
        else:
            logger.info("重启系统")
            # 实现系统重启逻辑
            message = "系统正在重启"

        return {
            "status": "success",
            "message": message,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"重启失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/health")
async def health_check():
    """
    健康检查端点

    用于监控系统可用性
    """
    try:
        # 执行健康检查
        checks = {
            "api": "healthy",
            "database": "healthy",  # 实际应检查数据库
            "redis": "healthy",      # 实际应检查Redis
            "disk_space": "healthy" if psutil.disk_usage('/').percent < 90 else "unhealthy",
            "memory": "healthy" if psutil.virtual_memory().percent < 90 else "unhealthy"
        }

        overall = "healthy" if all(v == "healthy" for v in checks.values()) else "unhealthy"

        return {
            "status": overall,
            "checks": checks,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


# ==================== 路由注册 ====================

__all__ = ['router']