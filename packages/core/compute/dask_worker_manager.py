"""
Windows Dask Worker 管理器

在后端 API 启动时自动启动 Windows Dask Worker 进程，
用于托管需要 Windows 环境的数据源 SDK（AmazingData、MiniQMT 等）。
"""

from __future__ import annotations

import asyncio
import socket
import subprocess
import sys
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    pass

# 全局 Worker 进程句柄
_worker_process: subprocess.Popen | None = None
_plugin_registered: bool = False


async def _register_amazingdata_plugin(scheduler_address: str) -> bool:
    """注册 AmazingData Worker Plugin 到 Dask 集群

    Args:
        scheduler_address: Dask Scheduler 地址，如 "tcp://localhost:8786"

    Returns:
        True 如果注册成功，False 如果失败
    """
    global _plugin_registered

    if _plugin_registered:
        logger.debug("AmazingData Plugin 已注册，跳过")
        return True

    try:
        from core.config import get_config
        from core.infrastructure.providers.implementations.amazingdata.dask_plugin import (
            AmazingDataWorkerPlugin,
        )
        from distributed import Client

        # 获取 Redis URL
        settings = get_config()
        redis_url = "redis://localhost:6379"  # 默认值

        # 尝试从配置获取
        database_config = getattr(settings, "database", None)
        if database_config:
            cache_config = getattr(database_config, "cache", None)
            if cache_config:
                host = getattr(cache_config, "host", "localhost")
                port = getattr(cache_config, "port", 6379)
                redis_url = f"redis://{host}:{port}"

        # 创建临时 Client 注册 Plugin
        async with Client(scheduler_address, asynchronous=True) as client:
            plugin = AmazingDataWorkerPlugin(
                redis_url=redis_url,
                only_on_windows=True,
            )
            await client.register_plugin(plugin)
            _plugin_registered = True
            logger.info(f"AmazingData Worker Plugin 已注册 | redis_url={redis_url}")
            return True

    except ImportError as e:
        logger.warning(f"无法导入 Dask 依赖，跳过 Plugin 注册: {e}")
        return False
    except Exception as e:
        logger.error(f"注册 AmazingData Plugin 失败: {e}")
        return False


def _check_scheduler_available(host: str = "localhost", port: int = 8786) -> bool:
    """检查 Dask Scheduler 是否可达

    Args:
        host: Scheduler 主机地址
        port: Scheduler 端口

    Returns:
        True 如果可连接，否则 False
    """
    try:
        with socket.create_connection((host, port), timeout=3):
            return True
    except (OSError, socket.timeout):
        return False


def _parse_scheduler_address(address: str) -> tuple[str, int]:
    """解析 Scheduler 地址

    Args:
        address: 格式如 "localhost:8786" 或 "tcp://127.0.0.1:8786"

    Returns:
        (host, port) 元组
    """
    # 移除协议前缀
    if address.startswith("tcp://"):
        address = address[6:]
    elif address.startswith("://"):
        address = address[3:]

    # 分割 host:port
    if ":" in address:
        host, port_str = address.rsplit(":", 1)
        return host, int(port_str)
    return address, 8786


def _get_host_address_for_docker() -> str:
    """获取 Docker 容器可访问的主机 IP 地址

    用于 Windows Worker 注册时使用，确保 Docker 容器内的 Scheduler 能够访问 Worker。

    Returns:
        主机 IP 地址字符串
    """
    import socket

    try:
        # 方法1: 尝试获取连接到外网时使用的 IP（最可靠）
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(1)
        try:
            # 不实际发送数据，只是获取本机使用的 IP
            s.connect(("8.8.8.8", 80))
            host_ip = s.getsockname()[0]
            s.close()
            # 检查是否是有效的非回环地址
            if host_ip and not host_ip.startswith("127."):
                logger.debug(f"检测到主机 IP（通过 socket）: {host_ip}")
                return host_ip
        except Exception:
            s.close()

        # 方法2: 遍历网络接口查找合适的 IP
        hostname = socket.gethostname()
        for addr_info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = str(addr_info[4][0])
            if ip and not ip.startswith("127.") and not ip.startswith("169.254."):
                logger.debug(f"检测到主机 IP（通过 hostname）: {ip}")
                return ip

        # 方法3: 回退到 host.docker.internal（Docker Desktop 支持）
        logger.warning("无法检测主机 IP，使用 host.docker.internal")
        return "host.docker.internal"

    except Exception as e:
        logger.warning(f"获取主机 IP 失败: {e}，使用 host.docker.internal")
        return "host.docker.internal"


