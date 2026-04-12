"""
DeepSearch 命令行接口

提供统一的命令行工具来管理和运行 DeepSearch 系统。
"""

import asyncio
import contextlib
import inspect
import io
import json
import os
import socket
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import click
from loguru import logger

# 延迟导入以避免循环依赖
__version__ = "0.1.0"

if TYPE_CHECKING:
    from core.config.models.amazingdata import AmazingDataConfig


@click.group()
@click.version_option(version=__version__, prog_name="DeepSearch")
def cli():
    """DeepSearch - 智能量化交易系统"""
    pass


@cli.command()
@click.argument("env", type=click.Choice(["dev", "prod"]), required=False, default="prod")
@click.option(
    "--mode", type=click.Choice(["full", "engine", "webui"]), default="full", help="运行模式"
)
@click.option("--config", type=click.Path(exists=True), help="配置文件路径")
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"]),
    default="INFO",
    help="日志级别",
)
@click.option("--no-frontend", is_flag=True, help="不启动前端（仅在full模式下有效）")
@click.option("--open-browser", is_flag=True, help="自动打开浏览器")
@click.option(
    "--status-display/--no-status-display",
    default=True,
    help="启用 Rich 终端状态显示（减少日志刷屏）",
)
@click.option(
    "--frontend-port", type=int, default=None, help="前端端口（仅 webui 模式，默认从配置读取）"
)
@click.option(
    "--backend-port", type=int, default=None, help="后端端口（仅 webui 模式，默认从配置读取）"
)
def run(
    env,
    mode,
    config,
    log_level,
    no_frontend,
    open_browser,
    status_display,
    frontend_port,
    backend_port,
):
    """运行 DeepSearch 系统

    ENV: 环境模式 (dev/prod)，默认为 prod

    示例:
      deepsearch run          # 生产模式
      deepsearch run dev      # 开发模式
      deepsearch run prod     # 生产模式（明确指定）
    """
    # 首先设置环境变量，在任何导入之前
    import os

    os.environ["APP__ENV"] = env

    # 现在可以安全地导入其他模块
    from core.config import get_config
    from core.core.runtime.async_runner import run_async_engine
    from core.observability.logger import logger_manager
    from core.utils.system.port_checker import PortChecker
    from core.utils.system.redis_startup import RedisStartupError, ensure_redis_running

    # 显示当前环境
    click.echo(f"启动环境: {env.upper()} (使用配置: settings.{env}.yaml)")
    click.echo("")

    # 设置日志级别
    logger_manager.set_level(log_level)
    logger_manager.start()

    # 加载配置
    if config:
        from core.config import config_manager

        config_manager.load(config)

    settings_obj = get_config()
    cache_config = getattr(settings_obj, "database", None)
    cache_config = cache_config.cache if cache_config else None

    try:
        ensure_redis_running(cache_config, echo=click.echo)
    except RedisStartupError as exc:
        click.echo(f"[ERROR] Redis 自检失败：{exc}")
        sys.exit(1)

    # 验证端口配置
    click.echo("检查端口配置...")
    if not PortChecker.validate_ports():
        click.echo("\n[ERROR] 无法启动系统：端口冲突")
        click.echo("请解决端口冲突后再启动服务。")
        sys.exit(1)

    click.echo("[OK] 端口检查通过\n")

    # 使用上下文管理器管理引擎生命周期
    if mode == "webui":
        # WebUI 模式：整合原 webui 命令的完整功能
        click.echo("启动 WebUI...")
        from apps.api.runner import run_standalone

        run_standalone(
            start_frontend=not no_frontend,
            frontend_port=frontend_port,
            backend_port=backend_port,
            auto_open_browser=open_browser,
            start_engine=True,
            infrastructure_only=True,
        )
    else:
        # 配置参数
        context_config = {"no_frontend": no_frontend, "open_browser": open_browser}

        click.echo(f"启动模式: {mode}")

        # 显示访问信息
        if mode == "full":
            app_config = settings_obj
            click.echo(f"WebUI API: http://localhost:{app_config.webui.backend_port}")

            # 如果是开发环境，显示 AmazingData 配置信息
            if env == "dev" and hasattr(app_config, "amazingdata") and app_config.amazingdata:
                ad = app_config.amazingdata
                if ad.enabled:
                    click.echo(
                        f"AmazingData: {ad.connection.host}:{ad.connection.port} (User: {ad.connection.username})"
                    )

            if no_frontend:
                click.echo(
                    "Note: Frontend needs to be started separately - cd apps/web && npm run dev"
                )

            if open_browser and not no_frontend:
                import webbrowser

                webbrowser.open(f"http://localhost:{app_config.webui.backend_port}")

        # 启动状态显示（如果启用）
        status_ctx = None
        if status_display:
            try:
                from core.core.utils.status_display import get_status_display

                status = get_status_display()
                status.enable(suppress_logs=False)
                status.start()
                status_ctx = status
                click.echo("[OK] Rich 状态显示已启用")
            except Exception as e:
                click.echo(f"[WARN] 状态显示启动失败: {e}")

        # 使用异步运行器
        click.echo("System running, press Ctrl+C to exit")
        try:
            run_async_engine(mode=mode, config=context_config)
        finally:
            if status_ctx:
                status_ctx.stop()
        click.echo("System closed")


@cli.command()
def check_ports():
    """检查端口配置和占用情况"""
    from core.utils.system.port_checker import check_and_report_ports

    check_and_report_ports()


@cli.command(name="check-realtime")
@click.option("--env", type=click.Choice(["dev", "test", "prod"]), help="指定 settings.<env>.yaml")
@click.option("--config", type=click.Path(exists=True), help="指定设置文件")
def check_realtime(env: str | None, config: str | None) -> None:
    """检测实时数据源 orchestrator 失效点"""

    if env:
        os.environ["APP__ENV"] = env

    if config:
        from core.config import config_manager

        config_manager.load(config)

    from core.application.market_data import RealtimeDataOrchestrator
    from core.config import get_config

    settings = get_config()
    orchestrator = RealtimeDataOrchestrator(settings)

    async def _run_probe() -> dict[str, dict[str, object]]:
        try:
            return await orchestrator.probe_adapters()
        finally:
            await orchestrator.shutdown()

    results = asyncio.run(_run_probe())
    click.echo("Realtime adapter status:")
    ok = True
    for name, info in results.items():
        status = info.get("status", "unknown")
        timestamp = info.get("timestamp")
        detail = info.get("error")
        line = f" - [{status}] {name}"
        if timestamp:
            line += f" @ {timestamp}"
        if detail:
            line += f" | {detail}"
        click.echo(line)
        if status != "healthy":
            ok = False

    if not ok:
        raise SystemExit(1)


