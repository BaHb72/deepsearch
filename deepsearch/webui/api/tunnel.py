"""
Cloudflare Tunnel API 端点
"""
from typing import Optional

from fastapi import APIRouter, HTTPException

from deepsearch.cloudflare import (
    CloudflareTunnelComponent,
    TunnelConfig
)
from deepsearch.cloudflare.models import TunnelCommand, PublicHostname
from deepsearch.observability.logger import logger

# 创建路由
router = APIRouter(prefix="/api/tunnel", tags=["Cloudflare Tunnel"])

# 全局变量存储组件引用
tunnel_component: Optional[CloudflareTunnelComponent] = None


def get_tunnel_component() -> CloudflareTunnelComponent:
    """获取 Tunnel 组件"""
    global tunnel_component

    if tunnel_component is None:
        # 尝试从 MainEngine 获取
        try:
            from deepsearch.core.component_manager import ComponentManager
            manager = ComponentManager()
            tunnel_component = manager.get_component("cloudflare_tunnel")
        except:
            # 如果失败，创建独立实例
            tunnel_component = CloudflareTunnelComponent()

    if tunnel_component is None:
        raise HTTPException(status_code=503, detail="Tunnel component not available")

    return tunnel_component


@router.get("/status")
async def get_status():
    """获取 Tunnel 管理器状态"""
    try:
        component = get_tunnel_component()

        # 获取组件状态
        status = component.get_status()

        # 获取统计信息
        stats = component.get_statistics()

        return {
            "success": True,
            "data": {
                "component_status": status,
                "statistics": stats
            }
        }

    except Exception as e:
        logger.error(f"Failed to get tunnel status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list")
async def list_tunnels():
    """列出所有 Tunnel"""
    try:
        component = get_tunnel_component()
        tunnels = component.list_tunnels()

        # 转换为可序列化格式
        tunnel_list = []
        for tunnel in tunnels:
            tunnel_data = {
                "name": tunnel.config.name,
                "config": tunnel.config.dict(),
                "status": tunnel.status.dict(),
                "uptime_seconds": tunnel.uptime_seconds,
                "api_servers": tunnel.api_servers
            }
            tunnel_list.append(tunnel_data)

        return {
            "success": True,
            "data": tunnel_list
        }

    except Exception as e:
        logger.error(f"Failed to list tunnels: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{tunnel_name}")