async def ensure_windows_workers() -> bool:
    """确保 Windows Dask Workers 已启动

    读取配置文件中的 dask.windows_workers 设置，
    如果启用了 auto_start，则启动 Worker 进程。

    Returns:
        True 如果启动成功或已有 Worker，False 如果失败
    """
    global _worker_process

    # 只在 Windows 上运行
    if sys.platform != "win32":
        logger.debug("非 Windows 环境，跳过 Windows Worker 自启动")
        return True

    try:
        from core.config import get_config

        settings = get_config()

        # 获取 Dask 配置（从 infrastructure.{env}.yaml）
        dask_config = getattr(settings, "dask", None)
        if dask_config is None:
            logger.debug("未找到 Dask 配置，跳过 Windows Worker 自启动")
            return True

        # 检查是否启用自动启动
        windows_workers = getattr(dask_config, "windows_workers", None)
        if windows_workers is None:
            logger.debug("未找到 Windows Workers 配置")
            return True

        if not getattr(windows_workers, "enabled", False):
            logger.debug("Windows Workers 未启用")
            return True

        if not getattr(windows_workers, "auto_start", False):
            logger.debug("Windows Workers 自启动未开启")
            return True

        # 解析 Scheduler 地址
        scheduler_address = getattr(dask_config, "scheduler_address", "localhost:8786")
        host, port = _parse_scheduler_address(scheduler_address)

        # 检查 Scheduler 是否可达
        if not _check_scheduler_available(host, port):
            logger.warning(f"Dask Scheduler 不可达 ({host}:{port})，请确保 Docker 服务已启动")
            return False

        # 检查是否已有 Worker 进程运行
        if _worker_process is not None and _worker_process.poll() is None:
            logger.debug("Windows Worker 进程已在运行中")
            return True

        # 从配置获取 Worker 参数
        num_workers = getattr(windows_workers, "num_workers", 2)
        threads_per_worker = getattr(windows_workers, "threads_per_worker", 2)
        memory_limit = getattr(windows_workers, "memory_limit", "4GB")
        name_prefix = getattr(windows_workers, "name_prefix", "windows-worker")

        # 获取主机 IP（用于 Docker 容器访问 Worker）
        host_address = _get_host_address_for_docker()

        # 构建启动命令
        cmd = [
            "uv",
            "run",
            "dask",
            "worker",
            f"tcp://{host}:{port}",
            "--nworkers",
            str(num_workers),
            "--nthreads",
            str(threads_per_worker),
            "--memory-limit",
            memory_limit,
            "--resources",
            "WIN=1",
            "--name",
            name_prefix,
            "--host",
            host_address,  # 关键：使用主机 IP 注册，Docker 容器可访问
        ]

        logger.info(f"启动 Windows Dask Workers: {' '.join(cmd)}")

        # 启动子进程（后台运行）
        _worker_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,  # Windows: 允许独立关闭
        )

        # 给 Worker 一点时间连接到 Scheduler
        await asyncio.sleep(2)

        # 检查进程是否仍在运行
        if _worker_process.poll() is not None:
            # 进程已退出，读取错误输出
            _, stderr = _worker_process.communicate(timeout=1)
            error_msg = stderr.decode("utf-8", errors="replace") if stderr else "Unknown error"
            logger.error(f"Windows Worker 启动失败: {error_msg}")
            _worker_process = None
            return False

        logger.info(f"Windows Dask Workers 已启动 (PID: {_worker_process.pid})")

        # 注册 AmazingData Worker Plugin
        scheduler_address = f"tcp://{host}:{port}"
        await _register_amazingdata_plugin(scheduler_address)

        return True

    except Exception as e:
        logger.error(f"启动 Windows Workers 时出错: {e}")
        return False


async def stop_windows_workers() -> None:
    """停止 Windows Dask Workers

    优雅地关闭之前启动的 Worker 进程。
    """
    global _worker_process

    if _worker_process is None:
        return

    if _worker_process.poll() is not None:
        # 进程已经退出
        _worker_process = None
        return

    try:
        logger.info("正在停止 Windows Dask Workers...")

        # 先尝试优雅关闭 (CTRL_BREAK_EVENT on Windows)
        if sys.platform == "win32":
            import signal

            _worker_process.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            _worker_process.terminate()

        # 等待进程退出
        try:
            _worker_process.wait(timeout=10)
            logger.info("Windows Dask Workers 已停止")
        except subprocess.TimeoutExpired:
            # 超时则强制杀死
            logger.warning("Worker 进程未响应，强制终止")
            _worker_process.kill()
            _worker_process.wait(timeout=5)

    except Exception as e:
        logger.warning(f"停止 Windows Workers 时出错: {e}")
    finally:
        _worker_process = None


def get_worker_status() -> dict:
    """获取 Worker 进程状态

    Returns:
        状态信息字典
    """
    global _worker_process

    if _worker_process is None:
        return {"running": False, "pid": None}

    poll_result = _worker_process.poll()
    if poll_result is not None:
        return {"running": False, "pid": None, "exit_code": poll_result}

    return {"running": True, "pid": _worker_process.pid}
