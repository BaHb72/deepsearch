# AmazingData 文档索引

> 更新时间：2025-10-10  
> 对应官方资料：`AmazingData_API.md`（2025-09-11，文档版本 V1.0.8，Python SDK V1.0.8）

## 快速导览

| 场景 | 文档 | 说明 |
| ---- | ---- | ---- |
| 入门体验 | [quick_start.md](./quick_start.md) | 5 分钟完成环境准备、首次登录与常见数据拉取示例。 |
| 环境配置 | [setup.md](./setup.md) | SDK 安装、接入点选择、配置文件与 WebUI 设置流程。 |
| 接口使用 | [api_guide.md](./api_guide.md) | 调用流程、缓存策略、错误处理与最佳实践。 |
| 参数检索 | [api_reference.md](./api_reference.md) | 按官方章节整理的函数签名、关键参数与返回结构。 |
| 枚举字段 | [data_types.md](./data_types.md) | `security_type`、`Period`、`STATEMENT_TYPE` 等枚举与核心数据结构。 |
| 系统集成 | [integration.md](./integration.md) | DeepSearch 内部调用链、配置要点与测试策略。 |
| 隔离方案 | [isolation_technical_design.md](./isolation_technical_design.md) | SDK 进程隔离、异常退出防护与设计权衡。 |
| 兼容计划 | [amazingdata_py39_bridge_plan.md](./amazingdata_py39_bridge_plan.md) | Python 3.13 主环境 + Python 3.9 Worker 的桥接部署步骤。 |
| 兼容性评估 | [amazingdata_py313_direct_run_eval.md](./amazingdata_py313_direct_run_eval.md) | 对在 Python 3.13 直接运行 SDK 的可行性评估。 |
| 稳定性策略 | [resilience_strategy.md](./resilience_strategy.md) | 线程池、重试、监控等全量弹性方案与验证路线。 |
| 降级处理 | [amazingdata_degraded_mode.md](./amazingdata_degraded_mode.md) | 降级触发条件、运行态与恢复流程。 |
| 已知问题 | [starshine_api_issues.md](./starshine_api_issues.md) | 官方 SDK/TGW 历史缺陷与原因分析记录。 |

## 维护约定
- 发布新接口或调整运行模式时，须先更新 `AmazingData_API.md` 并同步上述相关文档。
- 更新完成后，请一并维护 `docs/overview/document_index.md` 与 `docs/modules/README.md` 的索引信息。
- 文档默认采用 UTF-8 编码；如需引用外部 PDF 或截图，请注明来源并放入对应的 `/assets` 目录。

> 相关 Runbook 位于 `docs/operations/runbooks/`，测试策略位于 `docs/testing/`，历史方案请参见 `docs/archive/datasources/`。
