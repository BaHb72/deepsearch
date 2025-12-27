"""
Redis 自动启动辅助。

提供 Windows 环境下的 Redis 自启动逻辑
"""

from __future__ import annotations

import ipaddress
import platform
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence

from loguru import logger
from redis import Redis
from redis.exceptions import RedisError

from deepsearch.config.models.database import CacheDatabaseConfig, CacheDatabaseWSLConfig

EchoFunc = Callable[[str], None]
DEFAULT_WAIT_TIMEOUT = 15.0
WAIT_INTERVAL_SECONDS = 0.5


@dataclass
class _WSLRuntimeState:
    last_ip: Optional[str] = None
    resolved: bool = False


_WSL_STATE: Dict[int, _WSLRuntimeState] = {}
_WSL_NETWORK_MODE: Optional[str] = None


class RedisStartupError(RuntimeError):
    """Redis 拉起失败时抛出的异常。"""


def _build_default_wsl_start_command(
    wsl_config: Optional[CacheDatabaseWSLConfig],
) -> List[str]:
    command: List[str] = []
    if wsl_config is None:
        return command

    distro = (wsl_config.distro or "").strip()
    if not distro:
        return command

    command.extend(["wsl.exe", "-d", distro])

    user = getattr(wsl_config, "user", None)
    if user:
        command.extend(["-u", user])

    service_name = getattr(wsl_config, "service_name", None) or "redis-server"
    command.extend(["service", service_name, "start"])
    return command


def _decode_subprocess_output(data: bytes | str | None) -> str:
    if not data:
        return ""

    if isinstance(data, str):
        return data.strip()

    for encoding in ("utf-8", "utf-8-sig", "utf-16", "utf-16-le", "utf-16-be", "gbk"):
        try:
            return data.decode(encoding).strip()
        except UnicodeDecodeError:
            continue

    return data.decode("utf-8", errors="ignore").strip()


def _merge_subprocess_output(*parts: bytes | str | None) -> str:
    decoded = [_decode_subprocess_output(part) for part in parts]
    return " ".join(part for part in decoded if part).strip()


