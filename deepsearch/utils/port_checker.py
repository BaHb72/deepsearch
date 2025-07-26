"""
端口检查工具

提供端口可用性检查和端口冲突检测功能。
"""
import socket
from typing import List, Dict, Optional


class PortChecker:
    """端口检查器"""

    @staticmethod
    def is_port_available(port: int, host: str = "localhost") -> bool:
        """
        检查端口是否可用
        
        Args:
            port: 要检查的端口
            host: 主机地址
            
        Returns:
            True 如果端口可用，False 如果端口被占用
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            result = sock.connect_ex((host, port))
            return result != 0
        finally:
            sock.close()

    @staticmethod
    def get_all_configured_ports() -> Dict[str, int]:
        """
        获取所有配置的端口
        
        Returns:
            服务名到端口的映射
        """
        # 延迟导入避免循环依赖
        from deepsearch.config import get_config
        config = get_config()
        ports = {}

        # WebUI 端口
        ports["webui_backend"] = config.webui.backend_port
        ports["webui_frontend"] = config.webui.frontend_port

        # ZeroMQ 端口
        for bus_name, bus_config in config.message_bus.buses.items():
            if bus_config.enabled and hasattr(bus_config.config, "pub_port"):
                ports[f"{bus_name}_pub"] = bus_config.config.pub_port
                ports[f"{bus_name}_sub"] = bus_config.config.sub_port

        # Redis 端口（如果配置了）
        if hasattr(config, "redis") and config.redis:
            ports["redis"] = config.redis.port

        # 监控端口（如果配置了）
        if config.monitoring and hasattr(config.monitoring, "metrics_port"):
            ports["metrics"] = config.monitoring.metrics_port

        return ports

    @staticmethod
    def check_port_conflicts() -> List[Dict[str, any]]:
        """
        检查端口冲突
        
        Returns:
            冲突列表，每个冲突包含服务名、端口和占用状态
        """
        conflicts = []
        ports = PortChecker.get_all_configured_ports()

        # 检查端口重复
        port_to_services: Dict[int, List[str]] = {}
        for service, port in ports.items():
            if port not in port_to_services:
                port_to_services[port] = []
            port_to_services[port].append(service)

        # 检查每个端口
        for port, services in port_to_services.items():
            # 检查端口是否被占用
            is_available = PortChecker.is_port_available(port)

            if len(services) > 1:
                # 多个服务使用同一端口
                conflicts.append({
                    "type": "duplicate",
                    "port": port,
                    "services": services,
                    "is_available": is_available
                })
            elif not is_available:
                # 端口被外部进程占用
                conflicts.append({
                    "type": "occupied",
                    "port": port,
                    "services": services,
                    "is_available": False
                })

        return conflicts

    @staticmethod
    def get_available_port(start_port: int = 8000, max_attempts: int = 100) -> Optional[int]:
        """
        查找可用端口
        
        Args:
            start_port: 起始端口
            max_attempts: 最大尝试次数
            
        Returns:
            可用端口号，如果没找到返回 None
        """
        for i in range(max_attempts):
            port = start_port + i
            if PortChecker.is_port_available(port):
                return port
        return None

    @staticmethod
    def validate_ports() -> bool:
        """
        验证所有配置的端口
        
        Returns:
            True 如果所有端口都有效，False 如果有冲突
        """
        conflicts = PortChecker.check_port_conflicts()

        if conflicts:
            print("端口配置存在问题：")
            for conflict in conflicts:
                if conflict["type"] == "duplicate":
                    print(f"  - 端口 {conflict['port']} 被多个服务使用: {', '.join(conflict['services'])}")
                else:
                    print(f"  - 端口 {conflict['port']} 已被占用 (服务: {', '.join(conflict['services'])})")
            return False

        return True


def check_and_report_ports():
    """检查并报告端口状态"""
    print("检查端口配置...")

    # 获取所有配置的端口
    ports = PortChecker.get_all_configured_ports()
    print(f"\n配置的端口:")
    for service, port in sorted(ports.items()):
        status = "可用" if PortChecker.is_port_available(port) else "占用"
        print(f"  {service:<20} : {port:>5} [{status}]")

    # 检查冲突
    conflicts = PortChecker.check_port_conflicts()
    if conflicts:
        print(f"\n发现 {len(conflicts)} 个端口冲突!")
        for conflict in conflicts:
            if conflict["type"] == "duplicate":
                print(f"  - 端口 {conflict['port']} 被多个服务使用: {', '.join(conflict['services'])}")
            else:
                print(f"  - 端口 {conflict['port']} 已被占用 (服务: {', '.join(conflict['services'])})")
    else:
        print("\n所有端口配置正常，没有冲突。")


if __name__ == "__main__":
    check_and_report_ports()
