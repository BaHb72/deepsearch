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
    click.echo(f"停止组件: {component}")
    # TODO: 实现组件停止逻辑


@cli.command()
def status():
    """查看系统状态"""
    click.echo("系统状态:")
    # TODO: 实现状态查询逻辑
    click.echo("  - 引擎: 未运行")
    click.echo("  - WebUI: 未运行")
    click.echo("  - 网关: 未运行")


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

    # TODO: 实现配置文件生成逻辑
    config_template = """# DeepSearch 配置文件
version: 1.0

# 系统配置
system:
  name: DeepSearch
  mode: production
  
# 日志配置
logging:
  level: INFO
  output: file
  
# WebUI 配置
webui:
  host: 0.0.0.0
  port: 8000
  
# 交易配置
trading:
  # 添加你的交易配置
"""

    with open(output, 'w', encoding='utf-8') as f:
        f.write(config_template)

    click.echo(f"[OK] Config file generated: {output}")


@cli.group()
def config():
    """配置管理"""
    pass


@config.command('show')
def config_show():
    """显示当前配置"""
    click.echo("当前配置:")
    # TODO: 实现配置显示逻辑


@config.command('set')
@click.argument('key')
@click.argument('value')
def config_set(key, value):
    """设置配置项"""
    click.echo(f"设置配置: {key} = {value}")
    # TODO: 实现配置设置逻辑


def main():
    """主入口"""
    cli()


if __name__ == "__main__":
    main()
