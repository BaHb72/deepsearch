# AmazingData 接口实现与 SDK 1.0.28 文档/反编译结果不一致

- **发现日期**: 2026-02-17
- **严重程度**: 高
- **类型**: api-contract / compatibility
- **状态**: resolved

## 问题描述

基于最新文档 `docs/datasources/amazingdata/amazingdata_developer_manual.md` 与本地依赖 `AmazingData 1.0.28` 的 `.pyc` 反编译结果，发现接口实现存在下列不一致：

1. `get_option_mon_ctr_specs` 在代码中误写为 `get_option_mon_ctr_spcon`。
2. `AmazingDataExtended` 缺失多个 SDK 公开方法（基础数据与可转债相关）。
3. API 路由缺失文档中已声明的基础接口（如 `future-code-list`、`option-code-list`、`adj-factor`、`stock-basic`）。

## 关键证据

- 文档接口清单：`docs/datasources/amazingdata/amazingdata_developer_manual.md`
- SDK 反编译入口：
  - `.venv/Lib/site-packages/AmazingData/query_api/base_data.pyc`
  - `.venv/Lib/site-packages/AmazingData/query_api/info_data.pyc`
  - `.venv/Lib/site-packages/AmazingData/query_api/market_data.pyc`
- 代码位置：
  - `packages/core/infrastructure/providers/implementations/amazingdata/amazingdata_extended.py`
  - `packages/core/infrastructure/providers/implementations/amazingdata/dask_adapter.py`
  - `apps/api/api/endpoints/amazingdata/basic_data.py`
  - `apps/api/api/endpoints/amazingdata/option.py`

## 影响

1. 期权月合约接口在部分路径上会调用错误方法名导致运行失败。
2. 业务层无法使用 SDK 已提供的部分能力。
3. 接口文档、SDK 实现与 API 暴露面不一致，增加联调与运维排障成本。

## 解决记录

- **解决日期**: 2026-02-17
- **解决方式**:
  - `AmazingDataExtended` 补齐与 SDK 对齐的缺失方法：
    - 基础数据：`get_future_code_list`、`get_option_code_list`、`get_future_code_info`、`get_adj_factor`、`get_stock_basic`
    - 期权：`get_option_mon_ctr_specs`（并保留 `get_option_mon_ctr_spcon` 兼容别名）
    - 可转债：`get_kzz_issuance`、`get_kzz_share`、`get_kzz_conv`、`get_kzz_conv_change`、`get_kzz_corr`、`get_kzz_call`、`get_kzz_put`、`get_kzz_put_call_item`、`get_kzz_put_explanation`、`get_kzz_call_explanation`、`get_kzz_suspend`
  - `DaskAdapter` 同步上述关键接口转发，修正 `get_option_mon_ctr_specs` 命名并保留旧别名。
  - `AmazingData` 基础路由补齐：
    - `GET /basic/future-code-list`
    - `GET /basic/option-code-list`
    - `POST /basic/adj-factor`
    - `POST /basic/stock-basic`
  - `option` 路由改为调用 `provider.get_option_mon_ctr_specs`。
  - 新增回归测试：`tests/unit/api/test_amazingdata_interface_alignment.py`（4 项通过）。
