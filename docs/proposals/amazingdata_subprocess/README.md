# AmazingData 子进程隔离方案

## 背景

- 当前 `optimized` 实现在主进程直接调用 AmazingData 官方 SDK。
- 遇到网络异常或凭证错误时，SDK 会触发原生异常（如 `SystemExit`、访问冲突），导致 Web 服务整体退出。
- 项目要求保障 WebUI 和 API 可用性，避免单一数据源故障放大为系统级宕机。

## 目标

1. 将 AmazingData SDK 调用隔离到独立子进程，主进程仅通过消息通道访问。
2. 发生崩溃时快速重启子进程，保证核心服务不中断。
3. 规范化凭证、连接生命周期，以及监控、日志采集接口。
4. 与现有 `DataProviderRegistry`、`DataSourceManager` 保持兼容，可按配置在 `optimized` / `process` 两种模式间切换。

## 设计约束

- 遵循 ports/adapters 分层：新增 `ports/amazingdata_process.py` 定义协议，适配器位于 `infrastructure/providers/implementations/amazingdata`.
- 子进程需支持 Windows（spawn）与 Linux（fork）两种启动方式，避免依赖未授权的守护进程。
- 配置仍走 `settings.<env>.yaml`，新增 `implementation_mode: process` 及子进程特定参数（通信方式、超时、重启策略）。
- 与现有监控、日志体系兼容：子进程日志写入统一目录或通过主进程转发。

## 方案概述

1. **端口定义**  
   - 在 `ports/` 增加 `AmazingDataProcessPort`，声明登录、注销、行情/历史数据查询、订阅管理等接口。
   - 提供 DTO / TypedDict 约束输入输出，限制原生对象穿透领域层。

2. **子进程适配器**  
   - 编写 `process_adapter.py`：  
     - 主进程负责启动子进程（`multiprocessing.Process` 或 `asyncio.subprocess`），并保持心跳。  
     - 使用双向通信（首选 `multiprocessing.Pipe`/`Queue`，备选 ZeroMQ/Protobuf）封装请求与响应。  
     - 子进程内部加载官方 SDK，实现协议接口。  
     - 应对崩溃：主进程检测异常并在冷却时间后重启，累计失败达到阈值时上报告警。

3. **注册中心集成**  
   - 在 `DataProviderRegistry` 中新增 `implementation_mode == "process"` 的代码路径，生成 `ProcessAmazingDataProvider`。  
   - 保留原有模式以方便回退，并为 WebUI 增加模式选择项。

4. **监控与日志**  
   - 子进程输出重定向到文件（`logs/amazingdata-process.log`）或通过 IPC 回传给主进程。  
   - 增加健康检查 API，提供进程存活、重启次数等指标。

## 详细设计

### 1. 协议层（ports）

| 模块 | 说明 | 关键点 |
| ---- | ---- | ------ |
| `ports/amazingdata_process.py` | 定义 `AmazingDataProcessPort` 协议 | 统一登录、行情、订阅接口；约束输入输出类型；提供错误枚举 |
| DTO / TypedDict | 描述请求参数、响应结构 | 例如 `LoginRequest`, `QuoteResponse`，方便后续序列化与测试 |

### 2. 传输协议

- **消息结构**：  
  ```jsonc
  {
    "id": "uuid4",
    "method": "get_kline",
    "payload": { ... },
    "context": { "timeout": 5.0 }
  }
  ```
  - `id` 用于匹配响应；
  - `method` 与 port 方法一致；
  - `payload` 序列化参数；
  - `context` 扩展超时、重试等设置。

- **响应结构**：  
  ```jsonc
  {
    "id": "uuid4",
    "status": "ok|error",
    "result": { ... },
    "error": {
      "code": "SDK_TIMEOUT",
      "message": "xxx",
      "details": {}
    }
  }
  ```

### 3. IPC 方案对比

| 方案 | 优点 | 缺点 | 备注 |
| ---- | ---- | ---- | ---- |
| `multiprocessing.Pipe/Queue` | 无额外依赖、实现简单 | 同机限于单节点；阻塞式读写需包装 | 当前方案采用 |
| ZeroMQ | 跨平台、可扩展 | 需要引入 zmq 依赖、复杂度高 | 后续如需多节点再评估 |
| gRPC/HTTP | 协议成熟 | 部署较重、拉长调用链 | 不优先 |

> **当前结论**：先使用 `multiprocessing.Pipe/Queue`，满足本地一对一个进程通讯需求；当需要横向扩展或跨机器部署时，再评估引入 ZeroMQ。

### 4. 子进程生命周期

