# T-Trading 止血：多数据源回退与运行时守护

> 日期: 2026-02-17
> 模块: strategy-center / ttrading / provider-factory
> 类型: bugfix / stability

---

## 背景

用户反馈系统在 MiniQMT 不可用场景下出现连锁失败：

1. `/strategy/ttrading` 页面状态与真实连接不一致；
2. `kline/intraday/start_engine` 对 MiniQMT 依赖过硬，单点失败会放大为 500；
3. 业务链路缺少端点级止血回退，不利于 AmazingData/AkShare 并行兜底验证。

---

## 根因

1. `DataProviderFactory.get_provider_async()` 默认严格模式，创建 Actor 失败直接抛异常，端点层无法软失败处理。
2. `ttrading` 端点原先以单源调用为主，MiniQMT 不可用时没有统一回退编排。
3. 新增回退代码中使用 `cast(...)` 但缺少导入，存在运行时 `NameError` 风险。
4. 既有测试仍按“探活失败即 mock”旧契约断言，未覆盖新回退行为。

---

## 修复内容

1. `apps/api/api/providers.py`
   - 为 `DataProviderFactory.get_provider_async(...)` 增加 `strict: bool = True` 参数；
   - `amazingdata/miniqmt` 创建失败时：
     - `strict=True` 维持原语义（抛异常）；
     - `strict=False` 返回 `None`，供端点层继续回退。

2. `apps/api/api/endpoints/strategy_center/ttrading.py`
   - 增加 `_FailoverIntradayDataProvider`，回退顺序固定为 `miniqmt -> amazingdata -> akshare`；
   - `quick_analyze`、`intraday`、`kline`、`start_engine(use_real_data=true)` 统一接入回退逻辑；
   - `datasource/status` 在 MiniQMT 探活失败后继续检查 AmazingData/AkShare；
   - 修复 `cast` 未导入导致的运行时错误。

3. 测试补强
   - 更新 `tests/api/test_strategy_center_ttrading_api.py` 为新契约；
   - 新增 `tests/api/test_strategy_center_ttrading_failover.py`，覆盖：
     - 三源不可用返回 `503`；
     - 有回退源时引擎可启动；
     - MiniQMT 断开时 `kline` 能回退到 provider。

---

## 验证路径（留痕）

1. 依赖检查
   - `uv pip check --python ./.venv/Scripts/python.exe`

2. 编译检查
   - `./.venv/Scripts/python.exe -m py_compile apps/api/api/endpoints/strategy_center/ttrading.py`
   - `./.venv/Scripts/python.exe -m py_compile apps/api/api/providers.py`

3. 定向回归
   - `./.venv/Scripts/python.exe -m pytest tests/api/test_strategy_center_ttrading_failover.py tests/unit/strategies/test_ttrading_providers.py tests/api/test_strategy_center_ttrading_kline_collector_reuse.py tests/api/test_strategy_center_ttrading_api.py -q`
   - 结果：`12 passed`

---

## 当前残余风险

1. 测试退出阶段存在 Loguru `I/O operation on closed file` 日志错误（不影响本次用例通过，但建议单独治理日志 sink 生命周期）。
2. Dask Client 与 Scheduler/Worker 的 `numpy/pandas` 版本告警仍存在，生产环境建议继续做版本对齐以降低运行时不确定性。

---

## 结论

本次止血目标已达成：MiniQMT 不可用不会直接拖垮 `ttrading` 主链路，系统可自动尝试 AmazingData/AkShare，并在三源均不可用时返回可诊断的 `503`，避免“单源失败即全链路 500”。
