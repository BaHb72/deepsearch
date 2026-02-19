# Provider 双主路径并存，架构未收敛

- **发现日期**: 2026-02-16
- **严重程度**: 高
- **类型**: architecture
- **状态**: open

## 问题描述

当前数据源主链路存在两套并行实现：

1. `ProviderContainer + ProviderFactory` 新路径
2. `DataSourceManager + DataProviderRegistry + API DataProviderFactory` 旧路径

两条路径都在生产代码中被引用，导致配置解释、生命周期、健康检查与容错行为可能不一致。

## 关键证据

- `packages/core/infrastructure/providers/container.py:24`
- `packages/core/infrastructure/providers/factory/provider_factory.py:18`
- `packages/core/infrastructure/providers/registry.py:57`
- `packages/core/infrastructure/providers/managers/data_source_manager.py:369`
- `packages/core/infrastructure/providers/managers/data_source_manager.py:1201`
- `apps/api/api/providers.py:180`

## 影响

- 同一数据源在不同入口行为不同，问题复现与排障难度上升
- 变更需要同时覆盖两套链路，回归成本高
- 新同学难以判断“唯一正确入口”

## 建议修复

1. 明确唯一运行主路径（建议 `ProviderContainer`）
2. 旧链路改为兼容层并标注废弃边界
3. API 入口统一经由同一容器与依赖注入机制

## 处理优先级

P0（先治理，后扩展）

## 处理进展（2026-02-16）

- 已完成成因追溯：`docs/worklog/2026/02/2026-02-16_provider-path-a-to-b-origin-analysis.md`
- 已输出收敛计划：`docs/plans/provider_dual_path_convergence_2026-02-16.md`
- 已先行修复一处过时分支：`packages/core/infrastructure/providers/integration/fastapi.py`
- 已启动 Phase 1 低风险迁移：
  - `apps/api/api/endpoints/data/data_source.py` 改为使用 `provider_deps.get_akshare_provider`
  - `apps/api/api/proxy.py` 改为通过 `Depends(get_akshare_provider)` 注入 Provider
  - `apps/api/api/endpoints/data/akshare_apis.py` 的 `/api/akshare/call` 已切换到 `Depends(get_akshare_provider)`
- 已修复 AmazingData 请求期重建 Provider 分支：
  - `apps/api/api/endpoints/amazingdata/amazingdata_api.py` 的 `get_amazingdata_provider()` 改为复用工厂实例
  - 解决记录：`docs/issues/resolved/2026-02-16_amazingdata-api-provider-reinit-on-request.md`

## 下一步

1. 按计划 Phase 1 批量替换 endpoint 的 provider 获取入口
2. 将 `apps/api/api/providers.py` 降级为兼容层，并增加废弃告警
