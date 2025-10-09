# 使用虾推啥实现微信与 Bark 消息推送实施计划

## 1. 背景
- 当前 DeepSearch 平台尚未提供面向微信或移动端的即时消息推送能力，策略告警和系统通知只能通过日志、WebUI 或邮件查看。
- 业务方提出需求：通过虾推啥（xtuis.cn）提供的 HTTP 接口，向微信和 iOS Bark 终端推送文本通知，以便在行情波动或任务异常时第一时间触达。
- 同时需要对不同类别的消息设置推送额度限制，避免频繁通知干扰终端用户。

## 2. 目标
- 集成虾推啥平台的微信与 Bark 推送接口，提供统一的消息发送服务。
- 支持按消息类别配置推送额度（条数限制 + 时间窗口），触达上限时自动阻止并记录原因。
- 在后端开放 API（FastAPI 路由 `/api/notification/...`），供前端或其他子系统触发推送，并保留扩展钩子。
- 提供最小可用的监控与日志记录能力，便于排查推送失败原因。

## 3. 范围与非目标
### 3.1 范围
- 新增基础通知服务接口（Domain Service Interface）。
- 在 `deepsearch/infrastructure` 内实现虾推啥客户端与调度器。
- 后端 WebUI 服务新增推送 API 与额度校验逻辑。
- 完成配置模型扩展、示例文件更新与文档说明。

### 3.2 非目标
- 本阶段不实现富文本、图片或模板消息推送，仅支持 `text` / `desp` 字段。
- 不实现消息持久化历史列表，仅提供实时发送与日志记录。
- 不接入除虾推啥外的其他推送渠道。

## 4. 关键约束与假设
- 保持单机部署架构，不依赖外部队列或分布式组件；额度限制使用内置缓存或本地持久化方案即可。
- 推送操作默认异步执行，但需提供同步阻塞选项以便在脚本场景中调用。
- 系统以 Python 3.13 + `uv` 工具链为基线，禁止直接新增未审查的第三方依赖；优先复用 `httpx`。
- 所有敏感配置（token）通过 `settings.{env}.yaml` 读取，不写死在代码中。

## 5. 架构设计
### 5.1 组件结构
| 图层 | 组件 | 说明 |
|------|------|------|
| Domain | `INotificationService`（待新增） | 抽象通知接口，支持多渠道、类别和额度控制。|
| Infrastructure | `XtuisClient` | 封装虾推啥 HTTP 请求、错误处理与重试。|
| Infrastructure | `NotificationQuotaGuard` | 使用 `cache_manager` / 本地 KV 记录各类别推送次数，支持时间窗口重置。|
| Application | `NotificationService` | 组合 `XtuisClient` 与 `NotificationQuotaGuard`，提供 `send_wechat`、`send_bark`、`dispatch` 等方法。|
| API | `NotificationRouter` | FastAPI 路由，验证请求参数并调用服务；暴露额度查询接口。|

### 5.2 交互流程（示例：发送微信告警）
1. 上层模块（如策略引擎或 WebUI）调用 `NotificationService.dispatch(channel="wechat", category="alert", title, body)`。
2. `NotificationService` 通过 `NotificationQuotaGuard` 检查在配置的时间窗口内是否超过额度：
   - 若超过，记录 warning 日志并返回错误码（例如 `quota_exceeded`）。
   - 若未超过，计数 +1，进入下一步。
3. 调用 `XtuisClient.send_wechat(token, title, body)` 组装 URL：`https://wx.xtuis.cn/{token}.send?text=...&desp=...`。
4. 接收响应，解析状态码；失败时记录日志并按策略重试（如 3 次指数退避）。
5. 将成功/失败状态返回调用方，并写入结构化日志。

## 6. 配置方案
- 新增 `deepsearch/config/models/notifications.py`（pydantic 模型），包含：
  - `enabled: bool`
  - `wechat_token: str`
  - `bark_token: Optional[str]`
  - `base_urls`: 可选覆盖默认域名
  - `categories`: 映射，键为类别名，值为额度配置（`max_per_window`, `window_seconds`, `channels`）。
- 在 `settings.template.yaml` / `.example` / `.dev` / `.prod` 新增 `notifications` 节点，token 使用 `your_xtuis_token` 占位。
- 更新 `deepsearch/config/settings.py` 与 `Settings` 汇总模型，确保加载新配置。
- 若涉及 CLI 环境变量覆盖，文档中列出 `DEEPSEARCH_NOTIFICATIONS__...` 栈式路径。

## 7. 类别额度限制策略
- 额度计数采用 `cache_manager` 提供的多级缓存（内存 + 可选 Redis）。
- 计数键格式：`notification:{channel}:{category}:{window_start}`。
- `NotificationQuotaGuard` 负责：
  - 计算当前窗口起始时间（向下取整到 `window_seconds`）。
  - 缓存不存在时写入 1 并设置 TTL=`window_seconds`。
  - 当计数 ≥ `max_per_window` 时拒绝推送并返回剩余解冻时间。
