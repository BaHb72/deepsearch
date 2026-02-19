# AmazingData 全接口历史测试夹具与进程隔离守卫不兼容

- **发现日期**: 2026-02-17
- **严重程度**: 高
- **类型**: test-infrastructure / compatibility
- **状态**: resolved

## 问题描述

`tests/test_amazingdata_all_apis.py` 仍沿用旧版直连测试夹具：通过手工设置
`_initialized_objects=True` 和 `_base_data/_info_data/_market_data` mock 对象来绕过初始化。

在当前实现中，`AmazingDataExtended._ensure_data_objects()` 已强制要求进程隔离路径，
旧夹具不会触发新的可用路径，导致业务接口测试在入口统一抛出：

- `TGWError: AmazingData 必须使用进程隔离模式运行。`

同时该测试中还存在两个历史遗留问题：

1. `provider.get_calendar` 被固定 mock 成 `20250101/20250102`，与用例期望值冲突。  
2. `block_trading` 使用了过时方法名，应为 `get_block_trading`。

## 关键证据

- 失败文件：`tests/test_amazingdata_all_apis.py`
- 报错位置：`packages/core/infrastructure/providers/implementations/amazingdata/amazingdata_extended.py:281`
- 失败现象：`pytest tests/test_amazingdata_all_apis.py -q` 出现 `28 failed, 11 passed`

## 影响

1. 这组全接口回归测试成为持续误报源，无法准确反映真实回归状态。  
2. 变更评审阶段会被大量假阳性噪音干扰，掩盖真实缺陷。  
3. 新架构（进程隔离守卫）上线后，旧测试基线失效但未及时迁移。

## 解决记录

- **解决日期**: 2026-02-17
- **解决方式**:
  - 更新 fixture，显式将 `provider._ensure_data_objects` 替换为 `AsyncMock(return_value=None)`，
    让本测试继续作为“接口层 mock 回归”而非“隔离后端集成测试”。
  - 移除 `provider.get_calendar` 的错误固定返回值覆盖，恢复按 `_base_data.get_calendar` mock 断言。
  - 修正测试调用方法名：`block_trading` -> `get_block_trading`。
- **验证结果**:
  - `pytest tests/test_amazingdata_all_apis.py -q` -> `39 passed`
  - 相关回归集合（含 provider/config/docker/security/interface 对齐）共 `50 passed`

