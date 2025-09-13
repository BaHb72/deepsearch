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

        # 数据库缓存端口（Redis）
        if hasattr(config, "database") and hasattr(config.database, "cache"):
            if config.database.cache.enabled:
                ports["cache_redis"] = config.database.cache.port

        # QMT 端口（如果配置了）
        if hasattr(config, "qmt") and config.qmt:
            if hasattr(config.qmt, "enabled") and config.qmt.enabled:
                if hasattr(config.qmt, "receiver"):
                    ports["qmt_tcp"] = config.qmt.receiver.tcp_port
                    ports["qmt_websocket"] = config.qmt.receiver.websocket_port

        # MiniQMT 端口（如果配置了）
        if hasattr(config, "miniqmt") and config.miniqmt:
            # Check if miniqmt is a dict or has attributes
            if isinstance(config.miniqmt, dict):
                if config.miniqmt.get("enabled", False):
                    connection = config.miniqmt.get("connection", {})
                    if "port" in connection:
                        ports["miniqmt"] = connection["port"]
            elif hasattr(config.miniqmt, "enabled") and config.miniqmt.enabled:
                if hasattr(config.miniqmt, "connection"):
                    ports["miniqmt"] = config.miniqmt.connection.port

        # 监控端口（如果配置了）
        if config.monitoring and hasattr(config.monitoring, "metrics_port"):
            ports["metrics"] = config.monitoring.metrics_port

        return ports

    @staticmethod
    def get_service_ports() -> Dict[str, int]:
        """
        获取依赖服务端口（应该被占用的端口）
        
        Returns:
            服务名到端口的映射
        """
        from deepsearch.config import get_config
        config = get_config()
        service_ports = {}

        # Redis 缓存端口
        if hasattr(config, "database") and hasattr(config.database, "cache"):
            if config.database.cache.enabled:
                service_ports["cache_redis"] = config.database.cache.port

        return service_ports

    @staticmethod
    def get_listen_ports() -> Dict[str, int]:
        """
        获取 DeepSearch 要监听的端口（不应该被占用的端口）
        
        Returns:
            服务名到端口的映射
        """
        from deepsearch.config import get_config
        config = get_config()
        listen_ports = {}

        # WebUI 端口
        listen_ports["webui_backend"] = config.webui.backend_port
        listen_ports["webui_frontend"] = config.webui.frontend_port

        # QMT 端口（如果配置了）
        if hasattr(config, "qmt") and config.qmt:
            if hasattr(config.qmt, "enabled") and config.qmt.enabled:
                if hasattr(config.qmt, "receiver"):
                    listen_ports["qmt_tcp"] = config.qmt.receiver.tcp_port
                    listen_ports["qmt_websocket"] = config.qmt.receiver.websocket_port

        # MiniQMT 端口（如果配置了）
        if hasattr(config, "miniqmt") and config.miniqmt:
            if isinstance(config.miniqmt, dict):
                if config.miniqmt.get("enabled", False):
                    connection = config.miniqmt.get("connection", {})
                    if "port" in connection:
                        listen_ports["miniqmt"] = connection["port"]
            elif hasattr(config.miniqmt, "enabled") and config.miniqmt.enabled:
                if hasattr(config.miniqmt, "connection"):
                    listen_ports["miniqmt"] = config.miniqmt.connection.port

        return listen_ports

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
        has_error = False

        # 检查依赖服务端口（应该被占用）
        service_ports = PortChecker.get_service_ports()
        service_issues = []
        for service, port in service_ports.items():
            if PortChecker.is_port_available(port):
                # 端口未被占用，服务未运行
                service_issues.append({
                    "service": service,
                    "port": port,
                    "issue": "服务未运行"
                })

        # 检查监听端口（不应该被占用）
        listen_ports = PortChecker.get_listen_ports()
        listen_conflicts = []
        for service, port in listen_ports.items():
            if not PortChecker.is_port_available(port):
                # 端口被占用，有冲突
                listen_conflicts.append({
                    "service": service,
                    "port": port
                })
                has_error = True

        # 显示服务状态问题（警告）
        if service_issues:
            print("\n[WARNING] 依赖服务未运行：")
            print("=" * 60)
            for issue in service_issues:
                print(f"\n{issue['service']} (端口 {issue['port']}) - {issue['issue']}")
                if "redis" in issue['service'].lower():
                    print("  提示: 请启动 Redis 服务，或禁用缓存配置")
            print("=" * 60)

        # 显示端口冲突（错误）
        if listen_conflicts:
            print("\n[ERROR] 端口配置存在冲突：")
            print("=" * 60)
            for conflict in listen_conflicts:
                print(f"\n端口 {conflict['port']} 已被占用:")
                print(f"  配置服务: {conflict['service']}")
                # 尝试获取占用进程信息
                try:
                    import psutil
                    for conn in psutil.net_connections():
                        if hasattr(conn, 'laddr') and conn.laddr.port == conflict['port'] and conn.status == 'LISTEN':
                            try:
                                proc = psutil.Process(conn.pid)
                                print(f"  占用进程: {proc.name()} (PID: {conn.pid})")
                                print(f"  进程路径: {proc.exe()}")
                            except:
                                print(f"  占用进程 PID: {conn.pid}")
                            break
                except:
                    pass

            print("\n" + "=" * 60)
            print("解决方案:")
            print("  1. 停止占用端口的进程")
            print("  2. 运行 'python -m deepsearch cleanup' 清理端口")
            print("  3. 或修改配置文件更改端口")
            print("=" * 60)

        return not has_error


def check_and_report_ports():
    """检查并报告端口状态"""
    print("检查端口配置...")

    # 分别获取两类端口
    service_ports = PortChecker.get_service_ports()
    listen_ports = PortChecker.get_listen_ports()

    print(f"\n依赖服务端口（应该被占用）:")
    for service, port in sorted(service_ports.items()):
        is_available = PortChecker.is_port_available(port)
        if is_available:
            status = "未运行"
        else:
            status = "运行中"
        print(f"  {service:<20} : {port:>5} [{status}]")

    print(f"\nDeepSearch 监听端口（不应该被占用）:")
    for service, port in sorted(listen_ports.items()):
        is_available = PortChecker.is_port_available(port)
        if is_available:
            status = "可用"
        else:
            status = "冲突"
        print(f"  {service:<20} : {port:>5} [{status}]")

    # 使用新的验证逻辑
    is_valid = PortChecker.validate_ports()
    if is_valid:
        print("\n[OK] 所有端口配置正常。")
    else:
        print("\n[ERROR] 存在端口冲突，请解决后再启动。")


if __name__ == "__main__":
    check_and_report_ports()