- 对于需应用全局上限的场景，支持在配置中定义 `category="__global__"`，初始化时自动加载。

## 8. API 设计
- 新增 FastAPI 路由模块 `deepsearch/webui/api/endpoints/notifications/push.py`，注册到 `/api/notification`。
- 端点规划：
  1. `POST /api/notification/send`：请求体包含 `channel`, `category`, `title`, `content`，返回发送结果与额度信息。
  2. `GET /api/notification/quotas`：返回当前各类别剩余额度，便于前端展示。
- 文档更新：
  - `docs/api/README.md` 增加新域概述。
  - `FRONTEND_API_REGISTRY.md` 与 `BACKEND_API_REGISTRY.md` 登记接口。
  - `API_MAPPING.md` 记录前后端函数映射。
  - 变更完成后必须运行 `python tools/generate_api_documentation.py`。

## 9. 日志与监控
- 在 `NotificationService` 中使用 `loguru` / `logging` 记录发送明细（channel, category, status, latency）。
- 若额度耗尽，写入 `warning` 级别日志，便于后续统计。
- 预留钩子给 `ProviderHealthMonitor` 或未来监控系统接入（例如：推送连续失败触发告警）。

## 10. 安全与合规
- Token、私有服务器地址仅存于配置文件或环境变量，避免写入仓库。
- 对外 API 需沿用现有认证中间件；参考 `webui/api/middleware` 中的鉴权逻辑。
- 对外响应避免暴露真实 token 或内部错误堆栈。

## 11. 实施步骤
1. **接口定义**：在 Domain 层新增 `INotificationService` 与数据模型；编写最小单元测试。
2. **基础设施实现**：
   - 创建 `XtuisClient`（封装 httpx 调用、重试、异常）。
   - 创建 `NotificationQuotaGuard` 并整合缓存。
   - 实现 `NotificationService`，满足接口契约。
3. **配置接入**：扩展 `config/models`、`settings` 文件与加载逻辑；更新 `.example` 模板。
4. **API 层**：新增 FastAPI 路由、请求模型、响应模型、依赖注入。
5. **文档与脚本**：更新 `docs/api`、新增开发说明；运行 `python tools/generate_api_documentation.py`。
6. **测试**：编写单元测试（推送成功、额度限制、异常重试、配置缺失），并补充 API 集成测试。
7. **回归与联调**：运行 `uv run pytest`、`ruff check`、`black`、`isort` 等校验。

## 12. 测试计划
- **单元测试**：
  - `tests/unit/infrastructure/test_xtuis_client.py`：校验请求参数和错误处理。
  - `tests/unit/infrastructure/test_notification_quota_guard.py`：验证窗口计算与限制行为。
  - `tests/unit/services/test_notification_service.py`：覆盖成功、失败、额度超限分支。
- **集成测试**：
  - `tests/api/test_notification_api.py`：使用 httpx ASGI 客户端模拟调用。
- **手动验证**：
  - 配置测试 token（若有沙箱），执行 `uv run python -m deepsearch tools send-notification ...`（可选 CLI）。

## 13. 风险与缓解
- **第三方可用性**：虾推啥服务不稳定导致推送失败 —— 通过重试与日志监控及时报警。
- **额度配置错误**：窗口或上限配置缺失 —— 提供默认值与配置校验，启动时抛出异常。
- **消息风暴**：系统异常反复推送 —— 额度限制 + 可选全局冷却策略。
- **安全风险**：token 泄露 —— 配置文件模板标注敏感字段，提交前执行 `git grep -i "password\|secret\|token" -- ':(exclude)*.example'` 自检。

## 14. 时间排期（预估 1.5 周）
| 阶段 | 内容 | 工期 |
|------|------|------|
| 第 1-2 天 | 接口设计、配置模型与单元测试用例草拟 | 2 天 |
| 第 3-5 天 | 实现客户端、额度守卫、服务层，并通过单测 | 3 天 |
| 第 6 天 | 接入 FastAPI 路由、编写 API 文档/测试 | 1 天 |
| 第 7 天 | 自测、文档生成、代码规范检查 | 1 天 |

## 15. 交付与验收
- 代码合并前提供：
  - 功能 PR（遵循 Conventional Commits，例如 `feat: add xtuis notification service`）。
  - 更新后的配置示例与 API 文档。
  - 运行日志与测试结果说明。
- 验收标准：
  - 本地环境可成功将消息推送到绑定的微信/Bark 设备。
  - 额度限制在手动压测下工作正常。
  - 所有新增单测/集成测通过，CI 无报错。

