# messaging 模块实现说明

## 模块定位

`deepsearch.messaging` 提供内部消息总线抽象，用于在事件引擎、策略、网关与外部服务之间传递命令和回报。其目标是解耦消息发布者与订阅者，并可根据配置选择不同传输后端。

## 目录结构

- `bus.py`：定义 `CompositeMessageBus` 与内存队列实现，支持多通道合并。
- `factory.py`：根据配置选择消息通道实现（内存、ZeroMQ、本地文件等）。
- `types.py`：统一消息类型与载荷结构体，便于序列化与校验。
- `implementations/`：具体消息总线适配层，如 `inmemory.py`、`zeromq.py`。

## 核心数据结构

- `MessageEnvelope`：包含 `topic`、`payload`、`priority`、`headers`，支持追踪链路 ID。
- `MessageBus` 接口：定义 `publish()`、`subscribe()`、`request()` 等方法。
- `RetryPolicy`：配置发布失败的退避策略，与 `core.error_handling` 协同。

## 关键流程

1. 启动时 `factory.create_bus()` 根据 `settings.messaging` 生成主消息总线。
2. 发布者通过 `CompositeMessageBus.publish()` 写入消息，并记录审计日志。
3. 订阅者注册回调后，按优先级拉取消息执行，必要时可开启独立线程。
4. 失败消息根据策略进入死信队列或触发 `observability` 告警。

## 扩展与集成

- 新增后端时，在 `implementations/` 中实现 `MessageBus` 接口，并在 `factory` 注册。
- 与 `event` 模块交互时，建议以事件类型作为 `topic`，保持语义一致。
- 如需跨进程通信，需在配置中开启持久化队列并确保加密/鉴权。
- 测试可使用 `InMemoryMessageBus`，通过依赖注入替换生产实现。
