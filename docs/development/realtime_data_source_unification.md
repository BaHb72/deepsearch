# 实时数据源统一与能力切换方案

## 背景

- WebUI 的实时板块接口（例如 `GET /api/market/live/board-overview`）依赖 `MarketDataRealtimePipeline` 写入 Redis，再由 API
  从 `market:strength:{window}` 读取结果。当前链路完全由 AmazingData provider 驱动。
- `DataSourceManager.execute_with_fallback` 仅服务于请求式（RPC-like）调用，实时流水直接在 `ensure_market_data_runtime()`
  中创建 AmazingData provider 并长驻运行，因此无法自动降级到 AkShare / Cloudflare 等备援。
- `docs/reports/amazingdata_info_get_stock_basic_blocking.md` 指出，当 `InfoData.get_stock_basic`
  长时间阻塞时，板块成份同步无法完成，间接导致流水无数据。该报告验证了“主源阻塞导致缓存空”的实际风险。
- 业务期望拥有“按能力自动切换、可观测、可回退”的统一机制，避免单点故障并让前台明确知道当前数据源。

## 现状诊断

| 模块                                                     | 现状                                                                                                               | 问题                                                 |
|--------------------------------------------------------|------------------------------------------------------------------------------------------------------------------|----------------------------------------------------|
| `deepsearch/webui/server.py:516-604`                   | 仅 `DataProviderFactory.get_provider_async(DataSourceType.AMAZINGDATA)`，直接实例化 pipeline/runner                     | 无法引用其他数据源； AmazingData 初始化失败时直接返回空                 |
| `deepsearch/application/market_data/factory.py:78-138` | `CapitalPulseCalculator/AuctionQualityCalculator/OrderImbalanceCalculator` 的 `data_source` 被硬编码为 `"amazingdata"` | Redis 中 `data_source` 字段始终为 `amazingdata`，无法体现真实来源 |
| `MarketDataCacheWriter` & `Reader`                     | 只识别 AmazingData 生产的结构；未携带能力信息                                                                                    | 不能缓存/回放其他来源的结构化数据                                  |
| `DataSourceManager`                                    | 采用“每次调用遍历 providers”的模式，缺少流式生命周期管理                                                                               | 无法直接承担订阅、心跳、流式 back-pressure                       |
| 配置 / 文档                                                | `data_sources.fallback_order` 仅描述请求式调用顺序， README 中也默认 AmazingData 为唯一实时源                                         | 运维/前端默认以为 AkShare 会自动兜底，预期与事实不符                    |

## 目标

1. **能力建模**：把“订阅、推流、板块成份、资金指标”抽象为 Ports，消除领域层对具体 SDK 的依赖。
2. **灵活编排**：构建实时数据源 Orchestrator，能按能力和优先级选择/切换适配器，支持运行时观测与告警。
3. **数据源透明**：缓存与 API 返回值准确标记 `data_source`，空结果时也能说明来源/失败原因。
4. **文档与运维**：提供能力矩阵、切换流程、诊断脚本，降低排障成本。

## 实施计划

### Phase 0：资料补完与观测基线

1. 扩充 `docs/reports/amazingdata_info_get_stock_basic_blocking.md` 的引用，让运行团队理解该问题会导致实时流水停滞。
2. 在 README「数据源」章节注明“实时流水仅依赖 AmazingData”以及当前的风险点，作为后续变更的起点。

### Phase 1：能力矩阵文档

1. 新建 `docs/datasources/realtime_capability_matrix.md`，列出各 provider（AmazingData、AkShare、Cloudflare、QMT…）对如下能力的支持度：
   `streaming`, `snapshot`, `board_universe`, `capital_pulse`, `auction`, `order_imbalance`, `throttle`, `auth`.
2. 标注每项能力的限制（如“AkShare 仅支持轮询快照”“Cloudflare Worker 无法推流”）及对缓存的影响。
3. 作为代码改造的引用文档，后续每次适配器更新同步调整该矩阵。

### Phase 2：端口定义

1. 在 `deepsearch/ports/market_data/` 下新增或扩展以下 Protocol：
    - `RealtimeStreamPort`：统一 `subscribe/ unsubscribe / fetch_latest`。
    - `BoardUniversePort`：定义 `fetch_records` 以及增量更新接口。
    - `CapitalPulsePort` / `AuctionQualityPort` / `OrderImbalancePort`：描述指标所需的输入/输出模型，并附带 `data_source`
      字段。
2. 每个 Port 需要在文档 `docs/architecture/realtime_ports.md` 中说明契约、错误语义、back-pressure 约束。

### Phase 3：适配器落地

1. 新建 `deepsearch/adapters/market_data/` 目录，引入 `AmazingDataRealtimeAdapter` 作为第一实现，直接对接现有 SDK。
2. 设计统一的 `RealtimeAdapterCapabilities` 数据结构（例如 `TypedDict` 或 `dataclass`），在每个 adapter 中声明自身能力。
3. 预留 `AkShareRealtimeAdapter` / `CloudflareRealtimeAdapter` skeleton，内部可以先通过轮询 `DataSourceManager` 或 HTTP
   API 来提供 `fetch_latest`，待后续迭代完善。

### Phase 4：Orchestrator

