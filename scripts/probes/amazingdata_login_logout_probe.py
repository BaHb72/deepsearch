# encoding:utf-8
"""
AmazingData 登录/退出进程探测脚本。

用于验证指定凭据在登录与退出阶段是否引发 worker 进程崩溃，并尝试捕获 SystemExit 迹象。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import multiprocessing as mp
import pickle
import queue
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional

from loguru import logger

from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_process_adapter import (
    AmazingDataProcessAdapter,
)
from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_process_pool import (
    get_global_pool,
)
from deepsearch.ports.amazingdata_process import (
    AmazingDataLoginRequest,
    AmazingDataLogoutRequest,
)

DEFAULT_USERNAME = "212200038719"
DEFAULT_PASSWORD = "212200038719@2025"
DEFAULT_HOST = "101.230.159.234"
DEFAULT_PORT = 8600


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="检测 AmazingData 登录、退出对 worker 进程的影响")
    parser.add_argument("--username", default=DEFAULT_USERNAME, help="登录用户名")
    parser.add_argument("--password", default=DEFAULT_PASSWORD, help="登录密码")
    parser.add_argument("--host", default=DEFAULT_HOST, help="数据源主机地址")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="数据源端口")
    parser.add_argument("--login-timeout", type=float, default=10.0, help="登录超时时间（秒）")
    parser.add_argument("--logout-timeout", type=float, default=5.0, help="退出超时时间（秒）")
    parser.add_argument(
        "--exit-wait",
        type=float,
        default=5.0,
        help="等待 worker 在退出后完全结束的最长时间（秒）",
    )
    parser.add_argument(
        "--python-interpreter",
        help="可选，指定 AmazingData SDK 所需的 Python 解释器路径（例如 3.13）",
    )
    parser.add_argument(
        "--worker-env",
        action="append",
        default=[],
        help="以 KEY=VALUE 形式提供 worker 进程的额外环境变量，可重复使用该参数",
    )
    parser.add_argument(
        "--auto-cleanup",
        action="store_true",
        help="启用进程池自动清理，默认关闭以便脚本主动回收",
    )
    parser.add_argument(
        "--cleanup-delay",
        type=float,
        default=60.0,
        help="启用自动清理时的延迟秒数，默认 60 秒",
    )
    parser.add_argument(
        "--datasource-id",
        help="可选，自定义 datasource_id，若不提供则自动生成唯一 ID",
    )
    parser.add_argument(
        "--startup-timeout",
        type=float,
        default=10.0,
        help="worker 启动超时时间（秒）",
    )
    parser.add_argument("--log-level", default="INFO", help="日志级别，例如 INFO/DEBUG")
    return parser.parse_args()


def configure_logger(level: str) -> None:
    logger.remove()
    logger.add(
        sys.stdout,
        level=level.upper(),
        format="[{time:YYYY-MM-DD HH:mm:ss}] [{level}] {message}",
    )


def parse_worker_env(items: List[str]) -> Dict[str, str]:
    env: Dict[str, str] = {}
    for item in items:
        key_value = item.split("=", 1)
        if len(key_value) != 2:
            raise ValueError(f"无法解析 worker-env 参数: {item}")
        key, value = key_value[0].strip(), key_value[1].strip()
        if not key:
            raise ValueError(f"worker-env 键不能为空: {item}")
        env[key] = value
    return env


def build_proxy_config(args: argparse.Namespace) -> Dict[str, Any]:
    config: Dict[str, Any] = {}
    if args.python_interpreter:
        config["python_executable"] = args.python_interpreter
    if args.worker_env:
        config["worker_env"] = dict(args.worker_env)
    if args.startup_timeout:
        config["startup_timeout"] = max(float(args.startup_timeout), 1.0)
    return config


def snapshot_worker_state(proxy: Any, *, include_stats: bool = False) -> Dict[str, Any]:
    process = getattr(proxy, "worker_process", None)
    state: Dict[str, Any] = {
        "alive": bool(proxy.is_worker_alive()),
        "pid": getattr(process, "pid", None),
        "process_type": None,
        "exit_code": None,
    }
    if isinstance(process, mp.Process):
        state["process_type"] = "multiprocessing"
        state["exit_code"] = process.exitcode
    elif isinstance(process, subprocess.Popen):
        state["process_type"] = "subprocess"
        state["exit_code"] = process.poll()
    elif process is None:
        state["process_type"] = None
    else:
        state["process_type"] = type(process).__name__
        exit_code = getattr(process, "exitcode", None)
        if exit_code is None and hasattr(process, "poll"):
            exit_code = process.poll()
        state["exit_code"] = exit_code
    if include_stats:
        try:
            state["stats"] = proxy.get_stats()
        except Exception as exc:
            state["stats_error"] = str(exc)
    return state


def tag_events(stage: str, events: List[Dict[str, Any]], source: str) -> List[Dict[str, Any]]:
    for event in events:
        event.setdefault("stage", stage)
        event.setdefault("source", source)
    return events


def collect_system_exit_events(proxy: Any, attempts: int = 5) -> List[Dict[str, Any]]:
    response_queue = getattr(proxy, "response_queue", None)
    if response_queue is None:
        return []

    events: List[Dict[str, Any]] = []
    for _ in range(max(attempts, 1)):
        try:
            raw = response_queue.get(timeout=0.01)
        except queue.Empty:
            break
        except Exception as exc:
            events.append({"error": f"读取响应队列失败: {exc}"})
            break

        try:
            payload: Dict[str, Any] = pickle.loads(raw)
        except Exception as exc:
            events.append({"error": f"解析响应载荷失败: {exc}"})
            continue

        if payload.get("error_type") == "SystemExit":
            events.append(
                {
                    "request_id": payload.get("request_id"),
                    "error": payload.get("error"),
                    "timestamp": payload.get("timestamp"),
                }
            )
        else:
            try:
                response_queue.put(raw)
            except Exception as exc:
                events.append({"error": f"回填非 SystemExit 响应失败: {exc}"})
            break

    return events


async def wait_for_process_exit(proxy: Any, timeout: float) -> Dict[str, Any]:
    start = time.time()
    interval = 0.2
    while proxy.is_worker_alive() and (time.time() - start) < timeout:
        await asyncio.sleep(interval)
    elapsed = time.time() - start
    state = snapshot_worker_state(proxy, include_stats=True)
    state["wait_elapsed"] = elapsed
    state["wait_timeout"] = timeout
    state["terminated_in_time"] = not state.get("alive", False)
    return state


def build_summary(
        report: Dict[str, Any],
        events: List[Dict[str, Any]],
        last_crash: Optional[str],
) -> Dict[str, Any]:
    stages = report.get("stages", {})
    login_info = report.get("login", {})
    logout_info = report.get("logout", {})

    after_login = stages.get("after_login", {})
    after_wait = stages.get("after_wait", {})

    summary: Dict[str, Any] = {
        "login_success": bool(login_info.get("success")),
        "worker_alive_after_login": bool(after_login.get("alive")),
        "logout_success": bool(logout_info.get("success")),
        "worker_alive_after_logout_wait": bool(after_wait.get("alive")),
        "logout_exit_code": after_wait.get("exit_code"),
        "terminated_in_time": after_wait.get("terminated_in_time"),
        "wait_elapsed": after_wait.get("wait_elapsed"),
    }

    summary["login_crash_detected"] = (
            not summary["login_success"] or not summary["worker_alive_after_login"]
    )

    logout_crash = not summary["logout_success"] or summary["worker_alive_after_logout_wait"]
    exit_code = summary["logout_exit_code"]
    if exit_code not in (None, 0):
        logout_crash = True
    if last_crash:
        logout_crash = True
        summary["last_crash_reason"] = last_crash
    summary["logout_crash_detected"] = logout_crash

    system_exit_detected = bool(events)
    summary["system_exit_detected"] = system_exit_detected
    if system_exit_detected:
        summary["system_exit_events"] = events

    return summary


async def execute_probe(args: argparse.Namespace) -> Dict[str, Any]:
    pool = get_global_pool()
    proxy_config = build_proxy_config(args)
    cleanup_delay = max(args.cleanup_delay, 1.0)
    datasource_id = (
            args.datasource_id
            or f"probe::{args.username}@{args.host}:{args.port}:{int(time.time() * 1000)}"
    )

    proxy = await asyncio.to_thread(
        pool.get_or_create,
        datasource_id,
        args.auto_cleanup,
        cleanup_delay,
        proxy_config,
    )
    adapter = AmazingDataProcessAdapter(proxy)

    report: Dict[str, Any] = {
        "datasource_id": datasource_id,
        "target": {
            "username": args.username,
            "host": args.host,
            "port": args.port,
        },
        "stages": {},
    }

    system_exit_events: List[Dict[str, Any]] = []

    try:
        report["stages"]["initial"] = snapshot_worker_state(proxy)

        if not await adapter.ensure_started():
            report["error"] = "worker 启动失败"
            return report

        report["stages"]["after_start"] = snapshot_worker_state(proxy)

        login_request = AmazingDataLoginRequest(
            username=args.username,
            password=args.password,
            host=args.host,
            port=args.port,
            timeout=max(args.login_timeout, 1.0),
        )
        login_result = await adapter.login(login_request)
        report["login"] = {
            "success": login_result.success,
            "error": login_result.error,
            "error_type": login_result.error_type,
            "metadata": dict(login_result.metadata) if login_result.metadata else None,
        }
        if login_result.error_type == "SystemExit":
            system_exit_events.append(
                {"stage": "login", "source": "result", "error": login_result.error}
            )

        report["stages"]["after_login"] = snapshot_worker_state(proxy)

        queue_events = collect_system_exit_events(proxy)
        if queue_events:
            system_exit_events.extend(tag_events("login", queue_events, "queue"))

        logout_request = AmazingDataLogoutRequest(
            username=args.username,
            timeout=max(args.logout_timeout, 1.0),
        )
        logout_result = await adapter.logout(logout_request)
        report["logout"] = {
            "success": logout_result.success,
            "error": logout_result.error,
            "error_type": logout_result.error_type,
            "metadata": dict(logout_result.metadata) if logout_result.metadata else None,
        }
        if logout_result.error_type == "SystemExit":
            system_exit_events.append(
                {"stage": "logout", "source": "result", "error": logout_result.error}
            )

        report["stages"]["after_logout"] = snapshot_worker_state(proxy)

        queue_events = collect_system_exit_events(proxy)
        if queue_events:
            system_exit_events.extend(tag_events("logout", queue_events, "queue"))

        report["stages"]["after_wait"] = await wait_for_process_exit(proxy, args.exit_wait)

        stats_after = report["stages"]["after_wait"].get("stats", {})
        last_crash: Optional[str] = None
        if isinstance(stats_after, dict):
            last_crash = stats_after.get("last_crash_reason")

        report["summary"] = build_summary(report, system_exit_events, last_crash)
        return report
    finally:
        try:
            await asyncio.to_thread(pool.stop, datasource_id, True, False)
        except Exception as exc:
            logger.warning(f"清理进程 {datasource_id} 失败: {exc}")


def main() -> None:
    args = parse_args()
    try:
        worker_env = parse_worker_env(args.worker_env)
    except ValueError as exc:
        print(f"参数错误: {exc}", file=sys.stderr)
        sys.exit(2)

    args.worker_env = worker_env
    configure_logger(args.log_level)

    try:
        report = asyncio.run(execute_probe(args))
    except KeyboardInterrupt:
        logger.warning("探测被手动终止")
        sys.exit(130)
    except Exception as exc:
        logger.exception(f"探测过程中出现异常: {exc}")
        sys.exit(1)

    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
