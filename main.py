#!/usr/bin/env python3
"""
DeepSearch - 量化交易事件系统主入口

该模块是程序的入口点，负责创建和启动MainEngine，
所有的初始化和管理逻辑都委托给MainEngine处理。
"""
import logging
import sys

from deepsearch.constants import EVENT_SYSTEM_READY, EVENT_TICK, EVENT_ORDER, EVENT_TRADE
from deepsearch.core import MainEngine


def setup_default_handlers(engine: MainEngine) -> None:
    """
    设置默认的事件处理器
    
    这些是示例处理器，实际使用时应该根据需求替换
    """
    logger = logging.getLogger(__name__)

    # 示例处理器
    def handle_system_ready(event):
        logger.info("System ready event received")
    
    def handle_tick(event):
        logger.debug(f"Tick event: {event.data}")
    
    def handle_order(event):
        logger.info(f"Order event: {event.data}")
    
    def handle_trade(event):
        logger.info(f"Trade event: {event.data}")

    # 注册处理器
    handlers = {
        EVENT_SYSTEM_READY: handle_system_ready,
        EVENT_TICK: handle_tick,
        EVENT_ORDER: handle_order,
        EVENT_TRADE: handle_trade,
    }

    engine.register_handlers(handlers)

    # 对于需要异步处理的事件，单独注册
    engine.register_handler(EVENT_TICK, handle_tick, async_flag=True)


def main() -> int:
    """
    主函数 - 程序入口
    
    创建MainEngine实例并运行系统
    """
    engine = None

    try:
        # 创建核心引擎
        engine = MainEngine()

        # 初始化系统
        engine.initialize()

        # 注册默认处理器（可选，也可以通过配置文件或插件系统加载）
        setup_default_handlers(engine)

        # 启动系统
        engine.start()

        # 运行主循环
        engine.run()

        return 0

    except KeyboardInterrupt:
        # Ctrl+C 被 MainEngine 的信号处理器捕获
        if engine and engine._logger:
            engine._logger.info("Main process interrupted")
        return 0

    except Exception as e:
        # 严重错误
        if engine and engine._logger:
            engine._logger.error(f"Fatal error: {e}", exc_info=True)
        else:
            print(f"Fatal error: {e}", file=sys.stderr)
        return 1

    finally:
        # 确保引擎被正确关闭
        if engine:
            try:
                engine.stop()
            except Exception as e:
                print(f"Error during shutdown: {e}", file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main())
