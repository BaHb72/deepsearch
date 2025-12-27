# 市场行情模块架构草案 v1

## 1. 模块定位与边界

- **目标**：围绕 AmazingData 提供的 Level‑1 实时快照与日频接口，构建 DeepSearch 内部的“市场行情洞察”域，覆盖实时资金脉冲、盘口质量、ETF
  溢价、两融方向、供给约束与（可选）外部资产映射。
- **输入**：`AmazingDataProcessPort` 暴露的订阅/查询能力；历史/事件类 REST 接口；内部板块/概念映射表。
- **输出**：以 `docs/modules/market_data/api_contract_v4.yaml` 约定的 REST API 为主，以及供前端订阅的事件流（后续扩展）。
- **边界**：领域层仅依赖新建的 `market_data` 端口协议，不直接触达 `infrastructure.providers`；跨域协作（策略、预警）通过消息总线或已有
  API 协议完成。

## 2. 目录规划

| 层级      | 目录建议                                                                           | 说明                                                  |
|---------|--------------------------------------------------------------------------------|-----------------------------------------------------|
| 领域层     | `deepsearch/domain/market_data/`                                               | 定义资金脉冲、盘口质量、ETF、两融、供给约束等值对象与聚合根，全部使用 `dataclasses`。 |
| 端口层     | `deepsearch/ports/market_data/`                                                | 声明各子域所需 Protocol（实时订阅、指标计算、日频拉取、外部资产映射）。            |
| 应用层     | `deepsearch/application/market_data/`                                          | 用例服务：实时处理（流式）、批处理（调度）、指标装配与缓存协调。                    |
| 适配器层    | `deepsearch/infrastructure/providers/implementations/amazingdata/market_data/` | 接入 AmazingData SDK，负责 DTO ↔️ 实体转换、节流与重试。            |
| 缓存层     | `deepsearch/infrastructure/cache/market_data/`                                 | 复用 Redis/DuckDB 存储实时与日频快照，提供滑窗查询。                   |
| Web API | `deepsearch/webui/api/market_data/`                                            | FastAPI 路由、Pydantic Schema（与 OpenAPI 契约一致）。         |
| Worker  | `deepsearch/workers/market_data/`                                              | 竞价/日频调度任务、外部资产协同任务。                                 |
| 文档 & 测试 | `docs/modules/market_data/`（本目录）、`tests/market_data/`                          | 文档记录、单元/集成/契约测试。                                    |

## 3. 端口设计

全部端口以 `Protocol` + `TypedDict/dataclass` 组成，不引入第三方实现。

| Port 名称                   | 能力                             | 备注                                                                   |
|---------------------------|--------------------------------|----------------------------------------------------------------------|
| `MarketStreamPort`        | 订阅股票/ETF Level‑1 快照，推送/拉取滑窗数据。 | 依赖子进程 IPC；提供 `subscribe`, `unsubscribe`, `collect_snapshot(window)`。 |
| `CapitalPulsePort`        | 在滑窗内计算资金强度/速度/加速度；支持板块聚合。      | 纯计算，不直接调用 SDK。                                                       |
| `AuctionQualityPort`      | 集合竞价阶段识别与评分。                   | 依赖 `MarketStreamPort` 的竞价数据缓冲。                                       |
| `OrderImbalancePort`      | 计算 OBI/EIS/NTM、封单强度。           | 提供高频榜单与个股追踪。                                                         |
| `ETFReferencePort`        | 维护 ETF 溢价率、资金速度、概念代理映射。        | 需持有 ETF ↔ 概念映射表（配置）。                                                 |
| `MarginFlowPort`          | 拉取两融 T‑1 数据并与实时脉冲对齐。           | 暴露 `fetch_summary`, `fetch_detail`, `persist`.                       |
| `SupplyConstraintPort`    | 解禁/质押/分红/配股事件聚合与承载力评分。         | 触发日频任务更新缓存。                                                          |
| `StylePreferencePort`     | 财务/业绩风格指标计算。                   | 以标准化三表数据为输入。                                                         |
| `ExternalOverlayPort`（可选） | 外部资产（期货） ↔ A 股行业映射与相关度计算。      | 仅当启用期货接口时加载。                                                         |
| `ConceptAssociationPort`  | 概念/板块关联、热点迁移图谱。                | 使用缓存的分钟序列，本地计算。                                                      |

## 4. 适配器规划

- **订阅适配器**：`amazingdata_market_stream_adapter.py`
  - 包含连接管理、节流（5–10s）、竞价特化（2–5s）、异常重连。
  - 输出统一的 `MarketSnapshot` dataclass（时间戳、五档、成交额、笔数等）。
- **ETF/两融/事件适配器**：按接口拆分为 `etf_adapter.py`、`margin_adapter.py`、`corporate_event_adapter.py`，每个适配器仅封装
  SDK 调用与字段清洗。
