# AmazingData SDK 导入兼容与模块级 __getattr__ 导入期误触发

- **发现日期**: 2026-02-17
- **严重程度**: 高
- **类型**: runtime / compatibility
- **状态**: resolved

## 问题描述

在导入 `core.infrastructure.providers.implementations.amazingdata` 相关模块时，出现：

- `RuntimeError: Cannot import AmazingData SDK ...`

实际并非单纯“SDK 不存在”，而是两个问题叠加：

1. `tgw` 可导入但仅暴露 `Login`（大写），代码路径要求 `login`（小写）。  
2. `amazingdata_extended.py` 的模块级 `__getattr__` 在导入阶段会被动触发 `_load_sdk()`，导致导入链路提前失败。

## 关键证据

- `packages/core/infrastructure/providers/implementations/amazingdata/amazingdata_extended.py:2469`
- `packages/core/infrastructure/providers/implementations/amazingdata/amazingdata_extended.py:2513`
- `packages/core/infrastructure/providers/implementations/amazingdata/_sdk_loader.py:27`
- `packages/core/infrastructure/providers/implementations/amazingdata/__init__.py:23`

## 影响

1. 单测与应用导入链路可能在模块加载阶段中断。  
2. 错误文案“Cannot import”会掩盖真实兼容问题，导致误判为缺包。  
3. `tgw` 可用场景下仍可能在 `sdk.login()` 处崩溃。

## 解决记录

- **解决日期**: 2026-02-17
- **解决方式**:
  - `packages/core/infrastructure/providers/implementations/amazingdata/__init__.py`
    - `StockListRecord` 改为从 `core.domain.market_data` 直接导入，避免触发扩展模块 `__getattr__` 回退路径。
  - `packages/core/infrastructure/providers/implementations/amazingdata/amazingdata_extended.py`
    - `_load_sdk()` 兼容 `login/Login` 双入口；
    - `__getattr__` 对 `__*` 属性直接 `AttributeError`，避免导入期误触发 SDK 加载；
    - 错误信息改为“兼容入口缺失”并附带候选失败细节。
  - `packages/core/infrastructure/providers/implementations/amazingdata/_sdk_loader.py`
    - 若检测到 `Login` 且无 `login`，自动补齐 `login` 别名，统一上层协议。
  - 回归结果：
    - `pytest tests/unit/api/test_amazingdata_provider_resolution.py tests/unit/infrastructure/providers/test_fastapi_integration.py tests/unit/infrastructure/test_dockerfile_dask_security.py -q` 通过（7 passed）。
