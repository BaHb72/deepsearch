# AkShare 数据源代理整合方案

## 背景
DeepSearch 当前通过 `DataSourceType` 将 `akshare` 与 `cloudflare_proxy` 视为两个独立数据源。AkShare 直连实现会在初始化时挂载 Cloudflare Worker 代理补丁，而 `cloudflare_proxy` 数据源对应的配置与状态监控则仅用于标记代理是否启用。这种拆分导致：

- 日志与监控面板出现“未启用 cloudflare_proxy，跳过初始化”之类的信息，容易误导为 AkShare 数据源不可用。
- 同一数据源的不同访问路径被拆成两个实体，配置迁移与优先级控制复杂化。
- WebUI/监控需要维护额外的数据源项，但底层仍是 AkShare 单实例。

## 现状分析
- `DataSourceType` 中存在 `AKSHARE` 与 `CLOUDFLARE_PROXY` 两个枚举值。
- `DataSourceManager` 根据 `data_sources.providers` 或旧版 `data_providers` 配置分别注册它们，初始化时若 `cloudflare_proxy.enabled=false` 会直接跳过。
- `deepsearch.utils.network.akshare_proxy.patch_akshare()` 会读取 `cloudflare_workers` 配置，如果存在 Worker URL 则自动启用代理。AkShare 直连实现 `akshare_direct` 无论 `cloudflare_proxy` 是否启用都会调用补丁函数。
- WebUI 与监控代码包含 Cloudflare Proxy 数据源项，用于显示启用状态与 Worker URL。

## 痛点
1. 日志语义混淆：明明只有 AkShare 一个数据源，却出现“Cloudflare Proxy 未启用”导致部分用户误判。
2. 配置冗余：需要同时维护 `cloudflare_proxy` 与 AkShare 配置，实际生效的仍然是 AkShare 的补丁逻辑。
3. 扩展阻碍：若未来引入其他代理模式，需要继续堆叠虚拟数据源，违背“单机、单实例”的整体约束。

## 目标
- 将 Cloudflare Worker 代理归并为 AkShare 的访问模式，保留单一 `AKSHARE` 数据源实体。
- 通过 AkShare Provider 内部配置灵活切换直连与代理，并对外披露当前模式与代理信息。
- 清理冗余的 `cloudflare_proxy` 数据源，确保日志、监控、配置结构一致。

## 设计方案
### 架构调整
1. **枚举与注册**：删除 `DataSourceType.CLOUDFLARE_PROXY`，`DataSourceManager` 仅对 `AKSHARE` 注册与初始化。
2. **配置结构**：在 AkShare 配置中新增 `proxy` 或 `mode` 字段，例如：
   ```yaml
   data_sources:
     providers:
       akshare:
         enabled: true
         priority: 2
         mode: worker  # 可选 direct / worker
         proxy:
           enabled: true
           worker_url: https://xxx.workers.dev
           timeout: 15
   ```
   保留 `cloudflare_workers` 全局配置作为默认值；当 `proxy.worker_url` 为空时回退到全局或直连。
3. **Provider 行为**：`akshare_direct` 在 `initialize()` 内读取 `proxy` 参数：
   - `mode=worker` 或 `proxy.enabled=true`：调用 `patch_akshare()` 并记录 Worker URL。
   - `mode=direct`：跳过补丁并输出“AkShare 直连模式”。
4. **监控输出**：`DataSourceManager` 与监控模块在状态信息里增加 `access_mode`, `worker_url`, `proxy_enabled` 字段。
5. **前端展示**：WebUI API 与页面仅保留 AkShare 一项，同时显示模式与代理信息。

### 兼容策略
- 启动时检测旧配置 cloudflare_proxy.enabled=true，自动转换为 akshare.proxy.enabled=true 并给出一次性警告提示。
- 对旧版 `data_providers.cloudflare_proxy` 字段做兼容读取，写入 AkShare 配置后在日志中提醒用户更新配置文件。
- 保留 `cloudflare_workers` 配置项，作为 AkShare 代理的全局默认值。

## 实施步骤
1. **代码重构**
   - 更新 `DataSourceType` 枚举与所有引用，删除 `CLOUDFLARE_PROXY`。
   - 调整 `DataSourceManager` 注册、初始化与状态输出逻辑。
   - 扩展 `AkShareDirectProvider` 配置解析与初始化流程，区分直连/代理模式。
   - 修改监控、WebUI API 的数据结构。
2. **配置迁移**
   - 更新 `settings.*.yaml.example`、`settings.template.yaml` 等模板，移除顶级 `cloudflare_proxy` 节点，新增 `akshare.proxy`。
   - 在文档中提供迁移指南，列出旧字段到新字段的映射。
3. **文档同步**
   - 更新 `docs/api` 相关文件，运行 `python tools/generate_api_documentation.py`。
   - 补充 `docs/operations`、`docs/architecture`、`docs/development` 中的数据源管理章节。
4. **测试验证**
   - 编写或更新单元与集成测试，覆盖直连模式、代理模式及配置兼容路径。
   - 验证日志信息与 WebUI 展示是否与新结构一致。
   - 运行既有质量检查：`ruff`, `black`, `isort`, `mypy`, `bandit`, `pytest`。

## 风险与缓解
- **遗留引用**：删除枚举值可能导致未更新的模块报错，需全局检索 `cloudflare_proxy` 并确认用途。
- **配置缺失**：若迁移脚本未覆盖用户自定义配置，可能导致代理失效；应用启动时应输出明确告警并使用直连兜底。
- **用户认知转换**：需要在发布说明和文档中强调“AkShare 现包含代理模式”，避免误认为功能被移除。

## 后续工作
1. 评估是否为 AkShare 增加更多代理模式（如企业网关），复用同一配置结构。
2. 在监控大屏中加入 AkShare 请求统计（直连/代理请求次数、失败率），便于观测代理效果。
3. 根据实施结果更新 `docs/testing`，记录针对 AkShare 的测试覆盖点。
4. 计划在下一个发布版本说明中突出本次变更及配置迁移步骤。