@cli.command(name="check-amazingdata")
@click.argument("env", type=click.Choice(["dev", "prod"]), required=False, default="prod")
@click.option("--config", type=click.Path(exists=True), help="自定义配置文件路径")
@click.option(
    "--timeout", type=float, default=3.0, show_default=True, help="TCP 连通性检测超时时间（秒）"
)
@click.option(
    "--probe-calendar/--no-probe-calendar",
    default=False,
    show_default=True,
    help="执行一次真实 get_calendar 调用（非 mock）",
)
@click.option(
    "--probe-timeout",
    type=float,
    default=15.0,
    show_default=True,
    help="真实 get_calendar 调用超时时间（秒）",
)
@click.option(
    "--probe-market",
    type=str,
    default="SH",
    show_default=True,
    help="真实 get_calendar 调用市场参数",
)
@click.option(
    "--probe-data-type",
    type=click.Choice(["int", "str"]),
    default="int",
    show_default=True,
    help="真实 get_calendar 返回类型参数",
)
@click.option(
    "--suppress-third-party-output/--no-suppress-third-party-output",
    default=True,
    show_default=True,
    help="抑制第三方库直接写入终端的输出，保持诊断 JSON 可读性",
)
@click.option(
    "--safe-ascii-json/--raw-unicode-json",
    default=True,
    show_default=True,
    help="安全模式下将 JSON 转义为 ASCII，避免终端编码不一致导致乱码",
)
def check_amazingdata(
    env: str,
    config: str | None,
    timeout: float,
    probe_calendar: bool,
    probe_timeout: float,
    probe_market: str,
    probe_data_type: str,
    suppress_third_party_output: bool,
    safe_ascii_json: bool,
) -> None:
    """对 AmazingData 依赖进行基础自检"""

    import os

    def _ensure_utf8_streams() -> None:
        os.environ["PYTHONUTF8"] = "1"
        os.environ["PYTHONIOENCODING"] = "utf-8"
        for stream in (sys.stdout, sys.stderr):
            reconfigure = getattr(stream, "reconfigure", None)
            if callable(reconfigure):
                try:
                    reconfigure(encoding="utf-8", errors="replace")
                except Exception:
                    pass

    os.environ["APP__ENV"] = env
    os.environ["DEEPSEARCH_ENV"] = env
    _ensure_utf8_streams()

    results: dict[str, object] = {
        "environment": env,
        "status": "failed",
        "checks": [],
    }

    def _emit_results() -> None:
        click.echo(
            json.dumps(
                results,
                ensure_ascii=bool(safe_ascii_json),
                indent=2,
            )
        )

    def add_check(name: str, status: str, detail: str, suggestion: str | None = None) -> None:
        entry: dict[str, object] = {"name": name, "status": status, "detail": detail}
        if suggestion:
            entry["suggestion"] = suggestion
        checks: list[dict[str, object]] = results.setdefault("checks", [])  # type: ignore[assignment]
        checks.append(entry)

    def aggregate_status() -> str:
        checks = results.get("checks", [])
        if not isinstance(checks, list):
            return "failed"

        statuses = {
            str(item.get("status", "")).lower() for item in checks if isinstance(item, dict)
        }
        if "failed" in statuses:
            return "failed"
        if "warning" in statuses:
            return "warning"
        if "ok" in statuses:
            return "ok"
        return "failed"

    def _read_tail_lines(file_path: Path, max_bytes: int = 4096, max_lines: int = 10) -> list[str]:
        try:
            size = file_path.stat().st_size
            with file_path.open("rb") as fh:
                if size > max_bytes:
                    fh.seek(size - max_bytes)
                data = fh.read()

            try:
                text = data.decode("utf-8")
            except UnicodeDecodeError:
                text = data.decode("gbk", errors="ignore")

            lines = [line for line in text.splitlines() if line.strip()]
            return lines[-max_lines:]
        except Exception as exc:  # pragma: no cover - 文件读取异常
            return [f"(读取日志失败: {exc})"]

    def _to_dict(value: object) -> dict[str, object]:
        if value is None:
            return {}
        if isinstance(value, dict):
            return dict(value)
        if hasattr(value, "model_dump"):
            try:
                dumped = value.model_dump()
                if isinstance(dumped, dict):
                    return dict(dumped)
            except Exception:
                return {}
        if hasattr(value, "__dict__"):
            return dict(getattr(value, "__dict__", {}))
        return {}

    def _get_static_callable(target: object, method_name: str):
        try:
            inspect.getattr_static(target, method_name)
        except AttributeError:
            return None

        callback = getattr(target, method_name, None)
        if not callable(callback):
            return None
        return callback

    async def _cleanup_provider(provider_obj: object) -> None:
        cleanup_timeout = 10.0
        for method_name in ("stop_async", "shutdown", "stop", "cleanup", "close"):
            callback = _get_static_callable(provider_obj, method_name)
            if not callable(callback):
                continue
            try:
                result = callback()
                if inspect.isawaitable(result):
                    await asyncio.wait_for(result, timeout=cleanup_timeout)
            except Exception:
                pass
            break

    def _resolve_amazingdata_config(
        settings_obj: object,
    ) -> tuple["AmazingDataConfig | None", str | None]:
        from core.config.models.amazingdata import AmazingDataConfig

        # 兼容旧配置：settings.amazingdata
        direct_config = getattr(settings_obj, "amazingdata", None)
        if isinstance(direct_config, AmazingDataConfig):
            return direct_config, "settings.amazingdata"

        # 兼容新配置：settings.data_sources.providers.amazingdata
        data_sources_obj = getattr(settings_obj, "data_sources", None)
        data_sources_dict = _to_dict(data_sources_obj)
        providers = _to_dict(data_sources_dict.get("providers"))
        provider_entry_obj = providers.get("amazingdata")
        provider_entry = _to_dict(provider_entry_obj)
        if not provider_entry:
            return None, None

        from core.config.models.amazingdata import AmazingDataConfig as SettingsAmazingDataConfig

        provider_config = _to_dict(provider_entry.get("config"))
        for key in (
            "enabled",
            "priority",
            "mode",
            "dask_scheduler_address",
            "implementation_mode",
            "prewarm",
            "worker_env",
        ):
            if key in provider_entry and key not in provider_config:
                provider_config[key] = provider_entry[key]

        if "enabled" not in provider_config:
            provider_config["enabled"] = bool(provider_entry.get("enabled", False))

        # 兼容偶发的扁平配置，尽量构造 connection 字段
        if "connection" not in provider_config:
            connection_payload: dict[str, object] = {}
            for key in (
                "username",
                "password",
                "host",
                "port",
                "timeout",
                "max_retries",
                "heartbeat_interval",
                "auto_reconnect",
                "python_interpreter_path",
                "tgw_log_path",
            ):
                if key in provider_entry:
                    connection_payload[key] = provider_entry[key]
            if connection_payload:
                provider_config["connection"] = connection_payload

        resolved = SettingsAmazingDataConfig.model_validate(provider_config)
        return (resolved, "settings.data_sources.providers.amazingdata")

    def _check_worker_backconnect_from_scheduler(
        dask_client: object,
        worker_addresses: list[str],
        timeout_seconds: float,
    ) -> dict[str, dict[str, object]]:
        if not worker_addresses:
            return {}

        def _probe(
            dask_scheduler=None,  # noqa: ARG001 - distributed 注入
            worker_addresses: list[str] | None = None,
            timeout_seconds: float = 2.0,
        ):
            import socket as _socket

            results: dict[str, dict[str, object]] = {}
            for raw_addr in worker_addresses or []:
                addr_text = str(raw_addr)
                result: dict[str, object] = {"reachable": False, "error": "", "host": "", "port": 0}
                try:
                    endpoint = addr_text.strip()
                    if "://" in endpoint:
                        endpoint = endpoint.split("://", 1)[1]

                    if endpoint.startswith("[") and "]:" in endpoint:
                        host, port_text = endpoint[1:].rsplit("]:", 1)
                    else:
                        host, port_text = endpoint.rsplit(":", 1)
                    port = int(port_text)

                    result["host"] = host
                    result["port"] = port
                    with _socket.create_connection(
                        (host, port),
                        timeout=max(0.5, float(timeout_seconds)),
                    ):
                        result["reachable"] = True
                except Exception as exc:  # pragma: no cover - scheduler 环境执行
                    result["error"] = f"{exc.__class__.__name__}: {exc}"

                results[addr_text] = result
            return results

        run_on_scheduler = getattr(dask_client, "run_on_scheduler", None)
        if not callable(run_on_scheduler):
            raise RuntimeError("当前 Dask Client 不支持 run_on_scheduler，无法执行回连检查")

        raw_result = run_on_scheduler(
            _probe,
            worker_addresses=worker_addresses,
            timeout_seconds=max(1.0, float(timeout_seconds)),
        )
        if not isinstance(raw_result, dict):
            raise RuntimeError(f"回连检查返回类型异常: {type(raw_result).__name__}")
        return raw_result

    def _windows_worker_autostart_enabled(settings_obj: object) -> bool:
        dask_config = getattr(settings_obj, "dask", None)
        windows_workers = getattr(dask_config, "windows_workers", None) if dask_config else None
        if windows_workers is None:
            return False
        return bool(
            getattr(windows_workers, "enabled", False)
            and getattr(windows_workers, "auto_start", False)
        )

    def _try_autostart_windows_workers(start_timeout: float = 45.0) -> tuple[bool, str]:
        async def _run_start() -> bool:
            from core.compute.dask_worker_manager import ensure_windows_workers

            return await asyncio.wait_for(ensure_windows_workers(), timeout=start_timeout)

        try:
            started = asyncio.run(_run_start())
            if started:
                return True, ""
            return False, "ensure_windows_workers() 返回 False"
        except Exception as exc:  # pragma: no cover - 依赖环境差异
            return False, str(exc)

    def _collect_dask_version_mismatches(dask_client: object) -> list[str]:
        get_versions = getattr(dask_client, "get_versions", None)
        if not callable(get_versions):
            return []

        try:
            versions = get_versions(check=False)
        except TypeError:
            versions = get_versions()
        except Exception:
            return []

        if not isinstance(versions, dict):
            return []

        scheduler_section = versions.get("scheduler", {})
        client_section = versions.get("client", {})
        scheduler_packages = (
            scheduler_section.get("packages", {}) if isinstance(scheduler_section, dict) else {}
        )
        client_packages = (
            client_section.get("packages", {}) if isinstance(client_section, dict) else {}
        )
        if not isinstance(scheduler_packages, dict) or not isinstance(client_packages, dict):
            return []

        mismatches: list[str] = []
        for package_name in ("dask", "distributed"):
            scheduler_ver = scheduler_packages.get(package_name)
            client_ver = client_packages.get(package_name)
            if scheduler_ver and client_ver and str(scheduler_ver) != str(client_ver):
                mismatches.append(f"{package_name}: client={client_ver}, scheduler={scheduler_ver}")
        return mismatches

    def _extract_endpoint_host(endpoint: str) -> str:
        endpoint_text = str(endpoint).strip()
        if "://" in endpoint_text:
            endpoint_text = endpoint_text.split("://", 1)[1]
        if endpoint_text.startswith("[") and "]:" in endpoint_text:
            host, _ = endpoint_text[1:].rsplit("]:", 1)
            return host.strip().lower()
        if ":" in endpoint_text:
            host, _ = endpoint_text.rsplit(":", 1)
            return host.strip().lower()
        return endpoint_text.strip().lower()

    def _is_loopback_host(host: str) -> bool:
        normalized = str(host).strip().lower()
        return normalized in {"localhost", "127.0.0.1", "::1"}

    try:
        if config:
            from core.config import config_manager

            # ConfigManager.env setter 会触发 reload()；在未设置 config_path 时会产生无效告警。
            # 这里仅同步运行环境，不触发 reload，随后直接 load(config)。
            if getattr(config_manager, "env", None) != env:
                setattr(config_manager, "_env", env)
            config_manager.load(config)
            add_check("加载自定义配置", "ok", f"已加载 {config}")
    except Exception as exc:  # pragma: no cover - 配置解析异常
        add_check("加载自定义配置", "failed", f"读取配置失败：{exc}")
        _emit_results()
        raise SystemExit(1)

    try:
        from core.config import get_config

        settings = get_config()
        add_check("配置文件加载", "ok", "Settings 实例化成功")
    except Exception as exc:
        add_check(
            "配置文件加载",
            "failed",
            f"无法实例化 Settings：{exc}",
            "请确认 settings.<env>.yaml 是否存在且字段填写完整",
        )
        _emit_results()
        raise SystemExit(1)

    try:
        amazingdata_config, config_source = _resolve_amazingdata_config(settings)
    except Exception as exc:
        add_check(
            "AmazingData 配置",
            "failed",
            f"AmazingData 配置解析失败：{exc}",
            "请检查 settings.<env>.yaml 中 amazingdata 或 data_sources.providers.amazingdata 配置",
        )
        _emit_results()
        raise SystemExit(1)

    if not amazingdata_config:
        add_check(
            "AmazingData 配置",
            "failed",
            "未找到 amazingdata 配置段",
            "请参考 settings.template.yaml，补充 amazingdata 或 data_sources.providers.amazingdata 配置后重试",
        )
        _emit_results()
        raise SystemExit(1)

    if config_source:
        add_check("AmazingData 配置来源", "ok", f"检测到 {config_source}")

    if not getattr(amazingdata_config, "enabled", False):
        add_check(
            "AmazingData 启用状态",
            "warning",
            "amazingdata.enabled 当前为 false，跳过连通性检测",
            "如需启用 AmazingData，请在配置中将 enabled 设置为 true",
        )
        results["status"] = aggregate_status()
        _emit_results()
        raise SystemExit(0)

    try:
        amazingdata_config.ensure_connection_ready()
        add_check("连接配置校验", "ok", "用户名/密码/主机/端口校验通过")
    except ValueError as exc:
        add_check(
            "连接配置校验",
            "failed",
            f"配置不符合要求：{exc}",
            "请更新 settings.<env>.yaml 中的 amazingdata.connection 字段",
        )
        _emit_results()
        raise SystemExit(1)

    log_path_value = getattr(amazingdata_config.connection, "tgw_log_path", "") or getattr(
        amazingdata_config, "tgw_log_path", ""
    )

    if not log_path_value:
        add_check(
            "TGW 日志配置",
            "warning",
            "未配置 tgw_log_path，无法自动抓取 TGW 日志",
            "在 amazingdata.connection.tgw_log_path 中填写日志目录或文件路径",
        )
    else:
        log_path = Path(log_path_value).expanduser()
        if not log_path.exists():
            add_check(
                "TGW 日志配置",
                "failed",
                f"指定的日志路径不存在：{log_path}",
                "确认 TGW 是否已生成日志，并检查运行账号的访问权限",
            )
        else:
            target: Path
            if log_path.is_dir():
                candidates = [p for p in log_path.glob("*.log") if p.is_file()]
                if not candidates:
                    add_check(
                        "TGW 日志检查",
                        "warning",
                        f"目录 {log_path} 中未发现 *.log 文件",
                        "确认 TGW 是否已开始写入日志",
                    )
                else:
                    target = max(candidates, key=lambda p: p.stat().st_mtime)
                    snippet = "\n".join(_read_tail_lines(target)) or "(日志为空)"
                    add_check(
                        "TGW 日志检查",
                        "ok",
                        f"最近日志文件 {target.name}：\n{snippet}",
                        f"完整路径：{target}",
                    )
            else:
                target = log_path
                snippet = "\n".join(_read_tail_lines(target)) or "(日志为空)"
                add_check(
                    "TGW 日志检查",
                    "ok",
                    f"已读取日志文件 {target}：\n{snippet}",
                )

    host = amazingdata_config.connection.host
    port = amazingdata_config.connection.port

    try:
        with socket.create_connection((host, port), timeout=timeout):
            pass
        add_check("TCP 连通性", "ok", f"成功连接 {host}:{port}")
    except OSError as exc:
        add_check(
            "TCP 连通性",
            "failed",
            f"无法连接 {host}:{port}：{exc}",
            "请确认网络连通性、防火墙及服务端监听状态",
        )
        _emit_results()
        raise SystemExit(1)

    mode = str(getattr(amazingdata_config, "mode", "local") or "local").lower()
    scheduler_address = getattr(amazingdata_config, "dask_scheduler_address", None)
    probe_skip_reason: str | None = None
    probe_skip_suggestion: str | None = None
    worker_bootstrap_command = (
        '`uv run --python ./.venv/Scripts/python.exe python -c "import asyncio; '
        "from core.compute.dask_worker_manager import ensure_windows_workers; "
        'print(asyncio.run(ensure_windows_workers()))"`'
    )

    if mode == "distributed":
        if not scheduler_address:
            probe_skip_reason = "distributed 模式缺少 dask_scheduler_address"
            probe_skip_suggestion = (
                "请在 AmazingData 配置中补充 dask_scheduler_address；"
                "修复后重试 `deepsearch check-amazingdata dev --probe-calendar`"
            )
            add_check(
                "Dask Worker 可用性",
                "failed",
                "distributed 模式缺少 dask_scheduler_address",
                "请在 AmazingData 配置中补充 dask_scheduler_address",
            )
        else:
            try:
                from distributed import Client

                with Client(
                    str(scheduler_address),
                    timeout=f"{max(timeout, 3.0)}s",
                    set_as_default=False,
                ) as client:
                    scheduler_info = client.scheduler_info() or {}
                    workers = scheduler_info.get("workers", {}) or {}
                    version_mismatches = _collect_dask_version_mismatches(client)
                    if version_mismatches:
                        add_check(
                            "Dask 版本一致性",
                            "warning",
                            "检测到 client/scheduler 版本不一致: " + "; ".join(version_mismatches),
                            "建议对齐 dask/distributed 版本后重启 Scheduler 和 Worker",
                        )
                    else:
                        add_check("Dask 版本一致性", "ok", "client/scheduler 版本一致")

                    if not workers:
                        auto_start_attempted = False
                        if _windows_worker_autostart_enabled(settings):
                            auto_start_attempted = True
                            started, reason = _try_autostart_windows_workers()
                            if started:
                                time.sleep(1.0)
                                scheduler_info = client.scheduler_info() or {}
                                workers = scheduler_info.get("workers", {}) or {}
                                add_check(
                                    "Dask Worker 自动拉起",
                                    "ok",
                                    f"已触发自动拉起，当前 Worker 数: {len(workers)}",
                                )
                            else:
                                add_check(
                                    "Dask Worker 自动拉起",
                                    "warning",
                                    f"自动拉起失败: {reason}",
                                    "请检查本机 Python 环境、端口占用与 Worker 启动日志",
                                )

                        if auto_start_attempted and workers:
                            pass
                        else:
                            suggestion = "请先启动至少一个 Dask Worker"
                            if _windows_worker_autostart_enabled(settings):
                                suggestion += f"（也可执行 {worker_bootstrap_command}）"
                            probe_skip_reason = "Scheduler 在线但无可用 Worker"
                            probe_skip_suggestion = f"{suggestion}；修复后重试 `deepsearch check-amazingdata dev --probe-calendar`"
                            add_check(
                                "Dask Worker 可用性",
                                "failed",
                                f"Scheduler {scheduler_address} 在线但无可用 Worker",
                                suggestion,
                            )
                    if workers:
                        win_workers = [
                            addr
                            for addr, info in workers.items()
                            if isinstance(info, dict)
                            and isinstance(info.get("resources"), dict)
                            and info["resources"].get("WIN", 0) > 0
                        ]

                        if not win_workers:
                            probe_skip_reason = (
                                f"Scheduler {scheduler_address} 已连接，但无 WIN 资源 Worker"
                            )
                            probe_skip_suggestion = (
                                "请先启动至少一个 resources.WIN > 0 的 Worker，"
                                f"例如执行 {worker_bootstrap_command}；"
                                "修复后重试 `deepsearch check-amazingdata dev --probe-calendar`"
                            )
                            add_check(
                                "Dask Worker 可用性",
                                "failed",
                                f"Scheduler {scheduler_address} 已连接，但无 WIN 资源 Worker（共 {len(workers)} 个）",
                                "Windows 任务需要至少一个 resources.WIN > 0 的 Worker",
                            )
                        else:
                            add_check(
                                "Dask Worker 可用性",
                                "ok",
                                f"可用 Worker: {len(workers)} 个，WIN 资源 Worker: {len(win_workers)} 个",
                            )

                            scheduler_runtime_address = str(
                                scheduler_info.get("address") or scheduler_address
                            )
                            scheduler_runtime_host = _extract_endpoint_host(
                                scheduler_runtime_address
                            )
                            loopback_win_workers = [
                                str(addr)
                                for addr in win_workers
                                if _is_loopback_host(_extract_endpoint_host(str(addr)))
                            ]

                            if loopback_win_workers and not _is_loopback_host(
                                scheduler_runtime_host
                            ):
                                add_check(
                                    "Scheduler 到 Worker 回连",
                                    "failed",
                                    (
                                        f"检测到 Scheduler({scheduler_runtime_address}) 与 WIN Worker "
                                        f"联系地址不兼容（loopback）: {loopback_win_workers[:3]}"
                                    ),
                                    "请将 Worker contact-address 配置为可被 Scheduler 回连的宿主机地址（如 host.docker.internal 或宿主机网卡 IP）",
                                )
                            else:
                                try:
                                    backconnect = _check_worker_backconnect_from_scheduler(
                                        client,
                                        worker_addresses=[str(addr) for addr in win_workers],
                                        timeout_seconds=max(1.0, float(timeout)),
                                    )
                                    reachable_workers = [
                                        addr
                                        for addr, info in backconnect.items()
                                        if isinstance(info, dict) and bool(info.get("reachable"))
                                    ]
                                    unreachable_workers = [
                                        addr
                                        for addr, info in backconnect.items()
                                        if not (
                                            isinstance(info, dict) and bool(info.get("reachable"))
                                        )
                                    ]

                                    if not reachable_workers:
                                        details: list[str] = []
                                        for addr in unreachable_workers[:3]:
                                            info = backconnect.get(addr, {})
                                            error = (
                                                str(info.get("error", "未知错误"))
                                                if isinstance(info, dict)
                                                else "未知错误"
                                            )
                                            details.append(f"{addr} -> {error}")
                                        detail_text = (
                                            "；".join(details)
                                            if details
                                            else "所有 WIN Worker 均不可回连"
                                        )
                                        add_check(
                                            "Scheduler 到 Worker 回连",
                                            "failed",
                                            f"未发现可回连 WIN Worker（共 {len(win_workers)} 个）：{detail_text}",
                                            "请检查 Worker --host 地址与 Docker 网络可达性，避免落到 Default Switch 网段",
                                        )
                                    elif unreachable_workers:
                                        add_check(
                                            "Scheduler 到 Worker 回连",
                                            "warning",
                                            (
                                                f"可回连 WIN Worker: {len(reachable_workers)}/{len(win_workers)}；"
                                                f"不可回连: {unreachable_workers[:3]}"
                                            ),
                                            "建议固定 Worker --host 到容器可回连地址，降低 gather 超时风险",
                                        )
                                    else:
                                        add_check(
                                            "Scheduler 到 Worker 回连",
                                            "ok",
                                            f"WIN Worker 全部可回连（{len(win_workers)} 个）",
                                        )
                                except Exception as exc:
                                    add_check(
                                        "Scheduler 到 Worker 回连",
                                        "warning",
                                        f"回连预检查执行失败：{exc}",
                                        "若后续出现 Actor 超时，请重点检查 Worker 地址与容器网络",
                                    )
            except Exception as exc:  # pragma: no cover - 依赖环境差异
                probe_skip_reason = f"无法连接 Dask Scheduler {scheduler_address}: {exc}"
                probe_skip_suggestion = (
                    "请确认 Scheduler/Worker 正常运行且地址可达；"
                    "修复后重试 `deepsearch check-amazingdata dev --probe-calendar`"
                )
                add_check(
                    "Dask Worker 可用性",
                    "failed",
                    f"无法连接 Dask Scheduler {scheduler_address}: {exc}",
                    "请确认 Scheduler/Worker 正常运行且地址可达",
                )

    if probe_calendar:
        if mode == "distributed" and probe_skip_reason:
            add_check(
                "真实 API Smoke",
                "warning",
                f"未执行 get_calendar 探测：{probe_skip_reason}",
                probe_skip_suggestion,
            )
        else:
            try:
                from core.infrastructure.providers.integration.compat import get_provider_compat

                async def _run_calendar_probe(provider_obj: object) -> object:
                    calendar_method = getattr(provider_obj, "get_calendar", None)
                    if not callable(calendar_method):
                        raise RuntimeError("Provider 不支持 get_calendar 接口")

                    def _resolve_effective_timeout() -> float:
                        # 严格遵循用户传入的 probe_timeout，避免巡检命令长时间阻塞。
                        return max(1.0, float(probe_timeout))

                    async def _invoke_static_lifecycle(method_name: str) -> object | None:
                        callback = _get_static_callable(provider_obj, method_name)
                        if callback is None:
                            return None

                        result = callback()
                        if inspect.isawaitable(result):
                            return await asyncio.wait_for(
                                result,
                                timeout=max(5.0, float(probe_timeout)),
                            )
                        return result

                    init_result = await _invoke_static_lifecycle("initialize")
                    if init_result is False:
                        raise RuntimeError("Provider initialize() 返回 False")

                    actor_obj = getattr(provider_obj, "_actor", None)
                    actor_call = getattr(actor_obj, "call", None)
                    if callable(actor_call):
                        actor_result = await asyncio.wait_for(
                            actor_call(
                                "get_calendar", data_type=probe_data_type, market=probe_market
                            ),
                            timeout=_resolve_effective_timeout(),
                        )
                        if actor_result is None:
                            return []
                        if isinstance(actor_result, list):
                            normalized: list[int] = []
                            for item in actor_result:
                                try:
                                    normalized.append(int(item))
                                except TypeError, ValueError:
                                    continue
                            return normalized
                        return actor_result

                    invocation_errors: list[str] = []
                    candidate_result: object | None = None
                    invoked = False
                    for invoke in (
                        lambda: calendar_method(data_type=probe_data_type, market=probe_market),
                        lambda: calendar_method(market=probe_market),
                        lambda: calendar_method(probe_data_type, probe_market),
                        lambda: calendar_method(),
                    ):
                        try:
                            candidate_result = invoke()
                            invoked = True
                            break
                        except TypeError as exc:
                            invocation_errors.append(str(exc))

                    if not invoked:
                        raise RuntimeError(
                            "get_calendar 参数适配失败: "
                            + " | ".join(invocation_errors[-2:] or ["未知参数错误"])
                        )

                    if inspect.isawaitable(candidate_result):
                        return await asyncio.wait_for(
                            candidate_result,
                            timeout=_resolve_effective_timeout(),
                        )
                    return candidate_result

                async def _run_probe_flow() -> object:
                    provider_obj: object | None = None
                    try:
                        provider_obj = await asyncio.wait_for(
                            get_provider_compat("amazingdata"),
                            timeout=max(1.0, float(probe_timeout)),
                        )
                        if provider_obj is None:
                            raise RuntimeError("无法创建 amazingdata Provider 实例")

                        return await _run_calendar_probe(provider_obj)
                    finally:
                        if provider_obj is not None:
                            await _cleanup_provider(provider_obj)
                        try:
                            from core.compute import close_dask_client

                            await asyncio.wait_for(close_dask_client(), timeout=5.0)
                        except Exception:
                            pass

                if suppress_third_party_output:
                    with (
                        contextlib.redirect_stdout(io.StringIO()),
                        contextlib.redirect_stderr(io.StringIO()),
                    ):
                        calendar_result = asyncio.run(_run_probe_flow())
                else:
                    calendar_result = asyncio.run(_run_probe_flow())

                if isinstance(calendar_result, list):
                    if calendar_result:
                        preview = calendar_result[:3]
                        add_check(
                            "真实 API Smoke",
                            "ok",
                            f"get_calendar 成功，返回 {len(calendar_result)} 条，样例: {preview}",
                        )
                    else:
                        add_check(
                            "真实 API Smoke",
                            "warning",
                            "get_calendar 调用成功但返回空列表",
                            "请检查交易日历数据是否完整同步",
                        )
                else:
                    add_check(
                        "真实 API Smoke",
                        "warning",
                        f"get_calendar 返回非列表类型: {type(calendar_result).__name__}",
                        "请确认 Provider 接口返回结构是否符合预期",
                    )
            except Exception as exc:
                error_text = str(exc).strip() or exc.__class__.__name__
                error_text_lower = error_text.lower()
                if isinstance(exc, asyncio.TimeoutError):
                    add_check(
                        "真实 API Smoke",
                        "warning",
                        "get_calendar 调用超时（可能为瞬时抖动）",
                        "建议重试；若持续超时，请检查 Worker 负载、Dask 链路与 Actor 状态",
                    )
                elif "unable to contact actor's worker" in error_text_lower:
                    add_check(
                        "真实 API Smoke",
                        "failed",
                        f"get_calendar 调用失败: {error_text}",
                        "Actor 所在 Worker 不可达，请优先检查 Worker --host 地址与 Scheduler 到 Worker 回连链路",
                    )
                elif (
                    "deserialization of the task graph" in error_text_lower
                    or "different environments" in error_text_lower
                    or "no module named" in error_text_lower
                ):
                    add_check(
                        "真实 API Smoke",
                        "failed",
                        f"get_calendar 调用失败: {error_text}",
                        "检测到 Dask 环境不一致，请重建 deepsearch-dask 镜像并重启 scheduler/worker",
                    )
                else:
                    add_check(
                        "真实 API Smoke",
                        "failed",
                        f"get_calendar 调用失败: {error_text}",
                        "请检查 Dask Worker、Redis 连接和 AmazingData 会话状态",
                    )

    _ensure_utf8_streams()
    results["status"] = aggregate_status()
    _emit_results()
    raise SystemExit(1 if results["status"] == "failed" else 0)


