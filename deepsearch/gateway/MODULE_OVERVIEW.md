# Gateway 模块概览

## 模块定位

`deepsearch/gateway` 定义了与外部行情/交易系统对接的抽象层。模块提供统一的 `BaseGateway`
基类，管理连接生命周期、心跳、异步任务执行和事件推送，确保具体交易接口实现时只需关注协议细节。

## BaseGateway 功能结构

- **状态管理**：`GatewayStatus` 枚举定义 `DISCONNECTED/CONNECTING/CONNECTED/RECONNECTING/CLOSED`；类属性 `status`
  始终反映当前连接态。
- **消息通道**：构造函数注入 `MessageBus`，所有行情、成交、日志、错误事件通过 `message_bus.publish` 或事件引擎 `Event` 分发。
- **异步执行**：内部维护 `ThreadPoolExecutor`（默认最多 2 workers）处理阻塞任务；`run_async`/`run_in_executor` 将同步 I/O
  封装为协程。
- **心跳机制**：`start_heartbeat` 创建后台线程周期性发送 `HEARTBEAT_EVENT_TYPE` 事件，并可配置间隔、断线重连延迟。
- **连接生命周期**：
  - `connect()`：置状态为 `CONNECTING`，调用子类 `on_connect`，成功后触发 `on_connected` 与心跳。
  - `disconnect()`：调用子类 `on_disconnect`，停止心跳、线程池和事件监听。
  - `reconnect()`、`schedule_reconnect()`：提供自动重连能力。
- **事件分发**：封装 `emit_tick/order/trade/log/error` 辅助方法，把原始数据包装成 `Event` 或消息总线 payload，统一事件类型：
  `EVENT_TICK/ORDER/TRADE/LOG/ERROR`。
- **订阅/下单接口**：抽象方法 `subscribe`, `unsubscribe`, `send_order`, `cancel_order`、`query_account` 等由具体网关实现。
- **错误处理**：提供 `_safe_execute`、`_handle_exception` 等方法，将异常记录日志并生成错误事件。

## 典型使用流程

1. 新增具体网关（如 QMT、模拟）时继承 `BaseGateway` 并实现抽象方法（连接、订阅、下单等）。
2. 实例化时传入系统 `MessageBus`，调用 `connect()` 建立连接，成功后自动进入心跳循环。
3. 外部接收到行情/订单响应后调用 `emit_tick`/`emit_trade` 等方法，事件会进入事件引擎和消息总线。
4. 当连接异常或主动关闭时，`disconnect()` 处理资源释放，必要时 `schedule_reconnect()` 再次尝试。

## 设计要点

- 模块大量使用 `threading.Event`、锁与超时控制，确保在多线程环境下安全关闭。
- Heartbeat 线程与执行线程池可选地被关闭（`stop_executor=True`），避免资源泄漏。
- 所有对外接口均记录详细日志，便于 CLI `debug errors` 调试。

## 扩展建议

- 实现新网关时应充分利用 `emit_*` 辅助函数，保持事件格式一致。
- 如需支持特殊的心跳或认证流程，可覆写 `start_heartbeat` 或添加额外的周期任务。
