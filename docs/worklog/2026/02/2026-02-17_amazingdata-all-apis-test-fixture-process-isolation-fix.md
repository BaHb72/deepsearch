# AmazingData 全接口历史测试夹具兼容进程隔离守卫

> 日期: 2026-02-17  
> 模块: amazingdata-tests, provider-test-fixture  
> 类型: bugfix / test-maintenance

---

## 为什么要改

`tests/test_amazingdata_all_apis.py` 是历史全接口回归用例，但夹具仍依赖旧直连初始化语义。
在当前 `AmazingDataExtended` 强制进程隔离守卫后，该测试大面积误报失败，无法继续承担回归基线作用。

---

## 诊断路径

1. 复现失败：`pytest tests/test_amazingdata_all_apis.py -q`，结果 `28 failed, 11 passed`。  
2. 查看堆栈，统一失败入口为 `AmazingDataExtended._ensure_data_objects()` 的 `DIRECT_MODE_DISABLED`。  
3. 审阅测试夹具，确认存在三处历史不兼容：
   - 仅设置 `_initialized_objects=True`，未绕过新的 `_ensure_data_objects` 守卫；
   - `get_calendar` 被硬编码为与断言不一致的日期；
   - `block_trading` 仍是旧方法名。

---

## 最终方案

### 选择: 将该文件明确定位为“接口 mock 回归”，不模拟真实进程隔离后端

原因：

1. 该文件目标是验证接口包装层调用与返回，不是验证进程隔离基础设施。  
2. 真实隔离链路已有其他测试覆盖；此处继续 mock 更稳定、执行更快。  
3. 可以最小改动修复误报，不引入新依赖和长耗时后端启动。

### 改动清单

- `tests/test_amazingdata_all_apis.py`
  - fixture 中新增 `provider._ensure_data_objects = AsyncMock(return_value=None)`；
  - 删除 `provider.get_calendar` 的错误覆盖；
  - 修正 `provider._info_data.block_trading` 为 `provider._info_data.get_block_trading`。

---

## 验证

1. `uv run --python ./.venv/Scripts/python.exe pytest tests/test_amazingdata_all_apis.py -q`  
   - 结果：`39 passed`
2. `uv run --python ./.venv/Scripts/python.exe pytest tests/unit/api/test_amazingdata_provider_resolution.py tests/unit/infrastructure/providers/test_fastapi_integration.py tests/unit/infrastructure/test_dockerfile_dask_security.py tests/unit/api/test_amazingdata_interface_alignment.py tests/test_amazingdata_all_apis.py -q`  
   - 结果：`50 passed`

---

## 结论

当 Provider 基础设施从“直连”演进到“强隔离”时，历史 mock 夹具必须同步更新其边界定义，否则会产生高噪音假失败并拖慢回归效率。

