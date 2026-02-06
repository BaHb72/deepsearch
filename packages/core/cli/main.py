"""
DeepSearch 命令行接口

提供统一的命令行工具来管理和运行 DeepSearch 系统。
"""

import asyncio
import json
import os
import socket
import sys
import time
from datetime import datetime
from pathlib import Path

import click
from loguru import logger

# 延迟导入以避免循环依赖
__version__ = "0.1.0"


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
def check_amazingdata(env: str, config: str | None, timeout: float) -> None:
    """对 AmazingData 依赖进行基础自检"""

    import os

    os.environ["APP__ENV"] = env

    results: dict[str, object] = {
        "environment": env,
        "status": "failed",
        "checks": [],
    }

    def add_check(name: str, status: str, detail: str, suggestion: str | None = None) -> None:
        entry: dict[str, object] = {"name": name, "status": status, "detail": detail}
        if suggestion:
            entry["suggestion"] = suggestion
        checks: list[dict[str, object]] = results.setdefault("checks", [])  # type: ignore[assignment]
        checks.append(entry)

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

    try:
        if config:
            from core.config import config_manager

            config_manager.load(config)
            add_check("加载自定义配置", "ok", f"已加载 {config}")
    except Exception as exc:  # pragma: no cover - 配置解析异常
        add_check("加载自定义配置", "failed", f"读取配置失败：{exc}")
        click.echo(json.dumps(results, ensure_ascii=False, indent=2))
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
        click.echo(json.dumps(results, ensure_ascii=False, indent=2))
        raise SystemExit(1)

    amazingdata_config = getattr(settings, "amazingdata", None)
    if not amazingdata_config:
        add_check(
            "AmazingData 配置",
            "failed",
            "未找到 amazingdata 配置段",
            "请参考 settings.template.yaml 添加 amazingdata 配置后重试",
        )
        click.echo(json.dumps(results, ensure_ascii=False, indent=2))
        raise SystemExit(1)

    if not getattr(amazingdata_config, "enabled", False):
        add_check(
            "AmazingData 启用状态",
            "warning",
            "amazingdata.enabled 当前为 false，跳过连通性检测",
            "如需启用 AmazingData，请在配置中将 enabled 设置为 true",
        )
        results["status"] = "ok"
        click.echo(json.dumps(results, ensure_ascii=False, indent=2))
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
        click.echo(json.dumps(results, ensure_ascii=False, indent=2))
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
        click.echo(json.dumps(results, ensure_ascii=False, indent=2))
        raise SystemExit(1)

    results["status"] = "ok"
    click.echo(json.dumps(results, ensure_ascii=False, indent=2))
    raise SystemExit(0)


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