@cli.command()
@click.argument("component", type=click.Choice(["gateway", "trader", "strategy", "all"]))
def start(component):
    """启动指定组件"""
    from core.core.runtime.engine_context import EngineContext

    click.echo(f"启动组件: {component}")

    # 使用上下文管理器
    with EngineContext(mode="engine") as engine:
        try:
            if component == "all":
                # 启动所有业务组件
                engine.start()
            else:
                # 启动特定组件
                engine.start_component(component)

            # 主循环
            while engine.is_running():
                time.sleep(1)

        except KeyboardInterrupt:
            click.echo("\n正在关闭...")


@cli.command()
@click.argument("component", type=click.Choice(["gateway", "trader", "strategy", "all"]))
def stop(component):
    """停止指定组件"""
    from core.core.managers.component_manager import ComponentManager
    from core.core.runtime.engine import MainEngine

    try:
        # 获取组件管理器实例
        component_manager = ComponentManager()

        if component == "all":
            click.echo("停止所有组件...")
            # 创建引擎实例来停止所有组件
            engine = MainEngine()
            engine.stop()
            click.echo("[OK] 所有组件已停止")
        else:
            # 停止特定组件
            component_map = {"gateway": "gateway", "trader": "trader", "strategy": "strategy"}

            component_name = component_map.get(component)
            if component_name:
                click.echo(f"停止组件: {component}")
                if component_manager.stop_component(component_name):
                    click.echo(f"[OK] {component} 已停止")
                else:
                    click.echo(f"[ERROR] 无法停止 {component}")
            else:
                click.echo(f"[ERROR] 未知组件: {component}")
    except Exception as e:
        click.echo(f"[ERROR] 停止组件失败: {e}")


