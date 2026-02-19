# AmazingData 接口对齐（文档 + SDK pyc 反编译）

> 日期: 2026-02-17
> 模块: amazingdata-extended, dask-adapter, api-endpoints
> 类型: bugfix / compatibility

---

## 为什么要改

### 遇到的问题

“接口文档、SDK 实现、项目代码”三者之间出现偏差：

1. 文档定义 `get_option_mon_ctr_specs`，代码实际调用 `get_option_mon_ctr_spcon`。
2. `AmazingDataExtended` 没有完整暴露 SDK 1.0.28 的方法集合。
3. API 层缺少部分基础接口路由，和文档不一致。

### 诊断路径

1. 读取最新文档：`docs/datasources/amazingdata/amazingdata_developer_manual.md`。
2. 反编译 `.venv` 中 `AmazingData` 的 `base_data.pyc/info_data.pyc/market_data.pyc`，提取类方法列表。
3. 用 AST 对比 `AmazingDataExtended` 方法集合，定位缺口。

---

## 最终方案

### 选择: 以 SDK 运行时可用方法为准，向上兼容旧命名

**原因**:

1. 运行时契约应以依赖包实际能力为准。
2. 对外接口应与文档一致，同时避免破坏旧调用方。
3. Actor/Dask 路径和直连路径需要同一命名语义。

### 关键改动

- `packages/core/infrastructure/providers/implementations/amazingdata/amazingdata_extended.py`
  - 补齐 17 个缺失接口；
  - 新增 `get_option_mon_ctr_specs`，旧名 `get_option_mon_ctr_spcon` 作为兼容别名。
- `packages/core/infrastructure/providers/implementations/amazingdata/dask_adapter.py`
  - 同步新增转发方法；
  - 修正期权月合约方法命名并保留别名。
- `apps/api/api/endpoints/amazingdata/basic_data.py`
  - 新增 `future-code-list` / `option-code-list` / `adj-factor` / `stock-basic` 接口。
- `apps/api/api/endpoints/amazingdata/option.py`
  - 改为调用 `provider.get_option_mon_ctr_specs`。
- `apps/api/api/endpoints/amazingdata/router.py`
  - 更新模块接口统计（basic_data 与 total_endpoints）。
- 测试
  - 新增 `tests/unit/api/test_amazingdata_interface_alignment.py`（4 项，覆盖新增与更名接口调用路径）。

---

## 验证

1. `ruff check`（本轮修改文件）通过。
2. `pytest --noconftest tests/unit/api/test_amazingdata_interface_alignment.py -q` 通过（4 passed）。
3. 反编译对齐复核：`AmazingDataExtended` 相比 SDK 方法缺口从 17 降为 0。

---

## 关键结论

> 对第三方 SDK 的长期维护，必须建立“文档 + 反编译/源码 + 适配层”三方对齐机制，不能只依赖历史注释或旧版本经验判断。