- **外部资产适配器**（可选）：`futures_overlay_adapter.py`，按夜盘规则切分序列。
- **缓存适配器**：针对 Redis（实时榜单）与 DuckDB（分钟历史）的存储读写封装，复用既有基础设施模块。

所有适配器通过依赖注入（FastAPI Depends / 应用服务构造函数）向上层提供端口实现，禁止在领域层直接引用。

## 5. 应用服务与数据流

1. **实时流水线**
    - Worker 启动后通过 `MarketStreamPort.subscribe` 订阅股票、ETF。
    - 快照进入 `CapitalPulseService`（实现 `CapitalPulsePort`），计算资金强度/速度/加速度并写入实时缓存 →
      `/api/market/live/strength`。
    - 同步触发 `OrderImbalanceService` 与 `LimitStrengthService`，产出盘口失衡、封单榜单。
    - 若处于竞价窗口，`AuctionQualityService` 额外计算竞价质量。
2. **日频/批处理**
    - `MarginFlowJob` 按交易日调用 `MarginFlowPort.fetch_*` → DuckDB 表 → `/api/market/margin/*`。
    - `SupplyConstraintJob` 汇总解禁/质押/分红事件，结合近端流动性（缓存的资金速度均值）计算承载力评分。
    - `StylePreferenceJob` 读取财报/业绩字段，生成风格雷达数据。
    - `ConceptAssociationJob` 利用本地缓存的分钟序列执行相关/Granger 分析。
3. **外部资产协同（可选）**
    - 若启用，`ExternalOverlayService` 周期性拉取期货快照 → 复合指标写入缓存。

## 6. 数据建模 & API 契约映射

- 实体与值对象：
  - `MarketSnapshot`, `CapitalPulse`, `AuctionScore`, `OrderImbalance`, `LimitStrength`, `ETFPremium`,
      `MarginSummary`, `MarginDetail`, `SupplyConstraintEvent`, `StylePreference`, `ExternalOverlay`.
  - 均落在 `deepsearch/domain/market_data/entities.py`（或按子域拆分）。
  - 数据传输对象使用 `TypedDict`（端口层）与 Pydantic Schema（API 层）双向保持同名字段，确保与 `api_contract_v4.yaml` 一致。
- API 输出字段与实体属性一一对应，禁止在 Web 层拼接裸字典；由 `application.market_data.presenters` 提供序列化辅助。

## 7. 缓存、性能与容错

- **实时缓存**：Redis Stream / Sorted Set 存储最新榜单，设置 TTL（默认 3 分钟），以 `board+window` 或 `code` 为 Key。
- **历史缓存**：DuckDB/Parquet 储存分钟轨迹、竞价记录，支持回放与概念关联计算。
- **节流策略**：实时服务统一走 `MarketStreamPort` 的聚合通道，避免多路订阅重复拉取。
- **容错**：适配器层负责登录/重连、接口限流、字段合法性校验；领域层对异常数据提供兜底评分（默认零值+告警）。
- **观测**：接入 `observability` 下的指标埋点（订阅延迟、计算耗时、队列长度）与报警规则。

## 8. 测试与质量保障

- 单元测试：对各 Port 实现、指标计算函数编写参数化测试（覆盖指标口径白皮书）。
- 合同测试：根据 `api_contract_v4.yaml` 生成 `schemathesis` / `pytest` 契约测试。
- 集成测试：构造 AmazingData SDK 的 `FakeClient`（在 `tests/market_data/fakes/`），模拟快照流与日频接口。
- 性能回归：针对实时榜单计算建立基准脚本，确保 5s 聚合窗口内完成。

## 9. 实施节奏建议

1. **M1：蓝图定稿**
    - 补齐端口接口定义草稿（Protocol + TypedDict）。
    - 明确 Worker 调度策略与缓存选型。
2. **M2：实时最小链路**
    - 市场订阅 + 资金脉冲 + 盘口失衡 + API MVP。
    - 完成 Redis/DuckDB 写入与基本监控。
3. **M3：指标体系拓展**
    - 加入封单稳定度、竞价质量、ETF 溢价、两融 T‑1。
    - 扩充测试覆盖与契约验证。
4. **M4：前端与联调**
    - 输出 mock server / schema，协助 WebUI MVP。
    - 建立端到端回放脚本。
5. **M5：外部资产 & 运维手册**
    - 如需启用期货参考层，完成适配与风险控制。
    - 输出运维 Runbook（接入 docs/operations）。

## 10. 待澄清事项

- AmazingData 订阅通道的并发限制、批量订阅上限是否需要拆分多进程。
- ETF ↔ 概念映射、行业分类是否已有权威数据源（若无需同步新增配置）。
- 外部资产模块是否纳入首轮交付；若否，可在配置层关闭 `ExternalOverlayPort` 的绑定。