@cli.command()
def status():
    """查看系统状态"""
    import psutil
    from core.core.managers.component_manager import ComponentManager

    click.echo("系统状态:")

    try:
        # 获取组件管理器实例
        component_manager = ComponentManager()

        # 检查各组件状态
        components = component_manager.get_all_components_status()

        if not components:
            click.echo("  没有已注册的组件")
        else:
            for name, info in components.items():
                # info 是 ComponentInfo 对象
                status = info.status.value if hasattr(info, "status") else "UNKNOWN"
                status_color = "green" if status == "running" else "red"
                click.echo(f"  - {name}: ", nl=False)
                click.secho(status.upper(), fg=status_color)

        # 检查端口占用情况
        click.echo("\n端口占用情况:")
        ports_to_check = {
            8000: "WebUI Backend",
            3000: "WebUI Frontend",
            5672: "RabbitMQ",
        }

        for port, service in ports_to_check.items():
            in_use = False
            for conn in psutil.net_connections():
                if conn.laddr.port == port and conn.status == "LISTEN":
                    in_use = True
                    break

            status = "占用" if in_use else "空闲"
            color = "red" if in_use else "green"
            click.echo(f"  - {service} (:{port}): ", nl=False)
            click.secho(status, fg=color)

    except Exception as e:
        click.echo(f"[ERROR] 获取状态失败: {e}")