async def get_tunnel_info(tunnel_name: str):
    """获取指定 Tunnel 信息"""
    try:
        component = get_tunnel_component()
        info = component.get_tunnel_info(tunnel_name)

        if not info:
            raise HTTPException(status_code=404, detail=f"Tunnel {tunnel_name} not found")

        return {
            "success": True,
            "data": {
                "name": info.config.name,
                "config": info.config.dict(),
                "status": info.status.dict(),
                "uptime_seconds": info.uptime_seconds,
                "api_servers": info.api_servers
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get tunnel info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/create")
async def create_tunnel(config: TunnelConfig):
    """创建新的 Tunnel"""
    try:
        component = get_tunnel_component()
        info = await component.create_tunnel(config)

        return {
            "success": True,
            "message": f"Tunnel {config.name} created successfully",
            "data": {
                "name": info.config.name,
                "config": info.config.dict(),
                "status": info.status.dict()
            }
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create tunnel: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{tunnel_name}/config")
async def update_tunnel_config(tunnel_name: str, config: TunnelConfig):
    """更新 Tunnel 配置"""
    try:
        component = get_tunnel_component()
        manager = component.get_manager()

        if not manager:
            raise HTTPException(status_code=503, detail="Tunnel manager not available")

        # 检查 Tunnel 是否存在
        info = component.get_tunnel_info(tunnel_name)
        if not info:
            raise HTTPException(status_code=404, detail=f"Tunnel {tunnel_name} not found")

        # 如果正在运行，先停止
        was_running = info.status.state == "running"
        if was_running:
            await component.stop_tunnel(tunnel_name)

        # 更新配置
        info.config = config
        await manager.save_config(config)

        # 如果之前在运行，重新启动
        if was_running:
            await component.start_tunnel(tunnel_name)

        return {
            "success": True,
            "message": f"Tunnel {tunnel_name} config updated",
            "data": config.dict()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update tunnel config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{tunnel_name}/start")
async def start_tunnel(tunnel_name: str):
    """启动 Tunnel"""
    try:
        component = get_tunnel_component()
        success = await component.start_tunnel(tunnel_name)

        if success:
            return {
                "success": True,
                "message": f"Tunnel {tunnel_name} started successfully"
            }
        else:
            raise HTTPException(status_code=500, detail=f"Failed to start tunnel {tunnel_name}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start tunnel: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{tunnel_name}/stop")
async def stop_tunnel(tunnel_name: str):
    """停止 Tunnel"""
    try:
        component = get_tunnel_component()
        success = await component.stop_tunnel(tunnel_name)

        if success:
            return {
                "success": True,
                "message": f"Tunnel {tunnel_name} stopped successfully"
            }
        else:
            raise HTTPException(status_code=500, detail=f"Failed to stop tunnel {tunnel_name}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to stop tunnel: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{tunnel_name}/restart")
async def restart_tunnel(tunnel_name: str):
    """重启 Tunnel"""
    try:
        component = get_tunnel_component()
        success = await component.restart_tunnel(tunnel_name)

        if success:
            return {
                "success": True,
                "message": f"Tunnel {tunnel_name} restarted successfully"
            }
        else:
            raise HTTPException(status_code=500, detail=f"Failed to restart tunnel {tunnel_name}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to restart tunnel: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/control")
async def control_tunnel(command: TunnelCommand):
    """控制 Tunnel（统一接口）"""
    try:
        component = get_tunnel_component()

        if command.action == "start":
            success = await component.start_tunnel(command.tunnel_name)
            action_msg = "started"
        elif command.action == "stop":
            success = await component.stop_tunnel(command.tunnel_name)
            action_msg = "stopped"
        elif command.action == "restart":
            success = await component.restart_tunnel(command.tunnel_name)
            action_msg = "restarted"
        else:
            raise HTTPException(status_code=400, detail=f"Unknown action: {command.action}")

        if success:
            return {
                "success": True,
                "message": f"Tunnel {command.tunnel_name} {action_msg} successfully"
            }
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to {command.action} tunnel {command.tunnel_name}"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to control tunnel: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{tunnel_name}")
async def delete_tunnel(tunnel_name: str):
    """删除 Tunnel"""
    try:
        component = get_tunnel_component()
        manager = component.get_manager()

        if not manager:
            raise HTTPException(status_code=503, detail="Tunnel manager not available")

        # 检查 Tunnel 是否存在
        info = component.get_tunnel_info(tunnel_name)
        if not info:
            raise HTTPException(status_code=404, detail=f"Tunnel {tunnel_name} not found")

        # 如果正在运行，先停止
        if info.status.state == "running":
            await component.stop_tunnel(tunnel_name)

        # 删除配置文件
        config_file = manager.config_dir / f"{tunnel_name}.yaml"
        if config_file.exists():
            config_file.unlink()

        # 从内存中删除
        del manager.tunnels[tunnel_name]

        return {
            "success": True,
            "message": f"Tunnel {tunnel_name} deleted successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete tunnel: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{tunnel_name}/hostname")
async def add_hostname(tunnel_name: str, hostname: PublicHostname):
    """添加 Public Hostname"""
    try:
        component = get_tunnel_component()
        info = component.get_tunnel_info(tunnel_name)

        if not info:
            raise HTTPException(status_code=404, detail=f"Tunnel {tunnel_name} not found")

        # 添加 hostname
        info.config.hostnames.append(hostname)

        # 保存配置
        manager = component.get_manager()
        await manager.save_config(info.config)

        # 如果正在运行，需要重启
        if info.status.state == "running":
            await component.restart_tunnel(tunnel_name)

        return {
            "success": True,
            "message": f"Hostname {hostname.hostname} added to tunnel {tunnel_name}",
            "data": hostname.dict()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add hostname: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{tunnel_name}/hostname/{hostname}")
async def remove_hostname(tunnel_name: str, hostname: str):
    """删除 Public Hostname"""
    try:
        component = get_tunnel_component()
        info = component.get_tunnel_info(tunnel_name)

        if not info:
            raise HTTPException(status_code=404, detail=f"Tunnel {tunnel_name} not found")

        # 查找并删除 hostname
        original_count = len(info.config.hostnames)
        info.config.hostnames = [
            h for h in info.config.hostnames
            if h.hostname != hostname
        ]

        if len(info.config.hostnames) == original_count:
            raise HTTPException(status_code=404, detail=f"Hostname {hostname} not found")

        # 保存配置
        manager = component.get_manager()
        await manager.save_config(info.config)

        # 如果正在运行，需要重启
        if info.status.state == "running":
            await component.restart_tunnel(tunnel_name)

        return {
            "success": True,
            "message": f"Hostname {hostname} removed from tunnel {tunnel_name}"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to remove hostname: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# 初始化函数，在应用启动时调用
def init_tunnel_component():
    """初始化 Tunnel 组件"""
    global tunnel_component
    try:
        tunnel_component = CloudflareTunnelComponent()
        logger.info("Tunnel API component initialized")
    except Exception as e:
        logger.error(f"Failed to initialize tunnel component: {e}")
