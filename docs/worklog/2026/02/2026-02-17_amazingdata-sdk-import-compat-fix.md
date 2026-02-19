# AmazingData SDK 导入兼容修复（Login/login + __getattr__）

> 日期: 2026-02-17
> 模块: amazingdata-loader, amazingdata-extended, provider-init
> 类型: bugfix

---

## 为什么要改

### 遇到的问题

导入 `core.infrastructure.providers.implementations.amazingdata` 时，触发：

- `RuntimeError: Cannot import AmazingData SDK ...`

根因并非单一缺包，而是：

1. `tgw` 只暴露 `Login`，上层调用契约是 `login`。
2. 模块级 `__getattr__` 在导入期会触发 SDK 懒加载，把可恢复兼容问题放大为导入失败。

### 现有方案的问题

当前兼容逻辑在 `_sdk_loader.py` 与 `amazingdata_extended.py` 两处标准不一致，导致行为不稳定且错误信息误导。

---

## 最终方案

### 选择: 统一兼容入口 + 限制导入期动态回退

__原因__:

1. 优先恢复“模块可导入”这一底线能力。
2. 将 `tgw` 与 `AmazingData` 的入口差异在加载边界统一消化。
3. 避免 `__getattr__` 影响 import machinery 的特殊属性访问。

### 关键改动

- `packages/core/infrastructure/providers/implementations/amazingdata/__init__.py`
  - `StockListRecord` 改为直接从 `core.domain.market_data` 导入。
- `packages/core/infrastructure/providers/implementations/amazingdata/amazingdata_extended.py`
  - `_load_sdk()` 兼容 `login/Login`；
  - `__getattr__` 对 `__*` 属性不触发 SDK 加载；
  - SDK 不可用时返回 `AttributeError` 语义，不在导入期抛误导性 RuntimeError。
- `packages/core/infrastructure/providers/implementations/amazingdata/_sdk_loader.py`
  - 发现 `Login` 时自动补齐 `login` 别名，保证上层 `sdk.login()` 协议一致。

---

## 验证

1. 导入验证
   - `import core.infrastructure.providers.implementations.amazingdata.amazingdata_extended` 成功。
2. 目标回归
   - `pytest tests/unit/api/test_amazingdata_provider_resolution.py tests/unit/infrastructure/providers/test_fastapi_integration.py tests/unit/infrastructure/test_dockerfile_dask_security.py -q`
   - 结果：`7 passed`。

---

## 关键结论

> 这类错误的关键不是“再多加几个 import 候选”，而是先统一协议边界（login/Login），再隔离导入期的动态行为副作用。