def ensure_redis_running(
    cache_config: Optional[CacheDatabaseConfig], *, echo: Optional[EchoFunc] = None
) -> None:
    """确保 Redis 处于可连接状态。"""

    if cache_config is None:
        logger.debug("未配置 Redis 缓存，跳过自动启动")
        return

    if not cache_config.enabled:
        logger.debug("Redis 缓存已禁用，跳过自动启动")
        return

    echo_fn = echo or (lambda _: None)

    wsl_config: Optional[CacheDatabaseWSLConfig] = getattr(cache_config, "wsl", None)
    wsl_enabled = _is_wsl_mode(wsl_config)
    prepare_hook: Optional[Callable[[], None]] = None

    if wsl_enabled and wsl_config is not None:

        def _hook() -> None:
            _refresh_wsl_host(cache_config, wsl_config, echo_fn, force=False)

        prepare_hook = _hook
        _refresh_wsl_host(cache_config, wsl_config, echo_fn, force=True)

    if not (_is_local_host(cache_config.host) or wsl_enabled):
        logger.debug("Redis host {} is remote, skip auto-start", cache_config.host)
        return

    if _can_connect(cache_config):
        logger.debug("Redis already reachable ({}:{})", cache_config.host, cache_config.port)
        return

    if platform.system() != "Windows":
        raise RedisStartupError(
            f"检测到 Redis 未运行，请手动启动 {cache_config.host}:{cache_config.port}"
        )

    if not cache_config.auto_start_windows:
        raise RedisStartupError("Redis 未运行，且关闭了 Windows 自动启动，请手动启动 Redis 服务")

    echo_fn("检测到本地 Redis 未运行，正在尝试自动启动...")
    logger.info("尝试自动拉起 Redis 服务")

    startup_command: List[str] = list(cache_config.startup_command or [])
    used_default_wsl_command = False

    if wsl_enabled and not startup_command:
        startup_command = _build_default_wsl_start_command(wsl_config)
        if startup_command:
            used_default_wsl_command = True
            logger.debug("WSL 模式启用，使用默认启动命令: {}", " ".join(startup_command))
        else:
            logger.debug("WSL 模式启用，但无法构造默认启动命令（缺少发行版配置）")

    service_names = [name for name in (cache_config.windows_service_names or []) if name]
    attempts: List[str] = []

    if service_names:
        attempts.append("Windows 服务")
        if _start_via_services(service_names, echo_fn):
            if wsl_enabled and wsl_config is not None:
                _refresh_wsl_host(cache_config, wsl_config, echo_fn, force=True)
            if _wait_for_redis(cache_config, prepare_hook):
                echo_fn("Redis 服务已就绪")
                return

    if cache_config.startup_binary_path:
        attempts.append("可执行文件")
        if _start_via_binary(
            cache_config.startup_binary_path, cache_config.startup_arguments, echo_fn
        ):
            if wsl_enabled and wsl_config is not None:
                _refresh_wsl_host(cache_config, wsl_config, echo_fn, force=True)
            if _wait_for_redis(cache_config, prepare_hook):
                echo_fn("Redis 可执行文件已启动")
                return

    if startup_command:
        command_label = "启动命令"
        if used_default_wsl_command:
            command_label = "WSL 启动命令(默认)"
        elif wsl_enabled:
            command_label = "WSL 启动命令"
        attempts.append(command_label)
        if _start_via_command(startup_command, echo_fn):
            if wsl_enabled and wsl_config is not None:
                _refresh_wsl_host(cache_config, wsl_config, echo_fn, force=True)
            if _wait_for_redis(cache_config, prepare_hook):
                echo_fn("Redis 自动启动命令执行完成")
                return

    detail = "、".join(attempts) if attempts else "Windows/WSL 自动启动机制"
    raise RedisStartupError(
        f"无法自动启动 Redis ({cache_config.host}:{cache_config.port})，已尝试 {detail}。"
        "请检查 windows_service_names、startup_binary_path 或 WSL 启动命令配置。"
    )


def _is_local_host(host: str) -> bool:
    normalized = host.strip().lower()
    if normalized in {"localhost", "127.0.0.1", "::1"}:
        return True

    try:
        ip = ipaddress.ip_address(normalized)
        return ip.is_loopback
    except ValueError:
        return False


def _is_wsl_mode(wsl_config: Optional[CacheDatabaseWSLConfig]) -> bool:
    if wsl_config is None:
        return False
    if not wsl_config.enabled:
        return False
    if platform.system() != "Windows":
        logger.debug("检测到 WSL 配置，但当前系统不是 Windows，忽略 WSL 自动解析")
        return False
    return True


def _get_wsl_state(config: CacheDatabaseConfig) -> _WSLRuntimeState:
    return _WSL_STATE.setdefault(id(config), _WSLRuntimeState())


def _detect_wsl_network_mode() -> Optional[str]:
    """
    检测 WSL 的网络模式。

    Returns:
        MIRRORED | NAT，无法识别时返回 None
    """

    global _WSL_NETWORK_MODE

    if _WSL_NETWORK_MODE is not None:
        return _WSL_NETWORK_MODE

    try:
        result = subprocess.run(
            ["wsl.exe", "--status"],
            capture_output=True,
            text=False,
            check=False,
        )
    except FileNotFoundError:
        _WSL_NETWORK_MODE = None
        return None
    except Exception as exc:  # pragma: no cover - WSL 状态命令执行失败
        logger.debug(f"查询 WSL 状态失败: {exc}")
        _WSL_NETWORK_MODE = None
        return None

    output = _merge_subprocess_output(result.stdout, result.stderr)
    if not output:
        _WSL_NETWORK_MODE = None
        return None

    pattern = re.compile(r"(networking|network)\s*mode\s*[:：]\s*([A-Za-z]+)", re.IGNORECASE)
    match = pattern.search(output)

    if not match:
        pattern_cn = re.compile(r"网络模式\s*[:：]\s*([^\s]+)")
        match = pattern_cn.search(output)
        if match:
            candidate = match.group(1).strip().lower()
        else:
            candidate = None
    else:
        candidate = match.group(2).strip().lower()

    _WSL_NETWORK_MODE = candidate
    if _WSL_NETWORK_MODE:
        logger.debug(f"WSL 网络模式: {_WSL_NETWORK_MODE}")

    return _WSL_NETWORK_MODE