@cli.command()
@click.option("--all", is_flag=True, help="清理所有端口和进程")
@click.option("--force", is_flag=True, help="强制清理")
def cleanup(all, force):
    """清理占用的端口和进程"""
    click.echo("清理占用的端口和进程...")

    from core.core.managers.process_manager import process_manager

    # 显示当前状态
    status = process_manager.get_status()
    active_count = len(status["active_resources"])

    if active_count > 0:
        click.echo(f"\n发现 {active_count} 个活跃资源:")
        for resource in status["active_resources"]:
            click.echo(f"  - {resource['type']}: {resource['name']}")

    # 执行清理
    click.echo("\n开始清理...")
    process_manager.shutdown(timeout=10.0, force=force)

    # 额外的端口清理
    if all:
        import psutil
        from core.config import get_config

        config = get_config()

        ports_to_clean = [config.webui.backend_port, config.webui.frontend_port]

        # 添加 RabbitMQ 端口（如果配置存在）
        if "rabbitmq" in config.message_bus.buses:
            rabbitmq_config = config.message_bus.buses["rabbitmq"].config
            if hasattr(rabbitmq_config, "port"):
                ports_to_clean.append(rabbitmq_config.port)
            elif isinstance(rabbitmq_config, dict):
                ports_to_clean.append(rabbitmq_config.get("port", 5672))

        cleaned = 0
        for conn in psutil.net_connections():
            if hasattr(conn, "laddr") and conn.laddr and conn.laddr.port in ports_to_clean:
                if conn.status == "LISTEN" or force:
                    try:
                        proc = psutil.Process(conn.pid)
                        click.echo(f"  清理端口 {conn.laddr.port} (PID={conn.pid}, {proc.name()})")

                        # Windows特殊处理
                        import platform

                        if platform.system() == "Windows":
                            # 在Windows上，先尝试terminate，不行就直接kill
                            try:
                                proc.terminate()
                                proc.wait(timeout=1)
                            except Exception:
                                proc.kill()
                        else:
                            proc.terminate()
                            proc.wait(timeout=3)

                        cleaned += 1
                    except psutil.NoSuchProcess:
                        # 进程已经不存在
                        pass
                    except psutil.AccessDenied:
                        if force:
                            # 尝试使用系统命令强制终止
                            import subprocess

                            if platform.system() == "Windows":
                                try:
                                    subprocess.run(
                                        ["taskkill", "/F", "/PID", str(conn.pid)],
                                        capture_output=True,
                                        check=False,
                                    )
                                    cleaned += 1
                                    click.echo(f"    强制终止进程 {conn.pid}")
                                except Exception:
                                    click.echo(f"    无法终止进程 {conn.pid} (权限不足)")
                    except Exception as e:
                        logger.debug(f"Failed to kill process {conn.pid}: {e}")

        if cleaned > 0:
            click.echo(f"\n[OK] 清理了 {cleaned} 个进程")

    click.echo("\n[OK] 清理完成")


