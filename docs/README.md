# DeepSearch 文档中心

> **快速导航**：[文档索引总表](./overview/document_index.md)

## 📚 文档地图

- **概览**（目录：overview/）
  - [架构优化策略](./overview/architecture_optimization_strategy.md)
  - [数据接口分层](./overview/data_interface_layer.md)
  - [数据源管理蓝图](./overview/data_source_management.md)
  - [数据源进程池架构](./overview/datasource_process_pool_architecture.md)
- **架构设计**（目录：architecture/）
  - [AmazingData 本地数据路径重构方案](./architecture/amazingdata-local-path-refactor.md)
  - [数据同步重构提案](./architecture/data_sync_refactor_proposal.md)
  - [实时端口设计](./architecture/realtime_ports.md)
- **模块说明**（目录：modules/）
  - [模块技术说明索引](./modules/README.md)
- **数据源手册**（目录：datasources/）
  - [AmazingData 系列](./datasources/amazingdata/README.md) — 快速开始、接入配置、隔离与容灾方案
  - [AkShare 接口](./datasources/akshare/) — AkShare 数据源接口文档
  - [实时能力矩阵](./datasources/realtime_capability_matrix.md)
- **开发指南**（目录：development/）
  - [盘后展示与实时页面改造](./development/frontend/market_live_after_hours.md)
  - [实时数据源统一方案](./development/realtime_data_source_unification.md)
  - [AmazingData Mypy 备注](./development/amazingdata_mypy_notes.md)
- **运维手册**（目录：operations/）
  - [运维手册索引](./operations/README.md)
  - [Runbooks](./operations/runbooks/)
- **计划与阶段性文档**（目录：plans/）
  - [阶段性计划汇总](./plans/README.md)
  - [模块数据源切换计划](./plans/module_data_source_switch_plan.md)
- **参考资料**
  - AmazingData 官方文档：请通过 <https://cloud.chinastock.com.cn/p/DSG36jYQx2IY_Y8CIAA> 查看最新版本

## 🚀 快速导航

- **新成员**
  1. 先阅读 overview/ 了解系统架构
  2. 根据角色选读 [数据源手册](./datasources/README.md)
- **后端/引擎开发**
  - overview/ 了解整体链路 → architecture/ 深入模块 → datasources/amazingdata/ 对接真实 API
- **运维支持**
  - operations/ 获取监控与诊断方案 → operations/runbooks/ 查看常见问题处理流程

## 🛠️ 文档维护

- **最后整理**：2025-12-28
- **维护者**：DeepSearch Team
- **覆盖范围**：单机部署、AmazingData 主数据源、MiniQMT(XTData)数据馈送

## 🔍 查阅方式

- 通过仓库内搜索关键字（rg/IDE 全局搜索）
- docs/datasources/README.md 提供数据源专题索引

## 🤝 文档贡献

1. 选择正确目录提交文档；新专题遵循"概览→设计→流程→参考"的结构
2. 文档默认 UTF-8，代码片段需注明语言
3. 大幅改动需在 PR 描述列出目的、影响范围以及验证步骤
4. 新增/调整配置时，记得同步更新示例文件与相关说明
