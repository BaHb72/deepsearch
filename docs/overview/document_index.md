# 文档索引总表

本索引汇总 DeepSearch 仓库内的关键文档，提供路径与摘要，便于快速查找。维护文档时请同时更新本表，保证路径正确、摘要准确。

## 推荐阅读顺序

| 分类  | 文档路径                                                            | 内容摘要                                                 |
|-----|-----------------------------------------------------------------|------------------------------------------------------|
| 概览  | docs/README.md                                                  | 顶层导航，包含架构、开发、运维等文档入口。                                |
| 概览  | docs/overview/architecture_optimization_strategy.md             | 当前架构现状、优化目标与阶段规划。                                    |
| 概览  | docs/overview/data_interface_layer.md                           | 数据接口层目录结构与启用策略。                                      |
| 概览  | docs/overview/data_source_management.md                         | WebUI 与 FastAPI 如何管理 AmazingData 配置。                 |
| 概览  | docs/overview/datasource_process_pool_architecture.md           | AmazingData 进程隔离方案：Port/Adapter/ProcessPool 协同与运维指引。 |
| 开发  | docs/development/BEST_PRACTICES.md                              | 通用开发规范、流程与工具。                                        |
| 开发  | docs/development/CODE_REVIEW.md                                 | 代码评审关注点与常见问题。                                        |
| 前端  | docs/development/frontend/zustand_integration.md                | Zustand 状态管理整合方案。                                    |
| 前端  | docs/development/frontend/notification_center_design.md         | 通知中心交互设计与 API 协作。                                    |
| 数据源 | docs/datasources/amazingdata/README.md                          | AmazingData 文档索引（接口同步至 2025-09-11 V1.0.8）            |
| 数据源 | docs/datasources/amazingdata/amazingdata_degraded_mode.md       | AmazingData 降级模式触发与恢复流程。                             |
| 数据源 | docs/datasources/amazingdata/process_usage.md                   | 进程隔离版使用指南：Provider/登录（login_flow）/告警（alert_utils）/订阅 |
| 数据源 | docs/datasources/amazingdata/amazingdata_developer_manual.md    | AmazingData 开发手册（格式增强版）                              |
| 运维  | docs/operations/README.md                                       | 运维目录索引，覆盖监控与 Runbook 导航。                             |
| 运维  | docs/operations/runbooks/frontend_timeout_solution.md           | WebUI 超时问题的应急步骤。                                     |
| 运维  | docs/operations/runbooks/amazingdata_process_troubleshooting.md | AmazingData 进程崩溃诊断与日志路径。                             |
| QA  | docs/testing/REAL_DATA_SOURCE_API_TEST.md                       | 实际数据源 API 覆盖情况与环境配置说明。                               |

## 维护约定
- 迁移或新增文档后，请在 24 小时内更新本索引。
- 摘要不超过 40 字，突出读者可获取的关键信息。
- 归档内容请放入 `docs/archive/`，并在本表移除或注明新位置。

