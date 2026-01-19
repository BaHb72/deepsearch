# 存在两个同名 DataProviderFactory 类

## 问题描述

项目中存在两个同名的 `DataProviderFactory` 类，功能不同，可能导致混淆：

1. **packages/core/infrastructure/providers/selection_factory.py**
   - 负责智能选择和管理数据提供者
   - 支持多种选择策略（优先级、轮询、故障转移、性能、混合）
   - 包含熔断器机制

2. **apps/api/api/providers.py**
   - API 层的工厂类
   - 功能待确认

## 影响

- 代码阅读时容易混淆
- IDE 自动导入可能选择错误的类
- 新开发者难以理解两者的区别

## 建议方案

1. **重命名其中一个类**：
   - `selection_factory.py` 中的改为 `ProviderSelector` 或 `SmartProviderFactory`
   - `providers.py` 中的改为 `ApiProviderFactory` 或其他更具体的名称

2. **或者合并功能**：如果两者功能有重叠，考虑统一为一个类

## 优先级

低 - 不影响功能，但影响代码可维护性

## 发现时间

2026-01-17

## 发现场景

修复 Provider 工厂模块命名冲突时发现
