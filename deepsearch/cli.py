"""
DeepSearch 命令行接口

提供统一的命令行工具来管理和运行 DeepSearch 系统。
"""
import time
from datetime import datetime

import click

# 延迟导入以避免循环依赖
__version__ = "0.1.0"


@click.group()
@click.version_option(version=__version__, prog_name="DeepSearch")
def cli():
    """DeepSearch - 智能量化交易系统"""
    pass


@cli.command()
@click.option('--mode', type=click.Choice(['full', 'engine', 'webui']),
              default='full', help='运行模式')
@click.option('--config', type=click.Path(exists=True),
              help='配置文件路径')
@click.option('--log-level', type=click.Choice(['DEBUG', 'INFO', 'WARNING', 'ERROR']),
              default='INFO', help='日志级别')
@click.option('--no-frontend', is_flag=True,
              help='不启动前端（仅在full模式下有效）')
@click.option('--open-browser', is_flag=True,
              help='自动打开浏览器')
def run(mode, config, log_level, no_frontend, open_browser):
    """运行 DeepSearch 系统"""
    # 延迟导入
    from deepsearch.observability.logger import logger_manager
    from deepsearch.core.async_runner import run_async_engine
    from deepsearch.config import get_config

    # 设置日志级别
    logger_manager.set_level(log_level)
    logger_manager.start()

    # 加载配置
    if config:
        from deepsearch.config import config_manager
        config_manager.load(config)

    # 使用上下文管理器管理引擎生命周期
    if mode == 'webui':
        # WebUI 模式特殊处理
        click.echo("启动 WebUI...")
        from deepsearch.webui.runner import run_standalone
        run_standalone()
    else:
        # 配置参数
        context_config = {
            'no_frontend': no_frontend,
            'open_browser': open_browser
        }

        click.echo(f"启动模式: {mode}")

        # 显示访问信息
        if mode == 'full':
            app_config = get_config()
            click.echo(f"WebUI API: http://localhost:{app_config.webui.backend_port}")
            if no_frontend:
                click.echo(
                    "Note: Frontend needs to be started separately - cd deepsearch/webui/frontend && npm run dev")

            if open_browser and not no_frontend:
                import webbrowser
                webbrowser.open(f"http://localhost:{app_config.webui.backend_port}")

        # 使用异步运行器
        click.echo("System running, press Ctrl+C to exit")
        run_async_engine(mode=mode, config=context_config)
        click.echo("System closed")


@cli.command()
@click.option('--frontend/--no-frontend', default=True,
              help='是否启动前端')
@click.option('--frontend-port', type=int, default=None,
              help='前端端口（默认从配置读取）')
@click.option('--backend-port', type=int, default=None,
              help='后端端口（默认从配置读取）')
@click.option('--open-browser/--no-open-browser', default=False,
              help='是否自动打开浏览器')
def webui(frontend, frontend_port, backend_port, open_browser):
    """运行 WebUI（独立模式）"""
    from deepsearch.webui.runner import run_standalone
    from deepsearch.utils.port_checker import PortChecker

    # 检查端口冲突
    if not PortChecker.validate_ports():
        click.echo("请解决端口冲突后再启动服务。")
        return

    run_standalone(
        start_frontend=frontend,
        frontend_port=frontend_port,
        backend_port=backend_port,
        auto_open_browser=open_browser,
        start_engine=True,
        infrastructure_only=True
    )


@cli.command()
def check_ports():
    """检查端口配置和占用情况"""
    from deepsearch.utils.port_checker import check_and_report_ports
    check_and_report_ports()


