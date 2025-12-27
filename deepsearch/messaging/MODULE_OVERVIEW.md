# 消息总线模块概览

## 模块定位

`deepsearch/messaging` 提供统一的消息发布/订阅抽象，兼容内存总线与 ZeroMQ 等实现。模块既可作为核心引擎组件使用，也可供独立服务或外部进程复用。

## 核心组件

- `bus.py`：
  - `MessageBus` 抽象类定义 `publish`、`subscribe`、`unsubscribe` 等基础接口。
  - `CompositeMessageBus` 聚合多个子总线，可基于路由规则（`RouteConfig`）决定消息流向，支持压缩（大于 1KB 使用 zlib）、去重（
      `MessageDeduplicator`）与性能统计。
  - 提供同步与异步订阅包装：`subscribe_async` 将 async handler 通过事件循环调度执行。
  - 内置监控数据结构 `PerformanceStats`，记录发布量、压缩率、路由分布、错误计数。
- `types.py`：定义 `MessageEnvelope`（包含 payload、timestamp、compression flag、headers 等）和 `BusName` 枚举等结构，统一消息格式。
- `factory.py`：根据配置构建 Composite 总线，自动注册默认实现（内存、ZeroMQ），并管理生命周期。
- `implementations/`：
  - `inmemory.py`：轻量级队列实现，适合测试或本地模式。
  - `zeromq.py`：封装 ZeroMQ PUB/SUB 模式，支持多线程安全发布、心跳与自动重连。

## 运行流程

1. 核心引擎在启动阶段调用 `messaging.factory.create_message_bus`，按配置装配 `CompositeMessageBus`。
2. 业务模块通过注入的 `MessageBus` 发布消息，Composite 根据路由规则（通配符匹配 topic）将消息转发到指定总线。
3. 若启用去重，`MessageDeduplicator` 结合 topic + payload 的哈希过滤重复消息。
4. 在需要异步消费的场景，调用 `subscribe_async` 注册协程 handler；内部会在订阅线程中把消息转发到主事件循环执行。
5. 停止引擎时调用 `stop()` 关闭所有子总线，释放资源。

## 设计要点

- 序列化使用 `pickle`，压缩阈值 1KB，可根据需求调整；去重 TTL 默认 60 秒。
- Composite 总线允许配置多个输出（例如同时推送到 ZeroMQ 与内存 bus），并针对每条消息记录路由决策。
- 异步订阅中使用 `loop.call_soon_threadsafe` 保证线程安全。

## 扩展建议

- 新增总线实现时，在 `implementations` 中编写类并在 `factory` 注册；可用于对接 Kafka、RabbitMQ 等。
- 若需要跨进程消息确认机制，可扩展 `MessageEnvelope` 与 Composite 统计逻辑，增加重试/ACK。