1. 编写 `deepsearch/application/market_data/orchestrator.py`（命名可调整），负责：
    - 解析配置 `settings.*.yaml` > `data_sources.realtime.adapters`；
    - `alert_policy` 映射 Ops 告警策略，`failure_threshold` + `window_seconds` 决定何时触发，`channels` 对应通知通道；
    - 根据能力矩阵筛选满足需求的 adapter；
    - 维护 adapter 生命周期（init、health check、recover）；
    - 提供 `get_active_adapter()`/`switch_adapter(reason=…)` 等方法。
2. `ensure_market_data_runtime()` 改为向 orchestrator 请求当前激活 adapter，而非直接实例化 AmazingData provider。
3. 在 orchestrator 中集成监控指标（成功率、切换次数、耗时），输出到现有日志/诊断通道。

### Phase 5：计算器与缓存改造

1. `CapitalPulseCalculator` 等计算器读取 `MarketSnapshot.data_source` 并写入 `CapitalPulseEntry.data_source`；必要时更新
   `ports.market_data` 的数据模型，移除硬编码。
2. `MarketDataCacheWriter`/`Reader` 层面保持 `data_source` 字段并允许混合来源；当 fallback adapter 产生数据时，API
   端即可正确暴露真实来源。
3. `board-overview` 等 API 在 `items` 为空时，除 `DATA_SOURCE_EMPTY` 之外还应报告当前激活 adapter 及其故障原因（由
   orchestrator 提供）。

### Phase 6：配置、文档与运行手册

1. 更新 `settings.<env>.yaml`：新增 `data_sources.realtime` 节点，用于声明 adapter 列表、优先级、能力约束、告警策略。
    - `health_check_interval` �� orchestrator ̽��Ƶ�ʹ����ڲ���ͣ��Ч����
    - `alert_policy` ӳ�� Ops ��澯������ͨ�� channel ��Ӧ��䵥�����ԭ��；
    - `adapters[].options` ֧�� driver �ض��������磺`use_proxy`��`batch_size` �������޻�������ƾ�ݣ�
    - dev/test/prod/template �Ѿ�����ͬ��ʾ�������Ը�������ڲ������޸���
2. README「数据源」「运行与监控」章节同步说明启用/切换步骤，强调“流式与请求式 fallback 逻辑不同”。
3. 新增 `docs/runbooks/realtime_source_failover.md`，覆盖：
    - 手动切换 adapter；
    - 如何查看当前激活数据源（API/CLI）；
    - 典型告警及处理流程。

### Phase 7：验证与发布

1. 增加自动化测试：
    - Adapter 层单测（能力声明、失败重试）；
    - Orchestrator 多源切换集成测试；
    - API 层端到端测试（模拟主源失效后 fallback）。
2. 提供 `uv run deepsearch check-realtime` 脚本，调用 orchestrator 的健康检查，确保 CI/CD 与运维都能快速定位问题。
3. 发布时更新 CHANGELOG，提示前端“可通过响应中的 `data_source` 识别当前来源”，并建议在 UI 上展示 fallback 状态。

## 近期工作拆解

1. **文档落地**：完成 Phase 1 的能力矩阵草稿 + `realtime_ports.md` 模板，以便团队对齐术语。
2. **PoC**：在 orchestrator 中先接入 AmazingData adapter，保持功能不变但改走新架构，确保回归通过。
3. **AkShare 轮询兜底**：实现最小可用的 `AkShareRealtimeAdapter`（基于轮询 + 快照写缓存），作为 fallback 验证管线。
4. **API 透明度**：调整 `board-overview` 等接口返回 `detail.reason`，指明来自 orchestrator 的错误或 fallback 说明。

完成以上步骤后，再逐步把其它实时接口（权重榜、竞价、委差）接入新机制，最终实现真正“按能力切换”的统一体。每个里程碑都应同步更新文档和运维手册，确保信息一致。
\n### Phase 5：模块级兜底与前端切换
\n- 接口 \\/market/live/{strength|board-overview|order-imbalance|auction-quality}\\ 新增 \\source\\ 查询参数，默认 auto。兜底成功时会在 \\detail.fallback\\ 中反馈写入源、时间戳等信息。
- \\settings.*.yaml\\ 中的 \\market_data.modules.{模块}\\ 描述主源+fallback 组合，后端会在主源失效或休市时按模块自动挑选兜底源，也允许显式指定。
- 代码层面引入 \\ModuleFallbackManager\\，按需启动指定 adapter 运行一次 pipeline，保证不会常驻多条 runner。

### Phase 5：模块级兜底与前端切换

- 接口 `/market/live/{strength|board-overview|order-imbalance|auction-quality}` 新增 `source` 查询参数，默认 auto。触发兜底时会在 `detail.fallback` 中反馈写入源、时间戳等信息，便于前端提示。
- `settings.*.yaml` 的 `market_data.modules.{模块}` 描述主源与 fallback 组合。后端会在主源失效或休市时按模块自动挑选兜底源，也允许显式指定某个 adapter。
- WebUI 在资金脉冲 / 板块概览 / 委卖失衡 / 集合竞价四个卡片上渲染模块级数据源选择器，支持“自动 + 配置的 adapter”选项，并在响应出现 `detail.fallback` 时高亮提示。
- 运行时引入 `ModuleFallbackManager`，按需启动指定 adapter 运行一次 pipeline，避免为每个模块常驻多条 runner，同时暴露最小间隔和兜底状态。
