#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
RedisTimeSeries 持久化示例

演示如何使用 TimeSeriesZeroMQBus 持久化 ZeroMQ 消息序列
并查询历史数据。
"""

import logging
import random
import time
from datetime import datetime

from deepsearch.event.bus import TimeSeriesZeroMQBus
from deepsearch.event.engine import Event

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def generate_random_tick(symbol: str):
    """生成随机行情数据"""
    return {
        "symbol": symbol,
        "price": round(random.uniform(10000, 60000), 2),
        "volume": round(random.uniform(0.1, 10), 4),
        "timestamp": time.time(),
    }


def main():
    # 创建支持 RedisTimeSeries 持久化的 ZeroMQ 消息总线
    bus = TimeSeriesZeroMQBus(
        url="tcp://127.0.0.1:5555",
        storage_config={
            "host": "localhost",
            "port": 6379,
            "db": 0,
            "key_prefix": "deepsearch:demo:ts:",
        },
        enable_persistence=True,
    )

    try:
        # 生成并发布一些测试数据
        logger.info("发布测试数据...")
        symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]

        for _ in range(20):
            for symbol in symbols:
                # 创建行情事件
                tick_data = generate_random_tick(symbol)
                event = Event("tick", tick_data)

                # 发布事件（会自动持久化）
                bus.publish("market_data", event)
                logger.info(f"发布行情: {symbol} - {tick_data['price']}")

            # 等待一秒
            time.sleep(1)

        # 查询可用的主题
        topics = bus.get_available_topics()
        logger.info(f"可用主题: {topics}")

        for topic in topics:
            # 查询主题下的事件类型
            event_types = bus.get_available_event_types(topic)
            logger.info(f"主题 '{topic}' 下的事件类型: {event_types}")

        # 查询一分钟内的历史数据
        now = time.time()
        one_minute_ago = now - 60

        historical_events = bus.query_historical_events(
            topic="market_data",
            event_type="tick",
            start_time=one_minute_ago,
            end_time=now,
        )

        logger.info(f"查询到 {len(historical_events)} 条历史事件")

        # 显示部分历史数据
        for i, event in enumerate(historical_events[:5]):
            timestamp = datetime.fromtimestamp(event["timestamp"]).strftime("%Y-%m-%d %H:%M:%S")
            data = event["data"]
            logger.info(f"历史事件 {i + 1}: {timestamp} - {data['symbol']} - {data['price']}")

        # 获取持久化统计信息
        stats = bus.get_persistence_stats()
        logger.info(f"持久化统计信息: {stats}")

    finally:
        # 清理资源
        bus.cleanup()
        logger.info("资源已清理")


if __name__ == "__main__":
    main()
