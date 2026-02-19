# 过时 FastAPI Provider 集成路径与现模型不兼容

- **发现日期**: 2026-02-16
- **严重程度**: 中
- **类型**: architecture
- **状态**: resolved

## 问题描述

`packages/core/infrastructure/providers/integration/fastapi.py` 使用 `config.data_sources.items()` 与 `ds_config.get(...)` 的 dict 风格访问。
但 `data_sources` 当前为 `DataSourcesConfig` 模型，不提供该访问方式。

## 关键证据

- `packages/core/infrastructure/providers/integration/fastapi.py:41`
- `packages/core/infrastructure/providers/integration/fastapi.py:42`
- `packages/core/config/models/data_sources.py:159`
- `apps/api/server.py:646`

## 影响

- 若误用该入口，将触发运行时错误
- 形成“看似可用但实际不可用”的维护陷阱

## 建议修复

1. 明确该模块状态：删除、废弃标注或修复到可运行
2. 若保留，按 `DataSourcesConfig.providers` 路径重写预加载逻辑
3. 补一条最小集成测试

## 处理优先级

P1

## 解决记录

- **解决日期**: 2026-02-16
- **解决方式**:
  - 重写 `packages/core/infrastructure/providers/integration/fastapi.py` 的配置读取逻辑
  - 新增 `_iter_enabled_provider_configs()`，统一从 `data_sources.providers` 读取并过滤启用项
  - 去除对 `config.data_sources.items()` 与 `ds_config.get()` 的错误依赖
  - 新增测试 `tests/unit/infrastructure/providers/test_fastapi_integration.py`
