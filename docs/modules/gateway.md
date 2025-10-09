# gateway 模块实现说明

## 模块定位

`deepsearch.gateway` 负责与外部交易撮合或行情系统交互，抽象出统一的网关接口，屏蔽各数据源/券商 API 差异，同时向事件引擎与策略层提供标准化的订单与成交信息。

## 主要文件

- `gateway.py`：定义 `BaseGateway` 抽象类及其生命周期管理；内置连接、心跳、错误回报处理流程。
- `__init__.py`：聚合常用导出，供策略与基础设施模块引用。

## 核心类与数据结构

- `BaseGateway`：统一接口，包含 `connect()`、`subscribe()`、`send_order()`、`cancel_order()` 等方法。
- `RemoteOrder`、`RemoteTrade`：封装外部系统回报的结构体，转换为内部事件。
- `GatewayContext`：记录连接状态、重连次数、认证信息等，支持热重启。

## 关键流程

1. 启动时读取 `config.data_source_config`，选择具体实现并实例化。
2. 网关建立连接后，注册行情/成交回调，将数据转化为 `event.Event` 投递。
3. 策略层下单时，先经 `messaging` 转换为标准订单，再通过网关发送。
4. 发生通信异常时调用 `core.error_handling` 触发重连或降级模式。

## 扩展与集成

- 新增券商对接需继承 `BaseGateway`，实现连接、订阅与推送解析。
- 数据字段映射应统一走 `constants.business`，避免魔法值散落。
- 安全性相关（签名、密钥）由 `config.crypto` 与 settings 文件管理。
- 所有外部调用必须封装重试与超时逻辑，并上报 `observability` 指标。