1. 主进程启动时，根据配置选择 `process` 模式；
2. `ProcessController` 负责：
   - 启动子进程（spawn/fork）；
   - 建立 IPC 通道；
   - 定时发送心跳；
   - 捕获异常和退出码，必要时重启；
   - 限制最大重启次数（如 5 次/分钟）。
3. 子进程初始化步骤：
   - 加载 SDK；
   - 登录、建立连接；
   - 进入事件循环（asyncio）处理消息队列；
   - 出现不可恢复错误时主动退出，由主进程重启。

### 5. 守护与监控

- **重启策略**：指数退避，防止短时间内频繁拉起；超过阈值后通知监控。
- **健康检查**：暴露 `/health/amazingdata-process` 接口，返回：
  ```json
  {
    "status": "running",
    "pid": 12345,
    "uptime": 120.3,
    "restartCount": 1,
    "lastError": null
  }
  ```
- **日志采集**：
  - 子进程 stdout/stderr 重定向到滚动日志文件；
  - 关键事件通过 IPC 回传，写入主进程的结构化日志（带上 `source=amazingdata-process` 标签）。

### 6. 熔断与故障注入

- 主进程收到连续错误时触发熔断，短期内直接返回备用数据源；
- 提供命令行/接口注入故障（模拟子进程崩溃、网络异常），用于测试恢复能力。

### 7. 配置项草案

```yaml
data_sources:
  providers:
    amazingdata:
      implementation_mode: process
      config:
        connection:
          host: 101.230.159.234
          port: 8600
          username: xxx
          password: yyy
        process:
          ipc: pipe            # pipe | zmq
          startup_timeout: 10  # seconds
          request_timeout: 5   # seconds
          max_restarts: 5
          restart_window: 60   # seconds
          log_path: logs/amazingdata-process.log
          env:
            AMAZINGDATA_SDK_HOME: ...
```

### 8. 回退策略

- 若子进程在启动阶段连续失败，自动回退到 `optimized` 并给出告警；
- 配置中提供 `fallback_mode` 开关，允许运维人员在运行时切换。

## 里程碑

| 阶段 | 内容 | 验收标准 |
| ---- | ---- | -------- |
| M1 | 端口定义与配置扩展 | `settings.<env>.yaml` 支持 `process` 模式；mypy/单测通过 |
| M2 | 子进程适配器原型 | 能在开发机上启动子进程、完成登录/查询、并正确返回数据 |
| M3 | Registry / DataSourceManager 集成 | WebUI 可切换模式；崩溃时主进程不退出 |
| M4 | 监控与回归测试 | 增加单/集成测试、日志采集文档，完成性能与异常场景验证 |

## 风险与待决事项

- IPC 方案选择：Pipe/Queue 简单但扩展性有限，ZeroMQ 需额外依赖；需结合现有消息总线评估。
- 子进程状态持久化：需确认订阅、缓存等状态是否需要主进程同步保存。
- 安全与凭证管理：将密码只在子进程持有可能更安全，但需要界定配置刷新策略。
- 部署与运维：需更新启动脚本、容器化配置，确保子进程生命周期被监控。

## 下一步

1. 与相关模块负责人确认接口需求与测试覆盖范围。  
2. 评估 IPC 与重启策略，产出技术决策记录。  
3. 实现 M1/M2，提交 PoC 供评审，再推进后续里程碑。

## 架构视图

### 组件关系

- **主进程**
  - `ProcessAmazingDataProvider`（Registry 返回）
  - `ProcessController`（管理子进程生命周期）
  - `IPCClient`（封装请求/响应）
  - `MetricsEmitter`（推送指标到监控系统）
- **子进程**
  - `ProcessServer`（事件循环 + 消息分发）
  - `SDKFacade`（包装 AmazingData 官方 SDK）
  - `SessionManager`（管理登录状态、心跳、订阅）
  - `ResultEncoder`（把 SDK 返回值转换为可序列化结构）

### 数据流（成功路径）

1. 主进程调用 `ProcessAmazingDataProvider.get_kline(...)`；
2. 组装请求消息并写入 IPC；
3. 子进程监听到消息，通过 `SDKFacade` 发起真实调用；
4. 结果经 `ResultEncoder` 标准化后写回 IPC；
5. 主进程收到响应，转换为业务层所需的 DTO，返回给调用方；
6. 期间 `MetricsEmitter` 记录耗时、成功率等指标。

### 数据流（失败路径）

- 如果子进程在超时时间内未响应，主进程：
  1. 记录一次超时；
  2. 向健康管理模块上报；
  3. 达到阈值后触发重启，同时将请求错误回传业务层（带错误码 `PROCESS_TIMEOUT`）。
