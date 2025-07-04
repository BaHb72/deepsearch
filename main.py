# main.py
import argparse
import sys

from trader.core.logger import configure_logger, get_logger

# 模块级日志记录器占位符 (module-level logger placeholder)
log = None

def parse_args(argv: list[str]) -> argparse.Namespace:
    """
    解析命令行参数。

    注意：
        目前尚未定义命令行参数。此函数是为未来扩展预留的占位符。
    """
    parser = argparse.ArgumentParser(description="DeepSearch Quant Starter")
    # (未来如有需要，在此处添加命令行参数)
    return parser.parse_args(argv)

# ───────────────────────────────────────────────
# 日志初始化 (Logging initialization)
# ───────────────────────────────────────────────
def init_logging() -> None:
    """
    初始化日志系统。

    如果初始化失败，将向标准错误输出错误信息并退出程序。
    """
    global log
    try:
        configure_logger()
    except Exception as exc:
        # 如果日志配置失败，将错误输出到标准错误并退出
        print(f"[Logger init failed] {exc}", file=sys.stderr)
        sys.exit(1)
    # 成功配置后获取用于启动过程的日志记录器
    log = get_logger(service="boot")
    log.info("日志模块已启动")

def main(sys_args: list[str] | None = None) -> None:
    """
    应用程序主入口 (Application entry point).

    参数:
        sys_args: 命令行参数列表。如果为None，则使用sys.argv[1:]。
    """
    # 解析命令行参数 (Parse command-line arguments)
    args = parse_args(sys_args or sys.argv[1:])
    # 初始化日志系统 (Initialize logging)
    init_logging()
    try:
        # TODO: 在此启动应用程序主逻辑 (Start the main application logic here, e.g., trading loop or web server)
        pass
    except KeyboardInterrupt:
        log.warning("收到 Ctrl+C，服务退出")
    except Exception:
        log.exception("应用程序运行期间发生未捕获异常")
        sys.exit(1)

if __name__ == "__main__":
    main()