@cli.command()
@click.argument('component', type=click.Choice(['gateway', 'trader', 'strategy', 'all']))
def start(component):
    """启动指定组件"""
    from deepsearch.core.engine_context import EngineContext
    
    click.echo(f"启动组件: {component}")

    # 使用上下文管理器
    with EngineContext(mode='engine') as engine:
        try:
            if component == 'all':
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
@click.argument('component', type=click.Choice(['gateway', 'trader', 'strategy', 'all']))
def stop(component):
    """停止指定组件"""
    from deepsearch.core.engine import MainEngine
    from deepsearch.core.component_manager import ComponentManager

    try:
        # 获取组件管理器实例
        component_manager = ComponentManager()

        if component == 'all':
            click.echo("停止所有组件...")
            # 创建引擎实例来停止所有组件
            engine = MainEngine()
            engine.stop()
            click.echo("[OK] 所有组件已停止")
        else:
            # 停止特定组件
            component_map = {
                'gateway': 'gateway',
                'trader': 'trader',
                'strategy': 'strategy'
            }

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
    from deepsearch.core.component_manager import ComponentManager
    import psutil
    
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
                status = info.status.value if hasattr(info, 'status') else 'UNKNOWN'
                status_color = 'green' if status == 'running' else 'red'
                click.echo(f"  - {name}: ", nl=False)
                click.secho(status.upper(), fg=status_color)

        # 检查端口占用情况
        click.echo("\n端口占用情况:")
        ports_to_check = {
            8000: "WebUI Backend",
            3000: "WebUI Frontend",
            5556: "ZeroMQ Pub",
            5557: "ZeroMQ Sub"
        }

        for port, service in ports_to_check.items():
            in_use = False
            for conn in psutil.net_connections():
                if conn.laddr.port == port and conn.status == 'LISTEN':
                    in_use = True
                    break

            status = "占用" if in_use else "空闲"
            color = 'red' if in_use else 'green'
            click.echo(f"  - {service} (:{port}): ", nl=False)
            click.secho(status, fg=color)

    except Exception as e:
        click.echo(f"[ERROR] 获取状态失败: {e}")


@cli.command()
@click.option('--all', is_flag=True, help='清理所有端口和进程')
@click.option('--force', is_flag=True, help='强制清理')
def cleanup(all, force):
    """清理占用的端口和进程"""
    click.echo("清理占用的端口和进程...")

    from deepsearch.core.process_manager import process_manager

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
        from deepsearch.config import get_config
        config = get_config()

        ports_to_clean = [
            config.webui.backend_port,
            config.webui.frontend_port
        ]

        # 添加 ZMQ 端口（如果配置存在）
        if 'zmq' in config.message_bus.buses:
            zmq_config = config.message_bus.buses['zmq'].config
            if hasattr(zmq_config, 'pub_port'):
                ports_to_clean.append(zmq_config.pub_port)
                ports_to_clean.append(zmq_config.sub_port)
            elif isinstance(zmq_config, dict):
                ports_to_clean.append(zmq_config.get('pub_port', 5556))
                ports_to_clean.append(zmq_config.get('sub_port', 5557))

        cleaned = 0
        for conn in psutil.net_connections():
            if hasattr(conn, 'laddr') and conn.laddr.port in ports_to_clean and conn.status == 'LISTEN':
                try:
                    proc = psutil.Process(conn.pid)
                    click.echo(f"  清理端口 {conn.laddr.port} (PID={conn.pid}, {proc.name()})")
                    proc.terminate()
                    proc.wait(timeout=3)
                    cleaned += 1
                except Exception as e:
                    if force:
                        try:
                            proc.kill()
                            cleaned += 1
                        except Exception as e:
                            logger.debug(f"Failed to kill process {proc.pid}: {e}")
                            pass

        if cleaned > 0:
            click.echo(f"\n[OK] 清理了 {cleaned} 个进程")

    click.echo("\n[OK] 清理完成")


@cli.command()
def diagnose():
    """诊断系统资源状态"""
    from deepsearch.core.process_manager import process_manager
    import json

    click.echo("系统资源诊断\n")

    # 获取状态
    status = process_manager.get_status()

    # 显示概览
    click.echo("资源概览:")
    click.echo(f"  总资源数: {status['total_resources']}")
    click.echo(f"  关闭中: {'是' if status['shutting_down'] else '否'}")

    # 按类型统计
    click.echo("\n按类型统计:")
    for rtype, count in status['resources_by_type'].items():
        if count > 0:
            click.echo(f"  {rtype}: {count}")

    # 按状态统计
    click.echo("\n按状态统计:")
    for rstatus, count in status['resources_by_status'].items():
        if count > 0:
            click.echo(f"  {rstatus}: {count}")

    # 活跃资源详情
    if status['active_resources']:
        click.echo("\n活跃资源详情:")
        for resource in status['active_resources']:
            click.echo(f"\n  [{resource['type']}] {resource['name']}")
            click.echo(f"    ID: {resource['id']}")
            click.echo(f"    状态: {resource['status']}")
            click.echo(f"    创建时间: {resource['created_at']}")

    # 检查潜在问题
    click.echo("\n潜在问题检查:")
    issues = []

    # 检查僵尸线程
    if status['resources_by_status'].get('running', 0) > 10:
        issues.append("发现过多运行中的资源，可能存在资源泄露")

    # 检查失败的资源
    if status['resources_by_status'].get('failed', 0) > 0:
        issues.append(f"有 {status['resources_by_status']['failed']} 个资源处于失败状态")

    if issues:
        for issue in issues:
            click.secho(f"  ⚠ {issue}", fg='yellow')
    else:
        click.secho("  ✓ 未发现明显问题", fg='green')

    # 导出详细信息
    if click.confirm("\n是否导出详细诊断信息到文件？"):
        filename = f"deepsearch-diagnose-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(status, f, indent=2, ensure_ascii=False)
        click.echo(f"\n诊断信息已保存到: {filename}")


