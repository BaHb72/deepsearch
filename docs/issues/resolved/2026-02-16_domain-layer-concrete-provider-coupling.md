# 领域层直接依赖 AmazingData 具体实现

- **发现日期**: 2026-02-16
- **严重程度**: 高
- **类型**: architecture
- **状态**: resolved

## 问题描述

领域层模块直接 import 基础设施层具体实现 `AmazingDataExtended`，未通过 ports 协议抽象依赖。

## 关键证据

- `packages/core/domain/concept_engine.py:6`
- `packages/core/domain/concept_engine.py:37`
- `packages/core/domain/concept_engine.py:248`

## 影响

- 无法平滑切换数据源实现
- 领域层测试难以替换依赖
- 违反 ports + adapters 约束，耦合向上扩散

## 建议修复

1. 在 `packages/core/ports/` 中定义概念引擎所需最小能力协议
2. 在 `packages/core/adapters/` 或 `packages/core/infrastructure/providers/adapters/` 提供实现映射
3. 领域层仅依赖协议，不直接依赖 `AmazingDataExtended`

## 处理优先级

P0

## 解决记录

- **解决日期**: 2026-02-16
- **解决方式**:
  - 新增端口协议 `packages/core/ports/concept_engine.py`，定义 `ConceptDataProviderPort`
  - `packages/core/domain/concept_engine.py` 改为依赖 `ConceptDataProviderPort`
  - 移除领域层对 `core.infrastructure.providers.implementations.amazingdata.amazingdata_extended` 的直接 import
  - `packages/core/ports/__init__.py` 导出新端口，统一跨层引用

