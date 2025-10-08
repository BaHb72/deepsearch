# infrastructure 模块实现说明

## 模块定位

`deepsearch.infrastructure` 统一管理系统的底层依赖（缓存、数据库、消息通道、监控、数据提供方等），为上层业务提供稳定、可替换的实现。模块严格遵循工厂与接口分层，确保切换实现时无需侵入核心逻辑。

## 目录总览

- `cache/`、`caching/`：多级缓存实现，包含内存 LRU、文件缓存与 Redis 适配层。
- `data/`：数据拉取与清洗管线的基础设施封装。
- `database/`：数据库连接管理、ORM 封装及迁移脚本。
- `di/`：轻量依赖注入容器，注解组件与生命周期管理。
- `messaging/`：与外部消息系统（如 ZeroMQ、本地 IPC）的对接。
- `monitoring/`、`notifications/`：指标采集、报警推送（邮件、Webhook 等）。
- `persistence/`：持久化抽象，支持本地文件与 DuckDB/PostgreSQL。
- `providers/`：数据提供方实现，当前重点为 `implementations/amazingdata`。
- `repositories/`：面向领域的仓储层，封装常用查询与聚合逻辑。

## 核心组件与数据结构

- `CacheProvider`、`CacheLayerConfig`：描述缓存策略、失效时间与回源流程。
- `DatabaseSessionManager`：包装 SQLAlchemy/DuckDB 会话，提供事务辅助。
- `ProviderRegistry`：登记数据提供方，实现优先级与熔断降级策略。
- `NotificationChannel`：抽象通知通道，支持批量发送与节流。
- `Repository` 基类：定义标准 CRUD/聚合接口，结合 `validators` 保证输入输出。

## 关键流程

1. `config.settings` 解析资源配置后，通过 `providers/factory` 初始化基础设施。
2. 依赖注入容器 `di.container` 注册实例，供 `core.ComponentFactory` 拉取。
3. 数据请求先命中缓存；若失败，则调用配置的 `datafeed` 提供方并回写缓存。
4. 监控组件基于 `observability` 输出来捕获错误、延迟并触发 `notifications`。
5. 持久化层统一通过仓储接口，避免业务直接操作数据库驱动。

## 扩展与集成

- 新增缓存/数据库/消息实现时，请在对应目录添加实现并更新工厂注册。
- AmazingData 的策略要求维持优先级、熔断与回退机制，扩展前务必阅读 `providers/implementations/amazingdata` 文档。
- 修改配置结构需同步更新 `settings.*.yaml.example` 与 `docs/api` 相关说明。
- 涉及外部服务调用时，必须在 `di` 中注入可替换的客户端，便于测试与故障演练。
