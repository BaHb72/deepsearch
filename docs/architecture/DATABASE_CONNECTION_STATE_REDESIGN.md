# 数据库启用与连接状态重新设计方案

## 背景
DeepSearch 的数据库管理模块需要同时处理“配置启用状态”和“运行时连接状态”。目前前端页面会在用户激活某个连接后展示“已启用”标签，但真实的数据库引擎可能因为 `auto_connect=false`、密码缺失、网络异常等原因仍处于未连接状态。该不一致导致运维同学误判数据库是否可用，也使得自动化脚本无法依赖接口判断。为消除歧义，需要一份新的设计方案，以规范状态模型和交互流程。

## 现状综述
- **配置维度**：`/system/database/connections` 接口维护的 `DatabaseConnection.enabled` 只表示该配置是否写入 `settings.yaml`，调用激活接口会无条件写入 `True`。
- **运行维度**：`/api/database/status` 会调用运行时组件 (`DatabaseComponent.is_connected()`) 来判断真实连接情况，但前端当前仅以一个布尔字段映射“已连接/未连接”。
- **前端处理**：在 `DatabaseConfig.tsx` 中，开关采用 `Boolean(record.is_active || record.enabled)` 判定展示文案，因此即使后端未连上也会显示“已启用”。
- **日志反馈**：后台在 `auto_connect=false` 场景只记录“数据库组件已初始化（未连接）”，缺少结构化状态说明。

## 问题痛点
1. **语义混淆**：启用状态与连接状态复用一个布尔，无法准确表达“已配置但未连上”“正在尝试连接”“因错误断开”等细分情形。
2. **接口不对齐**：前后端使用的字段含义不一致，同步场景（如切换主库）时需要额外读取日志或手动测试确认。
3. **缺乏状态追踪**：没有可靠的最近连接时间、错误原因等元数据，问题复现和报警难以自动化。
4. **操作链条割裂**：激活、测试、连接三个动作之间没有统一的状态机，重试逻辑由各层自行实现，增加维护成本。

## 设计目标
- 明确定义“启用（Activation）”与“连接（Connectivity）”两个维度，分别暴露状态、元数据与操控入口。
- 所有 API 均返回一致的结构化状态，便于前端、脚本和监控复用。
- 支持精细化过渡态（如 `connecting`、`error`、`disabled`），并记录最近成功连接时间、失败原因等辅助信息。
- 统一后端状态机与事件流，确保激活/停用/重连流程有可追踪的生命周期。
- 保持向后兼容：旧字段仍返回，但标记为待废弃，给予迁移窗口。

## 核心设计
### 状态模型
新增双层状态结构，覆盖配置与运行两个维度：

| 维度 | 字段 | 取值示例 | 含义来源 |
| --- | --- | --- | --- |
| Activation | `activation.state` | `active` / `inactive` / `pending` / `error` | 是否写入配置、是否为默认连接及写入结果 |
| Activation | `activation.enabled` | `true/false` | 兼容旧布尔字段，等价于 `state in {active, pending}` |
| Activation | `activation.updated_at` | `2025-09-23T08:30:00Z` | 最近一次写入配置的时间 |
| Activation | `activation.error` | `写入 settings.yaml 失败` | 配置落盘异常说明 |
| Connectivity | `connectivity.state` | `connected` / `connecting` / `disconnected` / `error` | 运行态真实连接情况 |
| Connectivity | `connectivity.last_success_at` | `2025-09-23T08:32:15Z` | 最近一次握手成功时间 |
| Connectivity | `connectivity.last_error` | `password required` | 最近一次失败原因 |
| Connectivity | `connectivity.retrying` | `true/false` | 是否有后台自动重试任务 |

旧字段兼容策略：
- `enabled` → 映射 `activation.enabled`，并在响应中加入 `deprecated: true` 提示。
- `connected` → 映射 `connectivity.state === 'connected'`。
- `status` → 保留，但值改为 `activation.state` 与 `connectivity.state` 的组合，如 `active_connected`、`active_error`。

### 生命周期状态机
1. **激活流程**：
   - 前端触发 `POST /system/database/connections/:id/activate`。
   - 后端写入配置（`activation.state=pending`），成功后记为 `active` 并触发事件 `database_activation_changed`。
   - 若 `connect_immediately=true`，调度运行态连接操作，并将 `connectivity.state` 置为 `connecting`，最终落在 `connected` 或 `error`。
2. **停用流程**：
   - `POST /system/database/connections/:id/deactivate`；配置写入成功后 `activation.state=inactive`。
   - 若请求携带 `disconnect=true`，后台调用断开逻辑，`connectivity.state` → `disconnected`。
3. **运行态监控**：
   - 数据库组件提供 `register_status_listener`，在连接成功/失败时写入状态仓库。
   - 后端新增定时健康检查（沿用 `health_check_async`），异常时将 `connectivity.state=error` 并附带 `last_error`。
4. **重连策略**：
   - 新增 `POST /system/database/connections/:id/reconnect`，先校验 `activation.state=active`，然后进入 `connecting` → `connected/error`。