@cli.command()
@click.option('--output', type=click.Path(), default='config.yaml',
              help='输出文件路径')
def init(output):
    """初始化配置文件"""
    click.echo(f"生成配置文件: {output}")

    from deepsearch.config import settings
    import yaml
    from pathlib import Path

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
            "debug": False
        },
        "log": {
            "active": True,
            "level": "INFO",
            "rotation": "00:00",
            "retention_days": 7,
            "json": False
        },
        "webui": {
            "backend_host": "0.0.0.0",
            "backend_port": 8000,
            "frontend_port": 3000,
            "auto_open_browser": True
        },
        "message_bus": {
            "buses": {
                "zmq": {
                    "type": "zeromq",
                    "config": {
                        "host": "127.0.0.1",
                        "pub_port": 5556,
                        "sub_port": 5557
                    }
                }
            }
        },
        "monitoring": {
            "enabled": True,
            "metrics_interval": 60,
            "health_check_interval": 30
        },
        "database": {
            "main": {
                "url": "sqlite:///deepsearch.db",
                "echo": False
            }
        }
    }

    # 写入配置文件
    with open(output, 'w', encoding='utf-8') as f:
        yaml.dump(config_template, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    click.echo(f"[OK] 配置文件已生成: {output}")
    click.echo("\n提示：")
    click.echo("  1. 请根据实际需求修改配置文件")
    click.echo("  2. 使用 'deepsearch run --config <file>' 指定配置文件运行")


@cli.group()
def config():
    """配置管理"""
    pass


@config.command('show')
@click.option('--format', type=click.Choice(['yaml', 'json', 'table']), default='yaml', help='输出格式')
def config_show(format):
    """显示当前配置"""
    from deepsearch.config import settings
    import yaml
    import json
    
    click.echo("当前配置:")
    click.echo(f"环境: {settings.env}\n")

    # 将配置转换为字典
    config_dict = settings.dict()

    if format == 'yaml':
        # YAML 格式输出
        yaml_str = yaml.dump(config_dict, default_flow_style=False, allow_unicode=True, sort_keys=False)
        click.echo(yaml_str)
    elif format == 'json':
        # JSON 格式输出
        json_str = json.dumps(config_dict, indent=2, ensure_ascii=False)
        click.echo(json_str)
    else:
        # 表格格式输出（使用内置方法）
        def flatten_dict(d, parent_key='', sep='.'):
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


@config.command('set')
@click.argument('key')
@click.argument('value')
@click.option('--env', type=click.Choice(['dev', 'prod']), help='目标环境')
def config_set(key, value, env):
    """设置配置项"""
    from deepsearch.config import settings
    import yaml
    from pathlib import Path

    # 确定目标环境
    target_env = env or settings.env
    config_file = Path(f"deepsearch/config/settings.{target_env}.yaml")

    if not config_file.exists():
        click.echo(f"[ERROR] 配置文件不存在: {config_file}")
        return

    try:
        # 读取现有配置
        with open(config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f) or {}

        # 解析键路径（支持嵌套，如 webui.backend_port）
        keys = key.split('.')
        current = config

        # 导航到目标键的父级
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]

        # 设置值
        final_key = keys[-1]
        old_value = current.get(final_key, '<未设置>')

        # 尝试转换值的类型
        if value.lower() in ['true', 'false']:
            value = value.lower() == 'true'
        elif value.isdigit():
            value = int(value)
        else:
            try:
                value = float(value)
            except ValueError:
                pass  # 保持字符串

        current[final_key] = value

        # 写回配置文件
        with open(config_file, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

        click.echo(f"[OK] 配置已更新")
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
