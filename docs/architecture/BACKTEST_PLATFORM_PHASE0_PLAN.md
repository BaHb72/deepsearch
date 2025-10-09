# 回测平台重构 Phase 0 工作清单

## 1. 现状梳理
- **代码模块**
  - `deepsearch/backtest/*`：包含旧版 `engine.py` 与新版 `backtest_engine.py`、数据桥接、适配器、结果工具，存在双引擎并行、注释乱码问题。
  - `deepsearch/strategies/*`：策略接口 `interfaces/base.py`、Backtrader 直接实现（`implementations/*.py`）、回测服务 `services/backtest_service.py`；当前服务与 WebUI 使用的策略类型不一致。
  - `deepsearch/webui/api/endpoints/trading/backtest_api.py`：回测 API 入口，依赖 `get_backtest_engine`，包含任务执行、图表输出等逻辑。
  - `examples/backtest_*.py`、`deepsearch/backtest/tests/test_strategies.py`：示例脚本与数据校验策略，测试覆盖面有限。
- **依赖与外部接口**
  - Python 3.13、Backtrader、Matplotlib、Loguru、Pandas、NumPy。
  - 数据来源通过 `infrastructure.providers`（QMT/AkShare 等），需同步评估可用性与缓存策略。
  - WebUI/事件系统通过组件 `deepsearch/backtest/components/component.py` 访问回测能力。
- **已知问题**
  - 策略接口割裂、实时数据模拟、测试缺失、编码乱码、任务状态不统一，与 Phase 0 文档一致。

## 2. 评审准备材料
- 《BACKTEST_PLATFORM_REDESIGN.md》：架构愿景及分阶段计划（已完成）。
- 功能/依赖盘点：以上现状清单，可在评审前补充时序图/数据流图。
- Pain Points 证据：日志、Issue、示例失败案例（需搜集）。
- 参考资料：`docs/architecture/STRATEGY_ARCHITECTURE.md`、`docs/development/CODE_REVIEW.md` 中的回测相关段落。

## 3. 待补充基线
- **数据集**：选取沪深 A 股日线、分钟线、极端行情样本各 1 套，生成快照供自动测试；确认获取方式与存储位置。
- **测试框架**：设计至少 3 类基准用例（数据适配、简单策略、指标输出）并在 Phase 0 收集预期结果。
- **性能基线**：记录现有引擎单任务耗时、内存、并发回测行为，作为后续对比依据。
- **文档**：规划《策略编写指南》《数据接入手册》《API 兼容说明》大纲，Phase 0 内确定章节与责任人。

## 4. 行动清单（Phase 0）
1. **组织评审**
   - 参与方：后端（回测/数据）、前端、运维、产品；拟定议题与期望输出（确认目标与资源）。
   - 产出：评审纪要、行动项责任人。
2. **现状调研**
   - 整理策略使用统计（实际接入的策略、调用入口）。
   - 梳理数据源可用性与缺陷（缓存命中、缺口、对账方式）。
   - 盘点 Web/API 对回测的依赖路径（页面、接口、任务类型）。
3. **基线采集**
   - 构建数据快照与预期指标表。
   - 记录当前回测任务的性能指标与错误率。
4. **文档落地**
   - 完成策略/数据/API 文档大纲与章节分工。
   - 补充《BACKTEST_PLATFORM_REDESIGN.md》附录（术语表、接口列表）。
5. **风险评估**
   - 列出 Phase 1 前需解决的阻断项（如数据授权、依赖版本、资源限制）。
   - 形成风险跟踪表并确定更新节奏。

## 5. 下一步执行建议
- 在一周内完成评审会议安排与资料准备。
- 开始收集基准数据与性能指标，输出初版调研报告草稿。
- 安排负责人撰写文档大纲，确保 Phase 1 可直接进入开发。


## 附录 A：现有回测流程依赖映射
- **调用路径（Web → 引擎）**
  - `deepsearch/webui/api/endpoints/trading/backtest_api.py` 暴露 `/api/backtest/*`，通过 `get_backtest_engine()` 获取全局单例，依次调用 `create_cerebro` → `add_data` → `add_strategy` → `run` → `get_performance_metrics`。
  - 后台任务 `execute_backtest`、`execute_optimization`、`get_backtest_plot` 等统一依赖此单例；`background_tasks.add_task` 负责异步执行。
- **调用路径（事件总线）**
  - `deepsearch/backtest/components/component.py` 注册 `BACKTEST_REQUEST`/`CANCEL`/`QUERY` 等事件，使用旧版 `BacktestEngine` (`engines/engine.py`)；与 Web API 并行存在，说明双轨实现仍被事件系统引用。
- **策略实现**
  - Web/API 直接引用 `deepsearch.strategies.implementations.*`（继承 `bt.Strategy`）。
  - `BacktestService`（`strategies/services/backtest_service.py`）面向 `deepsearch.strategies.interfaces.base.BaseStrategy`，但未在 Web/API 中使用，后续需决定保留方式。
- **数据链路**
  - `UnifiedBacktraderAdapter` 调 `infrastructure.providers.managers.enhanced_manager.get_data_manager()` → 多数据源（QMT/AkShare等）。
  - 数据桥接：`data_bridge.py`、`data_feed.py` 负责字段映射、缓存；`custom_data_feed.py` 提供实时模拟数据。
- **结果与工具**
  - `backtest_engine.py` 集中指标、权益曲线、图表生成；`utils/results.py`、`utils/parameter_converter.py` 提供结果与参数转换。
- **外部依赖总结**
  - 核心库：Backtrader、Pandas、NumPy、Matplotlib、Loguru。
  - DeepSearch 内部依赖：`deepsearch.infrastructure.providers.*` 数据管理、`deepsearch.event.engine` 事件驱动、`deepsearch.observability` 日志、WebUI API 层。

