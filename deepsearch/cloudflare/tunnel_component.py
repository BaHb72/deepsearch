"""
Cloudflare Tunnel 组件

集成到 DeepSearch 组件系统
"""
from typing import Dict, Any, Optional

from deepsearch.core.async_component import AsyncComponent
from deepsearch.core.exceptions import ComponentLifecycleError
from deepsearch.core.interfaces import ComponentType
from .models import TunnelConfig, TunnelState
from .tunnel_manager import TunnelManager


class CloudflareTunnelComponent(AsyncComponent[TunnelManager]):
    """
    Cloudflare Tunnel 组件
    
    管理 Cloudflare Tunnel 的生命周期
    """

    def __init__(self, config_dir: Optional[str] = None):
        """
        初始化组件
        
        Args:
            config_dir: 配置目录
        """
        super().__init__(
            name="cloudflare_tunnel",
            component_type=ComponentType.EXTERNAL,
            display_name="Cloudflare Tunnel 管理"
        )
        self.config_dir = config_dir
        self._auto_start_tunnels = []  # 自动启动的 Tunnel 列表

    async def _initialize(self) -> None:
        """初始化组件"""
        try:
            # 创建 Tunnel 管理器
            self._instance = TunnelManager(self.config_dir)

            # 初始化管理器
            await self._instance.initialize()

            # 从配置中获取自动启动的 Tunnel
            from deepsearch.config import settings
            tunnel_config = getattr(settings, 'cloudflare', {})
            self._auto_start_tunnels = tunnel_config.get('auto_start_tunnels', [])

            self._logger.info("Cloudflare Tunnel 组件初始化成功")

        except Exception as e:
            self._logger.error(f"初始化失败: {e}")
            raise ComponentLifecycleError(self.name, "initialize", str(e))

    async def _start(self) -> None:
        """启动组件"""
        try:
            # 启动自动启动的 Tunnel
            for tunnel_name in self._auto_start_tunnels:
                try:
                    await self._instance.start_tunnel(tunnel_name)
                    self._logger.info(f"自动启动 Tunnel: {tunnel_name}")
                except Exception as e:
                    self._logger.error(f"启动 Tunnel {tunnel_name} 失败: {e}")

            self._logger.info("Cloudflare Tunnel 组件已启动")

        except Exception as e:
            self._logger.error(f"启动失败: {e}")
            raise ComponentLifecycleError(self.name, "start", str(e))

    async def _stop(self) -> None:
        """停止组件"""
        try:
            if self._instance:
                await self._instance.shutdown()

            self._logger.info("Cloudflare Tunnel 组件已停止")

        except Exception as e:
            self._logger.error(f"停止失败: {e}")
            raise ComponentLifecycleError(self.name, "stop", str(e))

    def _health_check(self) -> bool:
        """健康检查"""
        if not self._instance:
            return False

        # 检查是否有运行中的 Tunnel
        tunnels = self._instance.list_tunnels()
        running_count = sum(
            1 for t in tunnels
            if t.status.state == TunnelState.RUNNING
        )

        return running_count > 0 or len(tunnels) == 0  # 没有配置或有运行中的

    def _get_extra_status_info(self) -> Dict[str, Any]:
        """获取额外状态信息"""
        if not self._instance:
            return {}

        status = self._instance.get_status()
        tunnels = self._instance.list_tunnels()

        return {
            "tunnel_count": status["tunnel_count"],
            "active_tunnels": status["active_tunnels"],
            "tunnels": [
                {
                    "name": t.config.name,
                    "state": t.status.state,
                    "connected": t.status.connected,
                    "pid": t.status.pid,
                    "uptime": t.uptime_seconds
                }
                for t in tunnels
            ]
        }

    def _get_component_statistics(self) -> Dict[str, Any]:
        """获取组件统计信息"""
        if not self._instance:
            return {}

        tunnels = self._instance.list_tunnels()

        # 统计各状态的 Tunnel 数量
        state_counts = {}
        for tunnel in tunnels:
            state = tunnel.status.state
            state_counts[state] = state_counts.get(state, 0) + 1

        # 计算总流量
        total_bytes_sent = sum(t.status.bytes_sent for t in tunnels)
        total_bytes_received = sum(t.status.bytes_received for t in tunnels)
        total_requests = sum(t.status.requests_count for t in tunnels)

        return {
            "state_counts": state_counts,
            "total_bytes_sent": total_bytes_sent,
            "total_bytes_received": total_bytes_received,
            "total_requests": total_requests,
            "total_errors": sum(t.status.error_count for t in tunnels)
        }

    # 公开方法

    async def create_tunnel(self, config: TunnelConfig):
        """创建新 Tunnel"""
        if not self._instance:
            raise ComponentLifecycleError(self.name, "create_tunnel", "Component not initialized")

        return await self._instance.create_tunnel(config)

    async def start_tunnel(self, tunnel_name: str):
        """启动 Tunnel"""
        if not self._instance:
            raise ComponentLifecycleError(self.name, "start_tunnel", "Component not initialized")

        return await self._instance.start_tunnel(tunnel_name)

    async def stop_tunnel(self, tunnel_name: str):
        """停止 Tunnel"""
        if not self._instance:
            raise ComponentLifecycleError(self.name, "stop_tunnel", "Component not initialized")

        return await self._instance.stop_tunnel(tunnel_name)

    async def restart_tunnel(self, tunnel_name: str):
        """重启 Tunnel"""
        if not self._instance:
            raise ComponentLifecycleError(self.name, "restart_tunnel", "Component not initialized")

        return await self._instance.restart_tunnel(tunnel_name)

    def get_tunnel_info(self, tunnel_name: str):
        """获取 Tunnel 信息"""
        if not self._instance:
            return None

        return self._instance.get_tunnel_info(tunnel_name)

    def list_tunnels(self):
        """列出所有 Tunnel"""
        if not self._instance:
            return []

        return self._instance.list_tunnels()

    def get_manager(self) -> Optional[TunnelManager]:
        """获取 Tunnel 管理器实例"""
        return self._instance
