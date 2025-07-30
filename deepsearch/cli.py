"""
DeepSearch 命令行接口

提供统一的命令行工具来管理和运行 DeepSearch 系统。
"""
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

    # 设置日志级别
    logger_manager.set_level(log_level)
    logger_manager.start()

    if mode == 'full':
        if no_frontend:
            click.echo("启动系统（不含前端）...")
            # 使用分阶段启动，但不启动前端
            from deepsearch.core import MainEngine
            engine = MainEngine()
            engine.initialize()
            engine.start_phased(
                include_business=True,
                include_webui=True,
                include_frontend=False  # 不启动前端
            )

            try:
                click.echo("系统运行中，按 Ctrl+C 退出")
                from deepsearch.config import get_config
                config = get_config()
                click.echo(f"WebUI API: http://localhost:{config.webui.backend_port}")
                import time
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                click.echo("\n正在关闭系统...")
            finally:
                engine.stop()
        else:
            click.echo("启动完整系统（含前端）...")
            # 使用分阶段启动，启动所有组件
            from deepsearch.core import MainEngine
            engine = MainEngine()
            engine.initialize()
            engine.start_phased(
                include_business=True,
                include_webui=True,
                include_frontend=True  # 启动前端
            )

            try:
                click.echo("系统运行中，按 Ctrl+C 退出")
                from deepsearch.config import get_config
                config = get_config()
                click.echo(f"WebUI 前端: http://localhost:{config.webui.frontend_port}")
                click.echo(f"WebUI API: http://localhost:{config.webui.backend_port}")

                if open_browser:
                    import webbrowser
                    webbrowser.open(f"http://localhost:{config.webui.frontend_port}")

                import time
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                click.echo("\n正在关闭系统...")
            finally:
                engine.stop()

    elif mode == 'engine':
        click.echo("仅启动引擎...")
        # 加载配置
        if config:
            from deepsearch.config import config_manager
            config_manager.load(config)

        from deepsearch.core import MainEngine
        engine = MainEngine()
        engine.initialize()
        engine.start_infrastructure()

        try:
            click.echo("引擎运行中，按 Ctrl+C 退出")
            import time
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            click.echo("\n正在关闭引擎...")
        finally:
            engine.stop()

    elif mode == 'webui':
        click.echo("启动 WebUI...")
        from deepsearch.webui.runner import run_standalone
        run_standalone()


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
    click.echo(f"启动组件: {component}")

    from deepsearch.core import MainEngine
    engine = MainEngine()
    engine.initialize()

    if component == 'all':
        engine.start()
    else:
        engine.start_infrastructure()
        engine.start_component(component)

    try:
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        engine.stop()


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
@click.option('--all', is_flag=True, help='清理所有端口')
def cleanup(all):
    """清理占用的端口和进程"""
    click.echo("清理占用的端口和进程...")

    import psutil

    # 要清理的端口
    ports_to_clean = [8000, 3000] if all else [8000]

    cleaned = 0
    for conn in psutil.net_connections():
        if conn.laddr.port in ports_to_clean and conn.status == 'LISTEN':
            try:
                proc = psutil.Process(conn.pid)
                if 'python' in proc.name().lower():
                    click.echo(f"  终止进程 PID={conn.pid} (端口 {conn.laddr.port})")
                    proc.terminate()
                    proc.wait(timeout=3)
                    cleaned += 1
            except Exception as e:
                click.echo(f"  无法终止进程 PID={conn.pid}: {e}")

    if cleaned > 0:
        click.echo(f"[OK] Cleaned {cleaned} processes")
    else:
        click.echo("[OK] No processes to clean")


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
    from deepsearch.config.manager import ConfigManager
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
