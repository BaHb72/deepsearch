# DeepSearch 文档中心

## 📚 文档组织结构

### 📋 核心文档（根目录）
- [自动化测试计划](../AUTOMATED_TESTING_PLAN.md) - 完整的自动化测试体系建设计划 **[已完成]**
- [测试使用指南](../TESTING_GUIDE.md) - 自动化测试系统使用手册 **[活跃]**
- [架构优化策略](./ARCHITECTURE_OPTIMIZATION_STRATEGY.md) - 架构优化策略和ROI分析
- [数据层架构](./DATA_INTERFACE_LAYER.md) - 数据层接口设计
- [数据源管理](./DATA_SOURCE_MANAGEMENT.md) - 数据源统一管理方案

### 🏗️ [架构文档](./architecture/)
- [系统架构](./architecture/SYSTEM_ARCHITECTURE.md) - DeepSearch 整体系统架构
- [配置架构最佳实践](./architecture/CONFIG_ARCHITECTURE_BEST_PRACTICES.md) - 配置系统设计
- [策略架构](./architecture/STRATEGY_ARCHITECTURE.md) - 策略模块架构
- [策略模块计划](./architecture/STRATEGY_MODULE_PLAN.md) - 策略模块实施计划
- [日志架构设计](./architecture/logging_architecture_design.md) - 日志系统设计
- [设计决策](./architecture/DESIGN_DECISIONS.md) - 关键设计决策记录

### 🔌 [API指南](./api-guides/)
#### AkShare相关
- [AkShare API映射](./api-guides/AKSHARE_API_MAPPING.md) - API映射关系
- [AkShare CloudFlare优化](./api-guides/AKSHARE_CLOUDFLARE_OPTIMIZATION.md) - CloudFlare代理优化

#### AmazingData相关
- [AmazingData API指南](./api-guides/AMAZINGDATA_API_GUIDE.md) - API使用指南
- [AmazingData集成](./api-guides/AMAZINGDATA_INTEGRATION.md) - 集成方案

#### QMT相关
- [QMT API实现](./api-guides/QMT_API_IMPLEMENTATION.md) - API实现详情
- [QMT API参考](./api-guides/QMT_API_REFERENCE.md) - API参考手册
- [QMT MiniQMT架构](./api-guides/QMT_MINIQMT_ARCHITECTURE.md) - MiniQMT架构
- [QMT订阅机制](./api-guides/QMT_SUBSCRIPTION_MECHANISM.md) - 订阅机制说明

#### 数据源相关
- [数据提供者设计](./api-guides/DATA_PROVIDER_DESIGN.md) - 数据提供者架构设计
- [数据源能力](./api-guides/DATA_SOURCE_CAPABILITIES.md) - 各数据源能力对比
- [数据源监控](./api-guides/DATA_SOURCE_MONITORING.md) - 数据源监控方案
- [数据源分析报告](./api-guides/DATA_SOURCE_ANALYSIS_REPORT.md) - 数据源问题分析

### 💻 [开发文档](./development/)
- [最佳实践](./development/BEST_PRACTICES.md) - 开发最佳实践指南
- [代码审查](./development/CODE_REVIEW.md) - 代码审查报告
- [调试功能](./development/DEBUG_FEATURES.md) - 调试功能说明
- [交易视图功能](./development/TRADING_VIEW_FEATURES.md) - 交易视图功能说明

### 🔧 [运维文档](./operations/)
- [资源管理改进](./operations/resource_management_improvements.md) - 资源管理优化方案

### 💡 [解决方案](./solutions/)
- [前端超时解决方案](./solutions/frontend_timeout_solution.md) - 前端API超时问题解决

### 🔄 [迁移文档](./migration/)
- [组件迁移映射](./migration/COMPONENT_MIGRATION_MAP.md) - 组件迁移对照表
- [前端迁移计划](./migration/FRONTEND_MIGRATION_PLAN.md) - 前端迁移方案

### 📦 [归档文档](./archive/)
历史版本和已废弃的文档存档

---

## 📖 快速导航

### 新手入门
1. 先阅读 [系统架构](./architecture/SYSTEM_ARCHITECTURE.md) 了解整体设计
2. 查看 [最佳实践](./development/BEST_PRACTICES.md) 了解开发规范
3. 参考 [API指南](./api-guides/) 了解各数据源使用

### 开发者
1. [开发文档](./development/) - 开发规范和最佳实践
2. [调试功能](./development/DEBUG_FEATURES.md) - 调试工具使用
3. [代码审查](./development/CODE_REVIEW.md) - 代码质量报告

### 运维人员
1. [运维文档](./operations/) - 系统运维指南
2. [数据源监控](./api-guides/DATA_SOURCE_MONITORING.md) - 监控配置

## 📅 文档维护

- **最后更新**: 2025-09-16（更新自动化测试系统文档）
- **维护者**: DeepSearch Team
- **版本**: v2.2
- **文档状态**: 已完成架构重构和自动化测试体系建设

## 🔍 文档搜索

使用 GitHub 搜索功能或本地文件搜索来查找特定内容。

## 📝 贡献文档

欢迎贡献文档！请遵循以下规范：
1. 使用清晰的标题和结构
2. 包含代码示例
3. 保持文档更新
4. 放置在正确的分类文件夹中