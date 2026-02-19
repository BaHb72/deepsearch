# 数据源优先级语义与排序实现不一致

- **发现日期**: 2026-02-16
- **严重程度**: 中
- **类型**: config
- **状态**: resolved

## 问题描述

配置模型说明“优先级值越小越优先”，但运行时排序实现使用 `reverse=True`，表现为“值越大越优先”。

## 关键证据

- `packages/core/config/models/data_sources.py:42`
- `packages/core/config/models/data_sources.py:105`
- `packages/core/infrastructure/providers/registry.py:673`

## 影响

- 配置与实际行为可能相反
- 线上切换主/备源时容易产生误判

## 建议修复

1. 统一语义：要么调整排序实现，要么修正文档与字段说明
2. 增加回归测试，锁定优先级排序行为

## 处理优先级

P1

## 解决记录

- **解决日期**: 2026-02-16
- **解决方式**:
  - 明确配置层语义边界：
    - `packages/core/config/models/data_sources.py` 中 `DataSourceProviderConfig.priority` 标注为“统一 data_sources 语义：值越小越优先”
    - `RealtimeAdapterSpec.priority` 标注为“仅 realtime adapters 选择语义”
  - 在 `packages/core/infrastructure/providers/registry.py:get_providers_by_priority()` 补充 legacy 说明：旧注册表链路沿用“值越大越优先”
  - 本次不改变 legacy 运行行为，避免影响旧链路稳定性；后续在双路径收敛阶段统一行为语义