@cli.command()
def diagnose():
    """诊断系统资源状态"""
    import json

    from core.core.managers.process_manager import process_manager

    click.echo("系统资源诊断\n")

    # 获取状态
    status = process_manager.get_status()

    # 显示概览
    click.echo("资源概览:")
    click.echo(f"  总资源数: {status['total_resources']}")
    click.echo(f"  关闭中: {'是' if status['shutting_down'] else '否'}")

    # 按类型统计
    click.echo("\n按类型统计:")
    for rtype, count in status["resources_by_type"].items():
        if count > 0:
            click.echo(f"  {rtype}: {count}")

    # 按状态统计
    click.echo("\n按状态统计:")
    for rstatus, count in status["resources_by_status"].items():
        if count > 0:
            click.echo(f"  {rstatus}: {count}")

    # 活跃资源详情
    if status["active_resources"]:
        click.echo("\n活跃资源详情:")
        for resource in status["active_resources"]:
            click.echo(f"\n  [{resource['type']}] {resource['name']}")
            click.echo(f"    ID: {resource['id']}")
            click.echo(f"    状态: {resource['status']}")
            click.echo(f"    创建时间: {resource['created_at']}")

    # 检查潜在问题
    click.echo("\n潜在问题检查:")
    issues = []

    # 检查僵尸线程
    if status["resources_by_status"].get("running", 0) > 10:
        issues.append("发现过多运行中的资源，可能存在资源泄露")

    # 检查失败的资源
    if status["resources_by_status"].get("failed", 0) > 0:
        issues.append(f"有 {status['resources_by_status']['failed']} 个资源处于失败状态")

    if issues:
        for issue in issues:
            click.secho(f"  ⚠ {issue}", fg="yellow")
    else:
        click.secho("  ✓ 未发现明显问题", fg="green")

    # 导出详细信息
    if click.confirm("\n是否导出详细诊断信息到文件？"):
        filename = f"deepsearch-diagnose-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(status, f, indent=2, ensure_ascii=False)
        click.echo(f"\n诊断信息已保存到: {filename}")


