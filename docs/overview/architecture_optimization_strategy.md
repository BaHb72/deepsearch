# DeepSearch 架构优化策略

> 更新时间：2025-10-04
> 适用范围：主干分支 / 单机场景

本文概述 DeepSearch 当前的架构现状、主要风险及未来两个月的优化计划。目标是在保持单机部署与模块化原则的前提下，稳步提升可维护性、观测性与数据链路的可靠性。

## 1. 现状盘点

### 1.1 核心模块

- **core**：组件化运行时，统一管理事件引擎、网关、缓存等能力。
- **event**：双线程事件引擎，负责调度行情、策略、通知等内部事件。
- **infrastructure**：对接缓存、数据库、消息、数据源等外部依赖。
- **strategies / backtest**：策略运行与回测框架，复用相同接口。
- **webui**：FastAPI + React 管理界面，提供配置、监控与运维入口。

### 1.2 已知问题

| 问题 | 影响 | 现状 | 优先级 |
| ---- | ---- | ---- | ------ |
| 组件配置散落 | 新人接入成本高 | `settings.*.yaml` 与代码校验差异 | P0 |
| AmazingData 故障回退流程零散 | 影响数据链路稳定 | ProcessPool、SafeWrapper、监控逻辑分布在多处 | P0 |
| 文档缺口 | 交接效率低 | 模块说明缺乏统一结构 | P1 |
| Windows 部署脚本分散 | 新环境搭建慢 | 多个 `.bat/.ps1` 缺乏总览 | P2 |

### 1.3 约束与原则

- **部署限制**：仅支持 Windows 单机，禁止引入分布式消息队列、容器调度等方案。
- **数据源策略**：默认启用 AmazingData，并在其不可用或无法提供所需数据时回退至 AkShare；其余实现保留在仓库但默认禁用。
- **配置管理**：所有环境差异写入 `settings.<env>.yaml`，严禁通过环境变量调参。
- **编码规范**：Python 3.13 + UV 工具链，统一执行 ruff / black / isort / pytest。

## 2. 优化目标

1. **模块边界清晰**：组件依赖关系有据可查，生命周期管理统一。
2. **数据源链路稳健**：AmazingData 的登录、重试、降级策略可追踪可回溯。
3. **文档与脚本易用**：关键流程有标准操作指引，新成员 1 天内完成环境搭建。
4. **可观测性增强**：日志、指标、诊断脚本覆盖核心链路，支持快速定位问题。

## 3. 两阶段路线图

### 阶段 A（2025-10 W1 ~ W2）

| 任务 | 说明 | 交付物 |
| ---- | ---- | ------ |
| 配置模型梳理 | 对齐 `deepsearch/config/models` 与示例 YAML | 更新 `settings.*.yaml.example`、增加校验用例 |
| 数据源流程固化 | 收敛 ProcessPool、SafeWrapper 的接口，补充异常上报 | `docs/datasources/amazingdata/*.md` + 新单测 |
| 组件文档补全 | 以 `docs/modules/` 结构描述核心模块 | 完成 core/event/infrastructure/schedulers 文档 |

### 阶段 B（2025-10 W3 ~ W4）

| 任务 | 说明 | 交付物 |
| ---- | ---- | ------ |
| 观测性增强 | 整合日志采集、指标暴露、调试脚本 | `observability` 配置说明 + CLI 调试指南 |
| Windows 部署指南 | 汇总 `.bat/.ps1` 使用方式，强调虚拟环境复用 | `docs/operations/runbooks/windows_deploy.md` |
| 回归流程固化 | 统一测试脚本、生成覆盖率报告 | 脚本 `scripts/run_all_tests.py` 升级说明 |

## 4. 关键措施

### 4.1 配置与依赖注入

- 使用 `DeepSearchSettings` 作为单一真源，任何组件初始化必须通过 `config.manager` 提供的实例。
- `ComponentFactory` 中新增/修改组件时，需同步编写 `ComponentConfig` 注释并更新 `docs/modules/core.md`。
- 配置热更新功能仅在 dev/test 环境开放，生产环境写死为手动重启。

### 4.2 AmazingData 防护

- **登录策略**：`AmazingDataSafeWrapper` 负责重试、熔断、登出补偿，所有调用走包装器。
- **进程隔离**：`AmazingDataProcessPool` 仅在需要兼容旧版 SDK 时启用；默认走 `amazingdata_optimized.py` 单进程实现。
- **监控集成**：失败率、重试次数写入 `observability.metrics`，并触发通知通道。

### 4.3 文档与知识库

- 采用 `docs/modules/README.md` 作为模块索引，新增或调整模块时务必补齐文档。
- 架构决策记录统一追加到 `docs/architecture/DESIGN_DECISIONS.md`，避免重复记录。
- 保留历史方案到 `docs/archive/`，正文只描述当前生效流程。

### 4.4 开发流程

- 新功能提交流程：本地校验 → `python scripts/run_all_tests.py --quick` → 更新文档 → 提交。
- 回归缺陷时，必须补充对应测试或诊断脚本，避免重复踩坑。
- 代码审查关注点：依赖注入是否统一、日志是否脱敏、配置示例是否更新。

## 5. 风险与缓解

| 风险 | 描述 | 缓解措施 |
| ---- | ---- | -------- |
| Windows 与 WSL 环境混用 | 可能导致解释器/依赖冲突 | 明确 WSL 仅用于只读，脚本中增加路径检查 |
| 数据源接口变更 | AmazingData 上游调整导致兼容性问题 | 提前在 `_sdk_loader.py` 增加版本探测，准备降级策略 |
| 文档滞后 | 新能力上线未及时补文档 | 在 PR 模板增加「文档更新」检查项 |

## 6. 里程碑与验收

- **2025-10-18**：阶段 A 项目完成，相关文档、测试合并至主干。
- **2025-10-31**：阶段 B 收尾，回归一次完整冒烟测试并输出执行报告。
- 验收标准：
  1. 配置模型、模块说明、数据源文档均可在 30 分钟内定位到关键信息。
  2. AmazingData 故障模拟用例稳定通过，失败原因可在日志/指标中追溯。
  3. 新成员按照文档完成环境搭建和基础任务不超过 1 天。

---
**维护人**：架构小组（<arch@deepsearch.internal>）
**下次评审**：2025-11-01
