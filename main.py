import argparse
import sys

from trader.core.logger import configure_logger, get_logger

log = get_logger(service="boot")


def parse_args(argv: list[str]) -> argparse.Namespace:
    """
    解析命令行参数

    注意: 当前未启用任何参数，保留此函数以便未来扩展
    """
    parser = argparse.ArgumentParser(description="DeepSearch Quant Starter")
    # 可在此添加命令行参数定义
    return parser.parse_args(argv)


# ───────────────────────────────────────────────
# 日志初始化
# ───────────────────────────────────────────────
def init_logging() -> None:
    """
    初始化日志系统

    如初始化失败，直接打印错误信息到标准错误输出并退出程序
    """
    try:
        configure_logger()
    except Exception as exc:
        log.error(f"[Logger init failed] {exc}", file=sys.stderr)
        sys.exit(1)
    log.info("日志模块已启动")


def main(sys_args: list[str] | None = None) -> None:
    """
    应用程序主入口函数

    Args:
        sys_args: 命令行参数列表，默认使用系统参数
    """
    # 解析命令行参数
    args = parse_args(sys_args or sys.argv[1:])

    # 初始化日志系统
    init_logging()

    try:
        pass
        # 启动应用程序主逻辑
        # 在此处可扩展量化交易主循环或Web服务器

    except KeyboardInterrupt:
        log.warning("收到 Ctrl+C，服务退出")
    except Exception:
        log.exception("应用程序运行期间发生未捕获异常")
        sys.exit(1)


if __name__ == "__main__":
    main()