def _refresh_wsl_host(
    config: CacheDatabaseConfig,
    wsl_config: CacheDatabaseWSLConfig,
    echo_fn: EchoFunc,
    *,
    force: bool,
) -> Optional[str]:
    state = _get_wsl_state(config)
    if not force and state.resolved:
        return state.last_ip

    ip = _resolve_wsl_ip(wsl_config)
    if not ip:
        state.resolved = False
        return None

    ip_changed = state.last_ip != ip
    state.last_ip = ip
    state.resolved = True

    network_mode = _detect_wsl_network_mode()
    mirrored_mode = network_mode == "mirrored"
    target_host = "127.0.0.1" if mirrored_mode else ip
    should_update_host = wsl_config.auto_resolve_ip and config.host != target_host

    if mirrored_mode:
        if should_update_host:
            logger.info(
                "WSL {} Mirrored \u6a21\u5f0f\uff0c\u4f7f\u7528 localhost \u8bbf\u95ee Redis (WSL IP: {})",
                wsl_config.distro,
                ip,
            )
            echo_fn(
                "\u68c0\u6d4b\u5230 WSL Mirrored \u6a21\u5f0f\uff0c\u6539\u7528 127.0.0.1 \u8bbf\u95ee Redis"
            )
            config.host = target_host
        elif ip_changed:
            logger.info("WSL {} Mirrored \u6a21\u5f0f IP \u53d8\u66f4: {}", wsl_config.distro, ip)
    else:
        if should_update_host:
            if ip_changed:
                logger.info(f"刷新 WSL 发行版 {wsl_config.distro} 的 IP: {ip}")
                echo_fn(f"刷新 WSL {wsl_config.distro} 的 IP: {ip}")
            config.host = target_host
        elif ip_changed:
            logger.info(f"WSL 发行版 {wsl_config.distro} 的 IP 发生变化: {ip}")

    return target_host


def _resolve_wsl_ip(wsl_config: CacheDatabaseWSLConfig) -> Optional[str]:
    command = ["wsl.exe", "-d", wsl_config.distro, "hostname", "-I"]
    try:
        result = subprocess.run(command, capture_output=True, text=False, check=False)
    except FileNotFoundError as exc:
        logger.debug("无法执行 wsl.exe 解析 WSL IP: {}", exc)
        return None
    except Exception as exc:  # pragma: no cover - 防御性日志
        logger.warning("解析 WSL IP 异常: {}", exc)
        return None

    if result.returncode != 0:
        output = _merge_subprocess_output(result.stdout, result.stderr)
        logger.debug("WSL {} IP 查询失败: {}", wsl_config.distro, output)
        return None

    stdout_text = _decode_subprocess_output(result.stdout)
    for token in stdout_text.split():
        try:
            ip_obj = ipaddress.ip_address(token)
        except ValueError:
            continue
        if getattr(ip_obj, "version", 4) == 4:
            return token
    logger.debug("WSL({}) 未返回有效 IPv4 地址: {}", wsl_config.distro, stdout_text)
    return None


def _build_client(config: CacheDatabaseConfig) -> Redis:
    password = config.password or None
    if password == "***":
        password = None

    username = config.username or None
    if username == "***":
        username = None

    logger.debug(f"DEBUG: _build_client username={repr(username)} password={repr(password)}")
    return Redis(
        host=config.host,
        port=config.port,
        db=config.db,
        username=username,
        password=password,
        socket_timeout=config.socket_timeout,
        socket_connect_timeout=config.socket_connect_timeout,
        socket_keepalive=config.socket_keepalive,
        retry_on_timeout=config.retry_on_timeout,
        health_check_interval=config.health_check_interval,
        max_connections=config.pool_size or None,
    )


