# DeepSearch 文档中心

> **快速导航**：[文档索引总表](./overview/document_index.md)

## 📚 文档地图

- **概览**（目录：overview/）
  - [架构优化策略](./overview/architecture_optimization_strategy.md)
  - [数据接口分层](./overview/data_interface_layer.md)
  - [数据源管理蓝图](./overview/data_source_management.md)
  - [数据源进程池架构](./overview/datasource_process_pool_architecture.md)
- **架构设计**（目录：architecture/）
  - [系统架构概览](./architecture/SYSTEM_ARCHITECTURE.md)
  - [配置架构最佳实践](./architecture/CONFIG_ARCHITECTURE_BEST_PRACTICES.md)
  - [数据提供者架构设计](./architecture/data_provider_design.md)
  - [策略模块规划](./architecture/STRATEGY_MODULE_PLAN.md)
  - [关键设计决策](./architecture/DESIGN_DECISIONS.md)
  - [AmazingData 本地数据路径重构方案](./architecture/amazingdata-local-path-refactor.md)
- **模块说明**（目录：modules/）
  - [模块技术说明索引](./modules/README.md)
- **数据源手册**（目录：datasources/）
  - [AmazingData 系列](./datasources/amazingdata/README.md) — 快速开始、接入配置、隔离与容灾方案（接口文档同步至 2025-09-11 V1.0.8）
  - [QMT 数据馈送（已归档）](./archive/datasources/qmt/README.md) — 历史本地终端集成方案
- **开发指南**（目录：development/）
  - [盘后展示与实时页面改造](./development/frontend/market_live_after_hours.md)
  - [最佳实践](./development/BEST_PRACTICES.md)
  - [调试功能](./development/DEBUG_FEATURES.md)
  - [代码审查要点](./development/CODE_REVIEW.md)
  - [前端 Zustand 集成](./development/frontend/zustand_integration.md)
  - [Git 提交规则总则](./development/GIT_COMMIT_RULES.md)
- **运维手册**（目录：operations/）
  - [数据源监控体系](./operations/monitoring/data_source_monitoring.md)
  - [资源管理改进方案](./operations/resource_management_improvements.md)
  - [前端超时应急手册](./operations/runbooks/frontend_timeout_solution.md)
- **计划与阶段性文档**（目录：plans/）
  - [阶段性计划汇总](./plans/README.md) —— 汇集数据源 orchestrator、AmazingData 重构、Market Live 休市体验、SDK 登录应急、盘面规划与缓存方案等内容
- **API 参考**（目录：api/）
  - [API 总览](./api/README.md)
  - [前端接口注册表](./api/FRONTEND_API_REGISTRY.md)
  - [后端接口注册表](./api/BACKEND_API_REGISTRY.md)
  - [前后端映射](./api/API_MAPPING.md)
  - [自动生成统计](./api/statistics.md)
- **参考资料**（目录：reference/）
  - AmazingData 官方文档：请联系数据源维护人获取最新资料，内部不再保留镜像。推荐通过 <https://cloud.chinastock.com.cn/p/DSG36jYQx2IY_Y8CIAA> 查看最新版本，并关注目录页 <https://cloud.chinastock.com.cn/p/DSG36jYQx2IY_Y8CIAA#dir=%2FAmazingData::mode=0> 的更新提示。
- **归档**（目录：archive/）
  - [历史方案与停用数据源](./archive/README.md)
  - 按主题分类的旧文档（如 AkShare 方案、历史清理报告）

> **提示**：原 docs/api-guides/ 已拆分至 docs/datasources/，docs/api/ 仍由自动化脚本生成维护。

## 🚀 快速导航

- **新成员**
  1. 先阅读 [系统架构概览](./architecture/SYSTEM_ARCHITECTURE.md)
  2. 了解 [开发最佳实践](./development/BEST_PRACTICES.md)
  3. 根据角色选读 [数据源手册](./datasources/README.md) 和 [API 文档](./api/README.md)
- **后端/引擎开发**
  - overview/ 了解整体链路 → architecture/ 深入模块 → datasources/amazingdata/ 对接真实 API
- **运维支持**
  - operations/monitoring/ 获取监控与诊断方案 → operations/runbooks/ 查看常见问题处理流程

## 🛠️ 文档维护

- **最后整理**：2025-10-10
- **维护者**：DeepSearch Team
- **覆盖范围**：单机部署、AmazingData 主数据源、QMT 本地数据馈送
- **维护约定**：变更接口后运行 python tools/generate_api_documentation.py 同步 docs/api/

## 🔍 查阅方式

- 通过仓库内搜索关键字（rg/IDE 全局搜索）
- docs/datasources/README.md 提供数据源专题索引
- docs/archive/ 收录历史方案、已淘汰流程，仅供回溯参考

## 🤝 文档贡献

1. 选择正确目录提交文档；新专题遵循“概览→设计→流程→参考”的结构
2. 文档默认 UTF-8，代码片段需注明语言
3. 大幅改动需在 PR 描述列出目的、影响范围以及验证步骤
4. 新增/调整配置时，记得同步更新示例文件与相关说明