### 数据流对齐
- **配置中心**：`database_manager.py` 负责读写 YAML；新增 `ActivationStatusStore` 缓存最后一次写入结果，减少重复 IO。
- **运行时引擎**：`DatabaseComponent` 在 `connect_async`、`disconnect_async`、`health_check_async` 中统一向 `ConnectivityRegistry` 上报状态。Registry 持久化至 Redis（可选）或内存 + checkpoint 文件（默认）。
- **API 出口**：
  - `/system/database/connections` 返回合并后的 Activation + Connectivity，供配置页列表使用。
  - `/api/database/status` 侧重主库连接，保留现有字段并嵌入统一结构，便于监控面板复用。
  - `/api/monitoring/database/summary`（新接口，待补）可提供系统级统计，如激活连接数量、连接成功率。

### 前端改造
- **数据模型**：在 `database.store.ts` 的 `normalizeConnection` 中解析新结构，分别存入 `activation`、`connectivity` 字段；旧布尔字段仅用于兼容，标注为只读。
- **UI 展示**：
  - 列表中拆分“启用状态”与“连接状态”两列；使用 Tag/Badge 展示状态机取值。
  - 开关组件仅绑定 `activation.state`，不会因为连接失败自动回滚；若连接失败，在“连接状态”列显示错误标签，并允许用户点击“查看详情”。
  - 新增“最近成功时间”“最近错误信息”悬浮提示，便于运维定位。
- **交互流程**：
  - 激活后自动调用 `reconnect`，根据响应更新 `connectivity.state`。
  - 连接失败时，提供“重试连接”“编辑凭据”快捷入口。

### 后端实现要点
1. **状态仓库抽象**：新增模块 `deepsearch/infrastructure/persistence/runtime_state/database_status_store.py`：
   - 方法：`save_activation_status(id, status)`, `save_connectivity_status(id, status)`。
   - 默认实现基于内存 + 原子写文件（`data/runtime/database_status.json`）。必要时可切换 Redis。
2. **组件事件**：为 `DatabaseComponent` 添加事件钩子：`on_connected`, `on_disconnected`, `on_error`，调用者负责写入 `ConnectivityRegistry`。
3. **API 响应模型**：使用 Pydantic 定义 `ActivationStateSchema`、`ConnectivityStateSchema`，避免散落的 dict。
4. **向后兼容**：在响应 JSON 中保留旧字段，同时在 `docs/api/API_MAPPING.md` 标注迁移计划；右侧加 `"deprecated": {"enabled": true}` 之类描述。
5. **日志格式化**：统一使用结构化日志：`logger.info("database.connected", connection_id=id, latency=xxx)`，方便搜集。

### 配置与自动化
- 默认 `database.main.auto_connect` 改为根据激活记录动态写入：激活时按用户选择更新，停用时恢复为 `false`。
- 在 `settings.*.yaml.example` 中补充新字段示例，说明 `activation` / `connectivity` 将在运行时生成，不需要手动维护。
- 提供 `python tools/database_status_cli.py` 用于命令行查看状态，方便排障。

## 迁移策略
1. **阶段一（兼容期）**：实现新字段，旧字段继续返回；前端只读使用旧字段，但逐步迁移视图展示。
2. **阶段二（切换期）**：前端完全改用新字段；API 对旧字段加告警 header `X-Deprecated-Fields`。
3. **阶段三（收尾期）**：删除旧字段支持，更新文档、脚本文档。

配置迁移：激活列表持久化文件新增字段时需判空，首次读取旧文件时补写默认状态（`activation.state='active' if enabled else 'inactive'`）。

## 风险与缓解
- **状态不同步风险**：若状态仓库写入失败可能导致前后端看到的状态不一致。缓解：写入失败时回滚到内存状态并返回错误，让前端提示重试。
- **性能开销**：频繁写状态可能影响 IO，使用缓存和批量落盘策略（例如 1 秒内合并写）。
- **兼容性**：外部脚本读取旧字段时可能出现异常，需提前发布迁移公告，并在 API 文档中增加“废弃计划”。
- **安全性**：记录错误信息时避免包含明文密码，仅保留高层描述。

## 验证计划
1. **单元测试**：为状态仓库、事件监听和 API 序列化添加测试；覆盖连接成功/失败、激活失败等分支。
2. **集成测试**：利用 `tests/api` 添加场景：激活 → 断开 → 重连，验证状态机变更。
3. **端到端测试**：在 dev 环境跑 `uv run python -m deepsearch run` 与 WebUI 手动验证开关/重试逻辑。
4. **回归检查**：执行 `python scripts/run_all_tests.py --quick`，确保无回归。

## 开发工作拆解
1. 后端：实现状态仓库、改造 `database_manager.py` 与 `database.py`、更新日志与文档。
2. 前端：重构 store 模型、调整列表渲染、增加状态详情组件、更新 API 调用。
3. 文档：更新 `docs/api/BACKEND_API_REGISTRY.md`、`docs/api/API_MAPPING.md`；执行 `python tools/generate_api_documentation.py`。
4. 运维工具：新增 CLI，更新 `docs/operations` 中的排障指南。

## 附录：示例响应
```json
{
  "id": 1,
  "name": "交易主库",
  "activation": {
    "state": "active",
    "enabled": true,
    "updated_at": "2025-09-23T08:30:00Z"
  },
  "connectivity": {
    "state": "error",
    "last_success_at": "2025-09-23T07:59:12Z",
    "last_error": "password required",
    "retrying": false
  },
  "deprecated": {
    "enabled": true,
    "connected": false,
    "status": "active_error"
  }
}
```