## 附录 B：基准数据与性能采集计划
- **数据基线**
  - 日线样本：上证综指(`000001.SH`)、深圳成指(`399001.SZ`)，区间 2020-01-01~2024-12-31，来源 AkShare/QMT；输出 CSV 快照存放于 `artifacts/backtest_baseline/daily/`。
  - 分钟线样本：`600519.SH`、`000858.SZ` 1m/5m 数据，区间近 90 天；验证高频场景。
  - 极端行情：2020-03、2022-10 等波动区间，额外拉取 `000001.SH` 日线用于压力测试。
  - 数据校验脚本：基于 `UnifiedBacktraderAdapter` + `DataBridge.validate_data`，生成诊断报告（Null/异常高低/缺口）。
- **性能基线**
  - 使用 `SimpleMAStrategy`、`MeanReversionStrategy` 在上述数据集上执行 `backtest_engine.run()`，记录运行时长、峰值内存、Cerebro 指标。
  - 并发测试：同时运行 5/10 个回测任务评估资源占用（CPU/内存）。
  - 采集方式：编写 `scripts/benchmarks/run_backtest_benchmarks.py`（Phase 0 任务），输出 JSON 报告至 `artifacts/backtest_baseline/perf/`。
- **任务安排建议**
  1. 数据团队：负责授权/接口校验，提供数据获取脚本模板（预计 3 天）。
  2. 回测研发：实现基准脚本与性能采集（预计 5 天）。
  3. 运维：确认存储目录与监控指标接入（预计 2 天）。
  4. 所有结果纳入 CI 产物，供后续回归对比。

## 附录 C：Phase 0 任务追踪（草案）
| 序号 | 任务 | 责任人（建议） | 预计完成 | 备注 |
| --- | --- | --- | --- | --- |
| P0-1 | 组织回测重构评审会（准备议程、资料） | 项目经理/回测负责人 | W1 | 产出评审纪要与行动项 |
| P0-2 | 数据样本采集脚本（AkShare/QMT） | 数据团队 | W1 | 生成日线/分钟/极端行情快照 |
| P0-3 | 基准回测与性能脚本 | 回测研发 | W2 | 输出 JSON 报告与资源监控记录 |
| P0-4 | 文档大纲编写（策略/数据/API 指南） | 文档负责人 | W1 | 确定章节与作者分工 |
| P0-5 | 现状调研报告（策略使用、接口依赖） | 回测研发 | W1 | 纳入 Phase 0 总结 |
| P0-6 | 风险与资源评估（环境、授权、CI） | 运维/PM | W2 | 建立风险跟踪表 |
| P0-7 | 更新评审材料（术语、接口列表） | 回测研发 | 与评审同步 | 附加到重构方案文档 |


## 评审会议议程草案
1. **会议目标**（5min）
   - 确认回测平台重构整体方向、阶段目标与资源投入。
2. **现状复盘**（15min）
   - 现有模块、调用路径、痛点回顾（附录 A/B 摘要）。
3. **重构方案讲解**（20min）
   - 架构分层、阶段计划、风险与应对。
4. **Phase 0 计划与行动项**（15min）
   - 基准数据采集、性能基线、文档与评估任务。
5. **资源与风险讨论**（15min）
   - 人力、环境、依赖授权、时间安排。
6. **决策与下一步**（10min）
   - 确认责任人、时间节点、评审输出。

## 资料清单
- `docs/architecture/BACKTEST_PLATFORM_REDESIGN.md`
- `docs/architecture/BACKTEST_PLATFORM_PHASE0_PLAN.md`
- 现有调用路径/依赖示意（可在会前准备流程图）
- 现有回测任务性能数据（若有）或调研记录
- 风险与资源评估初稿（待会中补充）

## 开放问题列表（评审前）
| 编号 | 问题 | 负责人（建议） | 状态 |
| --- | --- | --- | --- |
| O1 | 事件系统是否必须保留？若保留，如何迁移旧 `engine.py`？ | 回测研发 | 待确认 |
| O2 | 实时数据接入需求与优先级？Phase 0 是否需要明确数据源与接口？ | 数据团队 | 待确认 |
| O3 | 策略 SDK 统一方案：如何兼容现有 Backtrader 原生策略？ | 回测研发 | 待确认 |
| O4 | WebUI 功能期望（批量回测、图表、结果导出）与时间表？ | 前端/产品 | 待确认 |
| O5 | 性能目标与资源预算（并发数、耗时、成本）？ | PM/运维 | 待确认 |
| O6 | CI/CD 集成范围：是否需要在 Phase 0 完成自动化脚本接入？ | DevOps | 待确认 |
| O7 | 数据快照的存储与权限管理方案？ | 运维/数据 | 待确认 |

## 开放问题
- **事件系统迁移**：事件总线如何与统一回测入口对接，旧版组件淘汰顺序与兼容窗口待确认。
- **实时数据**：回测阶段是否需要复用实时行情桥接（QMT/AmazingData），以及缓存刷新策略未定。
- **策略 SDK 兼容**：新 SDK 与既有 Backtrader 策略/自研 BaseStrategy 的兼容计划及适配层范围需澄清。
- **前端需求**：WebUI 需展示的任务状态、结果可视化与交互调整项需产品确认。
- **性能目标**：Phase 0 基准的耗时、资源占用、指标稳定性目标值尚未评审。
- **CI 接入**：快照与基准脚本在 CI 的运行频率、资源配额、失败回滚策略待 DevOps 确认。
- **数据快照存储**：快照文件的持久化位置、版本管理方案及磁盘容量预算需要共识。
