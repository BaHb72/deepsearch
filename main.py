#!/usr/bin/env python3
"""
DeepSearch - 量化交易事件系统主入口
"""
import logging
import sys
import time

from deepsearch.config.setting import settings
from deepsearch.event.bus.bus import CompositeMessageBus
from deepsearch.event.const import EVENT_SYSTEM_READY, EVENT_TICK, EVENT_ORDER, EVENT_TRADE
from deepsearch.event.engine import EventEngine, Event
from deepsearch.event.monitoring import EventSystemMonitor
from deepsearch.gateway.gateway import Gateway
from deepsearch.observability.logger import logger_manager


def setup_logging():
    """初始化日志系统"""
    logger_manager.start()
    logger = logging.getLogger(__name__)
    logger.info("=" * 80)
    logger.info("DeepSearch - 量化交易事件系统")
    logger.info("=" * 80)
    logger.info(f"环境: {settings.app.env}")
    logger.info(f"日志级别: {settings.log.level}")
    return logger


def setup_event_system():
    """初始化事件系统组件"""
    logger = logging.getLogger(__name__)

    # 创建事件引擎
    logger.info("初始化事件引擎...")
    engine = EventEngine(
        queue_size=10000,
        max_workers=32,
        enable_batch_processing=True,
        batch_size=100,
        batch_timeout=0.1
    )

    # 创建消息总线
    logger.info("初始化消息总线...")
    bus = CompositeMessageBus()

    # 创建监控器
    logger.info("初始化系统监控...")
    monitor = EventSystemMonitor(engine, bus)

    # 启动组件
    engine.start()
    bus.start()
    monitor.start()

    logger.info("事件系统初始化成功")
    return engine, bus, monitor


def setup_gateway(engine):
    """初始化网关"""
    logger = logging.getLogger(__name__)
    logger.info("初始化网关...")

    gateway = Gateway(engine)
    gateway.start()

    logger.info("网关初始化成功")
    return gateway


def register_handlers(engine):
    """注册事件处理器"""
    logger = logging.getLogger(__name__)
    logger.info("注册事件处理器...")

    # 示例处理器
    def handle_system_ready(event):
        logger.info("系统已准备就绪")

    def handle_tick(event):
        logger.debug(f"收到行情: {event.data}")

    def handle_order(event):
        logger.info(f"订单事件: {event.data}")

    def handle_trade(event):
        logger.info(f"成交事件: {event.data}")

    # 注册处理器
    engine.register(event_type=EVENT_SYSTEM_READY, handler=handle_system_ready)
    engine.register(event_type=EVENT_TICK, handler=handle_tick, async_flag=True)
    engine.register(event_type=EVENT_ORDER, handler=handle_order)
    engine.register(event_type=EVENT_TRADE, handler=handle_trade)

    logger.info("事件处理器注册完成")


def main():
    """主函数"""
    try:
        # 设置日志
        logger = setup_logging()

        # 初始化组件
        engine, bus, monitor = setup_event_system()
        gateway = setup_gateway(engine)

        # 注册处理器
        register_handlers(engine)

        # 发送系统就绪事件
        engine.put(Event(EVENT_SYSTEM_READY, {"message": "系统初始化完成"}))

        logger.info("DeepSearch 正在运行，按 Ctrl+C 退出")

        # 保持运行
        try:
            while True:
                time.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("收到关闭信号")

        # 清理
        logger.info("正在关闭组件...")
        monitor.stop()
        gateway.stop()
        engine.stop()
        bus.stop()
        logger_manager.stop()

        logger.info("DeepSearch 已关闭")
        return 0

    except Exception as e:
        logging.error(f"严重错误: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
