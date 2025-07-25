"""
ZeroMQ TimeSeries 持久化规则使用示例
"""
from deepsearch.event.bus.bus import (
    TimeSeriesZeroMQBus,
    NeverPersist,
    TopicBasedPersist,
    EventTypeBasedPersist,
    SamplingPersist,
    CompositePersistenceRule
)
from deepsearch.event.const import EVENT_TICK, EVENT_ORDER, EVENT_TRADE, EVENT_LOG
from deepsearch.event.engine import Event


# ==============================================================================
# 示例1：基于主题的持久化
# ==============================================================================
def example_topic_based_persistence():
    """只持久化特定主题的消息"""

    # 只持久化 TICK 和 TRADE 主题
    rule = TopicBasedPersist(
        persist_topics=[EVENT_TICK, EVENT_TRADE],
        exclude_topics=[EVENT_LOG]  # 排除日志
    )

    bus = TimeSeriesZeroMQBus(
        enable_persistence=True,
        persistence_rule=rule
    )

    # 这些会被持久化
    bus.publish(EVENT_TICK, {"price": 100.5, "volume": 1000})
    bus.publish(EVENT_TRADE, {"order_id": "123", "price": 100.5})

    # 这个不会被持久化
    bus.publish(EVENT_LOG, {"message": "System started"})


# ==============================================================================
# 示例2：基于事件类型的持久化
# ==============================================================================
def example_event_type_based_persistence():
    """基于事件类型决定是否持久化"""

    # 只持久化 TICK 和 ORDER 类型的事件
    rule = EventTypeBasedPersist(
        persist_types=[EVENT_TICK, EVENT_ORDER]
    )

    bus = TimeSeriesZeroMQBus(
        enable_persistence=True,
        persistence_rule=rule
    )

    # 创建不同类型的事件
    tick_event = Event(EVENT_TICK, {"price": 100.5})
    order_event = Event(EVENT_ORDER, {"order_id": "123"})
    log_event = Event(EVENT_LOG, {"message": "Info"})

    # TICK 和 ORDER 会被持久化
    bus.publish(EVENT_TICK, tick_event)
    bus.publish(EVENT_ORDER, order_event)

    # LOG 不会被持久化
    bus.publish(EVENT_LOG, log_event)


# ==============================================================================
# 示例3：采样持久化（适合高频数据）
# ==============================================================================
def example_sampling_persistence():
    """对高频数据进行采样持久化"""

    # 只持久化 10% 的消息
    rule = SamplingPersist(sample_rate=0.1)

    bus = TimeSeriesZeroMQBus(
        enable_persistence=True,
        persistence_rule=rule
    )

    # 发送 100 个 tick，大约只有 10 个会被持久化
    for i in range(100):
        bus.publish(EVENT_TICK, {"price": 100 + i * 0.01, "index": i})


# ==============================================================================
# 示例4：组合规则
# ==============================================================================
def example_composite_rules():
    """使用组合规则实现复杂的持久化策略"""

    # 策略：TICK 数据采样10%，ORDER 和 TRADE 全部持久化
    tick_sampling = CompositePersistenceRule([
        TopicBasedPersist(persist_topics=[EVENT_TICK]),
        SamplingPersist(sample_rate=0.1)
    ], mode="all")  # 必须是 TICK 且在采样范围内

    order_trade_always = TopicBasedPersist(
        persist_topics=[EVENT_ORDER, EVENT_TRADE]
    )

    # 组合规则：满足任一子规则即持久化
    composite_rule = CompositePersistenceRule([
        tick_sampling,
        order_trade_always
    ], mode="any")

    bus = TimeSeriesZeroMQBus(
        enable_persistence=True,
        persistence_rule=composite_rule
    )

    # TICK 数据只有 10% 会被持久化
    for i in range(100):
        bus.publish(EVENT_TICK, {"price": 100 + i * 0.01})

    # ORDER 和 TRADE 全部持久化
    bus.publish(EVENT_ORDER, {"order_id": "123"})
    bus.publish(EVENT_TRADE, {"trade_id": "456"})


# ==============================================================================
# 示例5：使用消息级别的持久化控制
# ==============================================================================
def example_message_level_control():
    """在消息级别控制持久化"""

    # 默认不持久化
    rule = NeverPersist()

    bus = TimeSeriesZeroMQBus(
        enable_persistence=True,
        persistence_rule=rule
    )

    # 方法1：使用 persist 参数强制持久化
    bus.publish(EVENT_TICK, {"price": 100.5}, persist=True)  # 会被持久化
    bus.publish(EVENT_TICK, {"price": 100.6}, persist=False)  # 不会被持久化
    bus.publish(EVENT_TICK, {"price": 100.7})  # 使用规则，不会被持久化

    # 方法2：在事件数据中使用 _persist 标记
    event_data = {
        "price": 100.8,
        "_persist": True  # 这个标记会强制持久化
    }
    bus.publish(EVENT_TICK, event_data)  # 会被持久化


# ==============================================================================
# 示例6：量化程序的最佳实践
# ==============================================================================
def example_quant_best_practice():
    """量化程序的持久化最佳实践"""

    # 创建一个适合量化程序的持久化规则
    quant_rule = CompositePersistenceRule([
        # 1. 关键交易数据全部持久化
        EventTypeBasedPersist(persist_types=[EVENT_ORDER, EVENT_TRADE]),

        # 2. TICK 数据根据主题和采样率决定
        CompositePersistenceRule([
            TopicBasedPersist(persist_topics=["BTCUSDT", "ETHUSDT"]),  # 主要交易对
            SamplingPersist(sample_rate=0.01)  # 1% 采样率
        ], mode="all"),

        # 3. 排除日志消息
        EventTypeBasedPersist(exclude_types=[EVENT_LOG])
    ], mode="any")

    bus = TimeSeriesZeroMQBus(
        enable_persistence=True,
        persistence_rule=quant_rule,
        storage_config={
            "retention_ms": 7 * 24 * 60 * 60 * 1000  # 保留7天
        }
    )

    # 使用示例
    # 交易数据 - 全部持久化
    bus.publish(EVENT_ORDER, {"order_id": "123", "symbol": "BTCUSDT"})
    bus.publish(EVENT_TRADE, {"trade_id": "456", "symbol": "BTCUSDT"})

    # TICK 数据 - 主要交易对的 1% 采样
    for i in range(1000):
        bus.publish("BTCUSDT", Event(EVENT_TICK, {"price": 50000 + i}))
        bus.publish("DOGEUSDT", Event(EVENT_TICK, {"price": 0.1 + i * 0.0001}))

    # 日志 - 不持久化
    bus.publish(EVENT_LOG, {"message": "Strategy started"})

    # 特殊情况：强制持久化某个重要的 tick
    important_tick = {
        "price": 51000,
        "volume": 1000000,
        "_persist": True  # 强制持久化
    }
    bus.publish("BTCUSDT", Event(EVENT_TICK, important_tick))


if __name__ == "__main__":
    print("持久化规则示例:")
    print("1. 基于主题的持久化")
    print("2. 基于事件类型的持久化")
    print("3. 采样持久化")
    print("4. 组合规则")
    print("5. 消息级别控制")
    print("6. 量化程序最佳实践")