- 若子进程崩溃：
  1. `ProcessController` 捕获退出事件；
  2. 记录崩溃原因、重启次数；
  3. 在退避时间之后拉起新进程；
  4. 如果重启失败次数超过 `max_restarts`，进入熔断状态，将错误上报并停止进一步重启。

## 错误处理规范

| 场景 | 错误码 | 主进程行为 | 子进程行为 |
| ---- | ---- | ---------- | ---------- |
| 请求参数非法 | `INVALID_ARGUMENT` | 即刻返回错误，不写 IPC | 不涉及 |
| SDK 调用抛错（可恢复） | `SDK_ERROR` | 读取错误信息，按配置重试 | 记录日志，保持连接 |
| SDK 调用抛错（致命） | `SDK_FATAL` | 触发重连/重启流程 | 主动退出，让主进程重启 |
| 子进程无响应 | `PROCESS_TIMEOUT` | 中断请求，统计超时 | 如仍存活，继续处理下一条消息 |
| IPC 断开 | `IPC_DISCONNECTED` | 立即重启子进程 | 退出自身 |

## 配置管理

- 配置源：`settings.<env>.yaml` + `config/services/amazingdata_process.yaml`（可选）。
- 动态刷新：通过 WebUI 更新后写回 YAML，`ProcessController` 读取新配置并决定是否重启子进程。
- 机密字段（密码等）仍走现有加密/隐藏逻辑，仅在子进程内解密。

## 部署与运维

- **容器化**：需确保镜像内存在启动子进程所需的 SDK 依赖；EntryPoint 不变。
- **systemd / Supervisor**：若部署在裸机，可通过服务管理器监控主进程；子进程由主进程自管。
- **日志轮转**：建议使用 `logging.handlers.RotatingFileHandler` 或接入现有 ELK/Graylog。
- **指标导出**：新增 Prometheus 指标，如 `amazingdata_process_restart_total`, `amazingdata_process_uptime_seconds`。

## 安全考量

- IPC 通道仅在本地主机使用，避免开放网络端口。
- 子进程执行环境最小化：仅加载必要包，禁用未使用的模块。
- 凭证传递通过环境变量或安全文件，可考虑对敏感字段做一次性解密后驻留内存。

## 测试计划

1. **单元测试**
   - `ports` 层接口契约；
   - IPC 客户端/服务端消息序列化；
   - ProcessController 重启策略。
2. **集成测试**
   - 启动真实子进程，模拟成功/失败请求；
   - 注入网络异常、SDK 抛错；
   - 验证重启 & 熔断逻辑。
3. **压力测试**
   - 并发行情拉取、订阅场景；
   - 子进程稳定性 & 资源占用。
4. **故障演练**
   - 手动杀死子进程；
   - 删除 IPC 通道；
   - 注入无效凭证。

## 推广计划

| 阶段 | 目标 | 行动项 |
| ---- | ---- | ------ |
| Beta | 内部测试 | 在开发环境启用 `process`，收集日志、性能指标 |
| RC | 小规模部署 | 在预发环境灰度，与现有 `optimized` 对比 |
| GA | 全量启用 | 默认切换到 `process`，保留回退配置 |

## 风险与缓解

| 风险 | 影响 | 应对 |
| ---- | ---- | ---- |
| 子进程重启震荡 | 性能下降、数据延迟 | 指数退避、熔断机制、报警 |
| IPC 阻塞导致主进程卡死 | 请求堆积 | 使用非阻塞 IO + 超时控制 |
| SDK 升级兼容性问题 | 查询失败 | 在子进程内做版本检测，可回退到优化模式 |
| 部署环境差异（Windows/WSL） | 子进程无法启动 | 在 CI 中覆盖两种平台，提供文档指引 |

## 责任分工（建议）

- **后端 Framework**：子进程控制器、IPC 客户端、注册中心改造；
- **数据源团队**：SDKFacade 封装、业务接口适配；
- **DevOps**：日志、监控、部署脚本调整；
- **QA**：测试用例设计与执行、故障演练；
- **产品/运营**：灰度计划与反馈收集。

## 未决问题

1. 是否需要支持多子进程并行提升吞吐？（当前计划为单实例）
2. IPC 选型最终是否扩展为 ZeroMQ（满足未来多实例需求）？
3. 子进程是否需要独立的配置热更新能力？
4. 想要复用现有任务队列（如 Redis Stream）作为消息通道吗？
5. 是否引入安全沙箱（如限制子进程权限）？


