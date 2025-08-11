"""
Cloudflare Tunnel 管理器

管理 cloudflared 进程和 Tunnel 配置
"""
import asyncio
import os
import platform
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

import psutil
import yaml

from deepsearch.observability.logger import logger
from .models import (
    TunnelConfig,
    TunnelStatus,
    TunnelState,
    TunnelInfo
)


class TunnelManager:
    """
    Cloudflare Tunnel 管理器
    
    负责管理 cloudflared 进程、配置和状态监控
    """

    def __init__(self, config_dir: Optional[str] = None):
        """
        初始化 Tunnel 管理器
        
        Args:
            config_dir: 配置文件目录
        """
        self.config_dir = Path(config_dir or "./config/tunnel")
        self.config_dir.mkdir(parents=True, exist_ok=True)

        self.tunnels: Dict[str, TunnelInfo] = {}
        self.processes: Dict[str, subprocess.Popen] = {}
        self.logger = logger.bind(component="TunnelManager")

        # cloudflared 可执行文件路径
        self.cloudflared_path = self._find_cloudflared()

        # 监控任务
        self._monitor_task: Optional[asyncio.Task] = None
        self._running = False

    def _find_cloudflared(self) -> str:
        """查找 cloudflared 可执行文件"""
        # Windows
        if platform.system() == "Windows":
            paths = [
                "cloudflared.exe",
                r"C:\Program Files\cloudflared\cloudflared.exe",
                r"C:\Program Files (x86)\cloudflared\cloudflared.exe",
                os.path.expanduser("~\\cloudflared\\cloudflared.exe")
            ]
        else:
            # Linux/Mac
            paths = [
                "cloudflared",
                "/usr/local/bin/cloudflared",
                "/usr/bin/cloudflared",
                os.path.expanduser("~/cloudflared/cloudflared")
            ]

        # 检查 PATH 环境变量
        cloudflared = "cloudflared.exe" if platform.system() == "Windows" else "cloudflared"
        if self._command_exists(cloudflared):
            return cloudflared

        # 检查预定义路径
        for path in paths:
            if os.path.exists(path):
                return path

        self.logger.warning("cloudflared not found, please install it first")
        return cloudflared  # 返回默认值，让系统尝试

    def _command_exists(self, cmd: str) -> bool:
        """检查命令是否存在"""
        try:
            subprocess.run(
                [cmd, "version"],
                capture_output=True,
                check=False,
                timeout=5
            )
            return True
        except (subprocess.SubprocessError, FileNotFoundError):
            return False

    async def initialize(self) -> None:
        """初始化管理器"""
        self._running = True

        # 加载已保存的配置
        await self.load_configs()

        # 启动监控任务
        self._monitor_task = asyncio.create_task(self._monitor_loop())

        self.logger.info("Tunnel Manager initialized")

    async def shutdown(self) -> None:
        """关闭管理器"""
        self._running = False

        # 停止所有 Tunnel
        for tunnel_name in list(self.tunnels.keys()):
            await self.stop_tunnel(tunnel_name)

        # 等待监控任务结束
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

        self.logger.info("Tunnel Manager shutdown")

    async def load_configs(self) -> None:
        """加载所有 Tunnel 配置"""
        config_files = self.config_dir.glob("*.yaml")

        for config_file in config_files:
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                    config = TunnelConfig(**data)

                    # 创建 TunnelInfo
                    info = TunnelInfo(
                        config=config,
                        status=TunnelStatus(state=TunnelState.STOPPED)
                    )

                    self.tunnels[config.name] = info
                    self.logger.info(f"Loaded tunnel config: {config.name}")

            except Exception as e:
                self.logger.error(f"Failed to load config {config_file}: {e}")

    async def save_config(self, config: TunnelConfig) -> None:
        """保存 Tunnel 配置"""
        config_file = self.config_dir / f"{config.name}.yaml"

        try:
            with open(config_file, 'w', encoding='utf-8') as f:
                yaml.dump(config.dict(), f, default_flow_style=False)

            self.logger.info(f"Saved tunnel config: {config.name}")

        except Exception as e:
            self.logger.error(f"Failed to save config: {e}")
            raise

    async def create_tunnel(self, config: TunnelConfig) -> TunnelInfo:
        """
        创建新的 Tunnel
        
        Args:
            config: Tunnel 配置
            
        Returns:
            TunnelInfo 对象
        """
        # 检查是否已存在
        if config.name in self.tunnels:
            raise ValueError(f"Tunnel {config.name} already exists")

        # 保存配置
        await self.save_config(config)

        # 创建 TunnelInfo
        info = TunnelInfo(
            config=config,
            status=TunnelStatus(state=TunnelState.STOPPED)
        )

        self.tunnels[config.name] = info

        self.logger.info(f"Created tunnel: {config.name}")
        return info

    async def start_tunnel(self, tunnel_name: str) -> bool:
        """
        启动 Tunnel
        
        Args:
            tunnel_name: Tunnel 名称
            
        Returns:
            是否成功启动
        """
        if tunnel_name not in self.tunnels:
            raise ValueError(f"Tunnel {tunnel_name} not found")

        info = self.tunnels[tunnel_name]

        # 检查状态
        if info.status.state == TunnelState.RUNNING:
            self.logger.warning(f"Tunnel {tunnel_name} is already running")
            return True

        # 更新状态
        info.status.state = TunnelState.STARTING

        try:
            # 构建命令
            cmd = self._build_command(info.config)

            # 启动进程
            if platform.system() == "Windows":
                # Windows 下隐藏控制台窗口
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    startupinfo=startupinfo
                )
            else:
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )

            self.processes[tunnel_name] = process
            info.status.pid = process.pid

            # 等待启动
            await asyncio.sleep(2)

            # 检查进程状态
            if process.poll() is None:
                info.status.state = TunnelState.RUNNING
                info.status.connected = True
                info.status.connection_time = datetime.now()
                self.logger.info(f"Tunnel {tunnel_name} started (PID: {process.pid})")
                return True
            else:
                # 进程已退出
                stderr = process.stderr.read().decode() if process.stderr else ""
                info.status.state = TunnelState.ERROR
                info.status.last_error = stderr
                info.status.last_error_time = datetime.now()
                self.logger.error(f"Tunnel {tunnel_name} failed to start: {stderr}")
                return False

        except Exception as e:
            info.status.state = TunnelState.ERROR
            info.status.last_error = str(e)
            info.status.last_error_time = datetime.now()
            self.logger.error(f"Failed to start tunnel {tunnel_name}: {e}")
            return False

    async def stop_tunnel(self, tunnel_name: str) -> bool:
        """
        停止 Tunnel
        
        Args:
            tunnel_name: Tunnel 名称
            
        Returns:
            是否成功停止
        """
        if tunnel_name not in self.tunnels:
            raise ValueError(f"Tunnel {tunnel_name} not found")

        info = self.tunnels[tunnel_name]

        # 检查状态
        if info.status.state == TunnelState.STOPPED:
            self.logger.warning(f"Tunnel {tunnel_name} is already stopped")
            return True

        # 更新状态
        info.status.state = TunnelState.STOPPING

        try:
            process = self.processes.get(tunnel_name)
            if process and process.poll() is None:
                # 优雅停止
                process.terminate()

                # 等待进程结束
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    # 强制终止
                    process.kill()
                    process.wait()

                del self.processes[tunnel_name]

            # 更新状态
            info.status.state = TunnelState.STOPPED
            info.status.connected = False
            info.status.pid = None

            self.logger.info(f"Tunnel {tunnel_name} stopped")
            return True

        except Exception as e:
            info.status.state = TunnelState.ERROR
            info.status.last_error = str(e)
            self.logger.error(f"Failed to stop tunnel {tunnel_name}: {e}")
            return False

    async def restart_tunnel(self, tunnel_name: str) -> bool:
        """重启 Tunnel"""
        await self.stop_tunnel(tunnel_name)
        await asyncio.sleep(2)
        return await self.start_tunnel(tunnel_name)

    def _build_command(self, config: TunnelConfig) -> List[str]:
        """
        构建 cloudflared 命令
        
        Args:
            config: Tunnel 配置
            
        Returns:
            命令列表
        """
        cmd = [self.cloudflared_path, "tunnel"]

        # 日志级别
        if config.loglevel:
            cmd.extend(["--loglevel", config.loglevel])

        # 日志文件
        if config.logfile:
            cmd.extend(["--logfile", config.logfile])

        # Metrics
        if config.metrics_enabled:
            cmd.extend(["--metrics", f"localhost:{config.metrics_port}"])

        # 协议
        if config.protocol:
            cmd.extend(["--protocol", config.protocol])

        # 运行命令
        cmd.append("run")

        # Token 或配置文件
        if config.token:
            cmd.extend(["--token", config.token])
        elif config.config_file:
            cmd.extend(["--config", config.config_file])
        else:
            # 使用名称和认证文件
            if config.credentials_file:
                cmd.extend(["--credentials-file", config.credentials_file])
            cmd.append(config.name)

        return cmd

    async def _monitor_loop(self) -> None:
        """监控循环"""
        while self._running:
            try:
                # 检查所有 Tunnel 状态
                for tunnel_name, info in self.tunnels.items():
                    await self._check_tunnel_status(tunnel_name, info)

                # 收集指标
                await self._collect_metrics()

            except Exception as e:
                self.logger.error(f"Monitor loop error: {e}")

            # 等待下次检查
            await asyncio.sleep(5)

    async def _check_tunnel_status(self, tunnel_name: str, info: TunnelInfo) -> None:
        """检查 Tunnel 状态"""
        process = self.processes.get(tunnel_name)

        if process:
            # 检查进程是否存活
            if process.poll() is not None:
                # 进程已退出
                info.status.state = TunnelState.STOPPED
                info.status.connected = False
                info.status.pid = None

                # 读取错误信息
                if process.stderr:
                    stderr = process.stderr.read().decode()
                    if stderr:
                        info.status.last_error = stderr
                        info.status.last_error_time = datetime.now()
                        info.status.error_count += 1

                del self.processes[tunnel_name]

                # 自动重启
                if info.config.auto_restart and info.status.state != TunnelState.STOPPING:
                    self.logger.info(f"Auto-restarting tunnel {tunnel_name}")
                    await asyncio.sleep(info.config.restart_delay)
                    await self.start_tunnel(tunnel_name)
            else:
                # 进程存活，更新资源使用
                try:
                    p = psutil.Process(process.pid)
                    info.status.cpu_percent = p.cpu_percent()
                    info.status.memory_mb = p.memory_info().rss / 1024 / 1024

                    # 计算运行时间
                    if info.status.connection_time:
                        delta = datetime.now() - info.status.connection_time
                        info.uptime_seconds = int(delta.total_seconds())

                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

    async def _collect_metrics(self) -> None:
        """收集指标数据"""
        for tunnel_name, info in self.tunnels.items():
            if info.status.state != TunnelState.RUNNING:
                continue

            # 如果启用了 metrics，尝试从 cloudflared 获取
            if info.config.metrics_enabled:
                try:
                    # 从 metrics 端点获取数据
                    # TODO: 实现 Prometheus metrics 解析
                    pass
                except Exception as e:
                    self.logger.debug(f"Failed to collect metrics for {tunnel_name}: {e}")

    def get_tunnel_info(self, tunnel_name: str) -> Optional[TunnelInfo]:
        """获取 Tunnel 信息"""
        return self.tunnels.get(tunnel_name)

    def list_tunnels(self) -> List[TunnelInfo]:
        """列出所有 Tunnel"""
        return list(self.tunnels.values())

    def get_status(self) -> Dict[str, Any]:
        """获取管理器状态"""
        return {
            "running": self._running,
            "tunnel_count": len(self.tunnels),
            "active_tunnels": sum(1 for t in self.tunnels.values()
                                  if t.status.state == TunnelState.RUNNING),
            "cloudflared_path": self.cloudflared_path,
            "config_dir": str(self.config_dir)
        }
