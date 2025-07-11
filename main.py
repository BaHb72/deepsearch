import argparse
import sys
from typing import Optional

from deepsearch.observability.logger import configure_logger, get_logger


class Application:
    """DeepSearch 应用程序主类"""

    def __init__(self):
        self.logger: Optional[object] = None
        self.args: Optional[argparse.Namespace] = None

    def parse_args(self, argv: list[str]) -> argparse.Namespace:
        """
        解析命令行参数。
        
        注意：
            目前尚未定义命令行参数。此函数是为未来扩展预留的占位符。
        """
        parser = argparse.ArgumentParser(description="DeepSearch Quant Starter")
        # (未来如有需要，在此处添加命令行参数)
        return parser.parse_args(argv)

    def init_logging(self) -> None:
        """
        初始化日志系统。
        
        如果初始化失败，将向标准错误输出错误信息并退出程序。
        """
        try:
            configure_logger()
        except Exception as exc:
            # 如果日志配置失败，将错误输出到标准错误并退出
            print(f"[Logger init failed] {exc}", file=sys.stderr)
            sys.exit(1)
        # 成功配置后获取用于启动过程的日志记录器
        self.logger = get_logger(service="boot")
        self.logger.info("日志模块已启动")

    def run(self, sys_args: list[str] | None = None) -> None:
        """
        运行应用程序主逻辑。
        
        参数:
            sys_args: 命令行参数列表。如果为None，则使用sys.argv[1:]。
        """
        # 解析命令行参数 (Parse command-line arguments)
        self.args = self.parse_args(sys_args or sys.argv[1:])
        # 初始化日志系统 (Initialize logging)
        self.init_logging()

        try:
            self.logger.info("DeepSearch 启动完成（占位）")
            pass
        except KeyboardInterrupt:
            self.logger.warning("收到 Ctrl+C，服务退出")
        except Exception:
            self.logger.exception("应用程序运行期间发生未捕获异常")
            sys.exit(1)


def main(sys_args: list[str] | None = None) -> None:
    """
    应用程序主入口 (Application entry point).
    
    参数:
        sys_args: 命令行参数列表。如果为None，则使用sys.argv[1:]。
    """
    app = Application()
    app.run(sys_args)


if __name__ == "__main__":
    main()