def _can_connect(config: CacheDatabaseConfig) -> bool:
    client = _build_client(config)
    try:
        client.ping()
        return True
    except (ValueError, RedisError) as exc:
        logger.debug("Redis ping 失败: {}", exc)
        return False
    finally:
        try:
            client.close()
        except Exception:
            pass


def _wait_for_redis(
    config: CacheDatabaseConfig, prepare_hook: Optional[Callable[[], None]] = None
) -> bool:
    deadline = time.monotonic() + DEFAULT_WAIT_TIMEOUT
    while time.monotonic() < deadline:
        if prepare_hook:
            prepare_hook()
        if _can_connect(config):
            return True
        time.sleep(WAIT_INTERVAL_SECONDS)
    return False


def _start_via_services(service_names: Sequence[str], echo_fn: EchoFunc) -> bool:
    for service_name in service_names:
        if not service_name:
            continue

        status = _query_service(service_name)
        if status == "running":
            logger.info("Windows 服务 {} 已运行", service_name)
            return True

        if status is None:
            logger.debug("Windows 服务 {} 不存在或未注册", service_name)
            continue

        echo_fn(f"尝试启动 Windows 服务 {service_name} ...")
        if _start_service(service_name) and _wait_for_service(service_name):
            return True
    return False


def _query_service(service_name: str) -> Optional[str]:
    try:
        result = subprocess.run(
            ["sc", "query", service_name],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        logger.warning("查询 Windows 服务 {} 失败: {}", service_name, exc)
        return None

    if result.returncode != 0:
        output = _merge_subprocess_output(result.stdout, result.stderr)
        logger.debug("Windows 服务 {} 查询失败: {}", service_name, output)
        return None

    output = result.stdout.lower()
    if "running" in output:
        return "running"
    if "stopped" in output:
        return "stopped"
    return "unknown"


def _start_service(service_name: str) -> bool:
    try:
        result = subprocess.run(
            ["sc", "start", service_name],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        logger.error("启动 Windows 服务 {} 失败: {}", service_name, exc)
        return False

    output = (result.stdout + result.stderr).lower()
    if result.returncode == 0 or "service already running" in output:
        logger.info("已发送启动指令到 Windows 服务 {}", service_name)
        return True

    logger.warning("Windows 服务 {} 启动失败: {}", service_name, output.strip())
    return False


def _wait_for_service(service_name: str) -> bool:
    deadline = time.monotonic() + DEFAULT_WAIT_TIMEOUT
    while time.monotonic() < deadline:
        status = _query_service(service_name)
        if status == "running":
            return True
        time.sleep(WAIT_INTERVAL_SECONDS)
    logger.debug("Windows 服务 {} 在超时时间内仍未运行", service_name)
    return False


def _start_via_binary(binary_path: str, arguments: Sequence[str], echo_fn: EchoFunc) -> bool:
    path_obj = Path(binary_path).expanduser()
    if not path_obj.exists():
        logger.warning("Redis 可执行文件不存在: {}", path_obj)
        echo_fn(f"Redis 可执行文件不存在: {path_obj}")
        return False

    command = [str(path_obj)] + list(arguments or [])
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    echo_fn(f"正在执行 {path_obj} 启动 Redis...")

    try:
        subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=str(path_obj.parent),
            creationflags=creation_flags,
        )
        logger.info("已执行 Redis 可执行文件: {}", " ".join(command))
        return True
    except Exception as exc:
        logger.error("启动 Redis 可执行文件失败: {}", exc)
        return False


def _start_via_command(command: Sequence[str], echo_fn: EchoFunc) -> bool:
    if not command:
        return False

    echo_fn("正在执行自动启动命令...")
    try:
        result = subprocess.run(
            list(command),
            capture_output=True,
            text=False,
            check=False,
        )
    except Exception as exc:
        logger.error("执行自动启动命令失败: {}", exc)
        return False

    if result.returncode == 0:
        logger.info("自动启动命令执行成功")
        return True

    output = _merge_subprocess_output(result.stdout, result.stderr) or "<无输出信息>"
    logger.warning("自动启动命令返回非零状态: {}", output)
    return False
