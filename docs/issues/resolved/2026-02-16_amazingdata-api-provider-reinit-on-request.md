# AmazingData API 在请求阶段重复重建 Provider，绕过既有主链路

- **发现日期**: 2026-02-16
- **严重程度**: 高
- **类型**: architecture
- **状态**: resolved

## 问题描述

`apps/api/api/endpoints/amazingdata/amazingdata_api.py` 中的 `get_amazingdata_provider()` 逻辑会在拿到“非 `AmazingDataExtended`”实例时，直接在请求路径中重建 `AmazingDataExtended` 并初始化。

这会导致：

1. 绕过 `DataProviderFactory` / Dask Actor 的既有运行链路
2. 请求期出现重复初始化和重复登录风险
3. 在 AmazingData 单连接约束下放大连接竞争问题

## 关键证据

- `apps/api/api/endpoints/amazingdata/amazingdata_api.py:152`
- `apps/api/api/endpoints/amazingdata/amazingdata_api.py:205`
- 复现实验：当工厂返回任意非 `AmazingDataExtended` provider 时，函数仍会创建新实例（本轮已用单测覆盖）

## 影响

- 同一接口在不同 provider 类型下行为不一致
- 运行主路径出现“隐藏分叉”，增加排障复杂度
- 不利于“旧路径收敛到容器/代理路径”的治理目标

## 建议修复

1. 请求路径优先复用工厂返回实例，不做二次构造
2. 保留对 `None` provider 的显式错误（503）
3. 在 helper 中保留 `HTTPException` 原状态码，不再统一包装为 500

## 处理优先级

P0

## 解决记录

- **解决日期**: 2026-02-16
- **解决方式**:
  - 修改 `apps/api/api/endpoints/amazingdata/amazingdata_api.py`
    - `get_amazingdata_provider()` 改为优先复用工厂实例
    - 新增 `provider is None` 分支返回 503
    - 保留 `HTTPException`，避免 503 被误包成 500
    - `login()` 将实例写入键统一为 `DataSourceType.AMAZINGDATA.value`
  - 新增测试 `tests/unit/api/test_amazingdata_provider_resolution.py`
    - 验证已有 provider 被直接复用
    - 验证空 provider 返回 503
  - 回归：`uv run pytest tests/unit/api/test_amazingdata_provider_resolution.py tests/unit/cli/test_check_amazingdata_command.py -q` 通过