@cli.command()
@click.option("--output", type=click.Path(), default="config.yaml", help="输出文件路径")
def init(output):
    """初始化配置文件"""
    click.echo(f"生成配置文件: {output}")

    from pathlib import Path

    import yaml
    from core.config import settings

    # 检查文件是否已存在
    output_path = Path(output)
    if output_path.exists():
        if not click.confirm(f"文件 {output} 已存在，是否覆盖？"):
            click.echo("[CANCELLED] 操作已取消")
            return

    # 基于当前配置生成模板
    config_template = {
        "app": {
            "name": settings.app.name,
            "author": settings.app.author,
            "version": settings.app.version,
            "debug": False,
        },
        "log": {
            "active": True,
            "level": "INFO",
            "rotation": "00:00",
            "retention_days": 7,
            "json": False,
        },
        "webui": {
            "backend_host": "127.0.0.1",
            "backend_port": 8000,
            "frontend_port": 3000,
            "auto_open_browser": True,
        },
        "message_bus": {
            "buses": {
                "rabbitmq": {
                    "type": "rabbitmq",
                    "config": {"host": "localhost", "port": 5672, "exchange": "deepsearch.events"},
                }
            }
        },
        "monitoring": {"enabled": True, "metrics_interval": 60, "health_check_interval": 30},
        "database": {"main": {"url": "sqlite:///deepsearch.db", "echo": False}},
    }

    # 写入配置文件
    with open(output, "w", encoding="utf-8") as f:
        yaml.dump(config_template, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    click.echo(f"[OK] 配置文件已生成: {output}")
    click.echo("\n提示：")
    click.echo("  1. 请根据实际需求修改配置文件")
    click.echo("  2. 使用 'deepsearch run --config <file>' 指定配置文件运行")


@cli.group()
def config():
    """配置管理"""
    pass


# 添加调试命令组（仅在开发模式下可用）
try:
    from core.cli.debug_commands import debug

    cli.add_command(debug)
except ImportError:
    # 如果调试模块不可用，创建一个占位命令组
    @cli.group()
    def debug():
        """调试工具（仅开发模式）"""
        import os

        if os.environ.get("APP__ENV", "prod") != "dev":
            click.echo("[WARNING] 调试命令仅在开发模式下可用")
            click.echo("请使用: deepsearch run dev")
            import sys

            sys.exit(1)


@config.command("show")
@click.option(
    "--format", type=click.Choice(["yaml", "json", "table"]), default="yaml", help="输出格式"
)
def config_show(format):
    """显示当前配置"""
    import json

    import yaml
    from core.config import settings

    click.echo("当前配置:")
    click.echo(f"环境: {settings.env}\n")

    # 将配置转换为字典
    config_dict = settings.dict()

    if format == "yaml":
        # YAML 格式输出
        yaml_str = yaml.dump(
            config_dict, default_flow_style=False, allow_unicode=True, sort_keys=False
        )
        click.echo(yaml_str)
    elif format == "json":
        # JSON 格式输出
        json_str = json.dumps(config_dict, indent=2, ensure_ascii=False)
        click.echo(json_str)
    else:
        # 表格格式输出（使用内置方法）
        def flatten_dict(d, parent_key="", sep="."):
            items = []
            for k, v in d.items():
                new_key = f"{parent_key}{sep}{k}" if parent_key else k
                if isinstance(v, dict):
                    items.extend(flatten_dict(v, new_key, sep=sep).items())
                else:
                    items.append((new_key, v))
            return dict(items)

        flat_config = flatten_dict(config_dict)

        # 计算最大宽度
        max_key_width = max(len(k) for k in flat_config.keys()) if flat_config else 10
        max_val_width = max(len(str(v)) for v in flat_config.values()) if flat_config else 10

        # 打印表格头
        click.echo("+" + "-" * (max_key_width + 2) + "+" + "-" * (max_val_width + 2) + "+")
        click.echo(f"| {'配置项':<{max_key_width}} | {'值':<{max_val_width}} |")
        click.echo("+" + "=" * (max_key_width + 2) + "+" + "=" * (max_val_width + 2) + "+")

        # 打印数据行
        for key, value in flat_config.items():
            click.echo(f"| {key:<{max_key_width}} | {str(value):<{max_val_width}} |")

        # 打印表格尾
        click.echo("+" + "-" * (max_key_width + 2) + "+" + "-" * (max_val_width + 2) + "+")


@config.command("set")
@click.argument("key")
@click.argument("value")
@click.option("--env", type=click.Choice(["dev", "prod"]), help="目标环境")
def config_set(key, value, env):
    """设置配置项"""
    import yaml
    from core.config import get_config_dir, settings

    # 确定目标环境
    target_env = env or settings.env
    config_dir = get_config_dir()
    config_file = config_dir / f"settings.{target_env}.yaml"

    if not config_file.exists():
        click.echo(f"[ERROR] 配置文件不存在: {config_file}")
        return

    try:
        # 读取现有配置
        with open(config_file, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}

        # 解析键路径（支持嵌套，如 webui.backend_port）
        keys = key.split(".")
        current = config

        # 导航到目标键的父级
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]

        # 设置值
        final_key = keys[-1]
        old_value = current.get(final_key, "<未设置>")

        # 尝试转换值的类型
        if value.lower() in ["true", "false"]:
            value = value.lower() == "true"
        elif value.isdigit():
            value = int(value)
        else:
            try:
                value = float(value)
            except ValueError:
                pass  # 保持字符串

        current[final_key] = value

        # 写回配置文件
        with open(config_file, "w", encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

        click.echo("[OK] 配置已更新")
        click.echo(f"  环境: {target_env}")
        click.echo(f"  配置项: {key}")
        click.echo(f"  旧值: {old_value}")
        click.echo(f"  新值: {value}")
        click.echo("\n注意：需要重启服务才能使配置生效")

    except Exception as e:
        click.echo(f"[ERROR] 设置配置失败: {e}")


def main():
    """主入口"""
    cli()


if __name__ == "__main__":
    main()
