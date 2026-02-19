# Provider 核心模块体量过大且职责混杂

- **发现日期**: 2026-02-16
- **严重程度**: 中
- **类型**: architecture
- **状态**: open

## 问题描述

核心模块行数和职责边界超出合理范围，创建、路由、状态、配置落盘、兼容层逻辑混合在单文件中。

## 关键证据

- `packages/core/infrastructure/providers/managers/data_source_manager.py`（2472 行）
- `packages/core/infrastructure/providers/registry.py`（771 行）
- `apps/api/api/providers.py`（1194 行）

## 影响

- 改一处牵动多处，回归风险增大
- 单测粒度粗，缺陷定位速度慢

## 建议修复

1. 按职责拆分：配置编排、实例生命周期、路由策略、健康状态
2. 先抽出纯函数与数据结构，再逐步切边界
3. 每次拆分配套回归测试，避免一次性大改

## 处理优先级

P1

## 处理进展（2026-02-16）

- 已确认高体量文件并完成第一轮无行为风险清理：
  - 修复 `packages/core/infrastructure/providers/managers/data_source_manager.py` 关键乱码注释/日志
  - 修复 `packages/core/infrastructure/providers/integration/fastapi.py` 的配置读取失配问题
- 已形成拆分配套计划：`docs/plans/provider_dual_path_convergence_2026-02-16.md`

## 下一步

1. 从 `apps/api/api/providers.py` 抽离“获取 provider 入口”到独立兼容模块
2. 从 `data_source_manager.py` 抽离配置归一化与 fallback 同步逻辑为独立组件
3. 每次抽离都配套最小回归测试

